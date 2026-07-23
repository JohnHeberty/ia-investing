from __future__ import annotations

import hashlib
import json
import logging
from datetime import UTC, datetime
from typing import Annotated, Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from temporalio.client import Client
from temporalio.exceptions import WorkflowAlreadyStartedError

from apps.api.dependencies import SessionDep
from apps.api.security import Principal, require_permission
from database.models.agents import AuditLog
from database.models.operations import Operation, OperationDispatchOutbox
from ia_investing.application.mission_control import MissionControlService
from ia_investing.contracts.v1 import MissionControlResponse, PortfolioRankItem

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["institutional"])


class AgentRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    capability: str = Field(min_length=1, max_length=100)
    case_id: UUID | None = None
    input_payload: dict[str, Any]
    data_as_of: datetime
    knowledge_cutoff: datetime

    @model_validator(mode="after")
    def validate_temporal_cutoff(self) -> AgentRunRequest:
        if self.knowledge_cutoff > self.data_as_of:
            raise ValueError("knowledge_cutoff cannot be after data_as_of")
        if self.data_as_of.tzinfo is None or self.knowledge_cutoff.tzinfo is None:
            raise ValueError("data_as_of and knowledge_cutoff must include a timezone")
        return self


class OperationAccepted(BaseModel):
    operation_id: str
    workflow_id: str
    status: str = "accepted"
    submitted_at: datetime
    duplicate: bool = False


class OperationStatusResponse(BaseModel):
    operation_id: UUID
    workflow_id: str
    status: str
    created_at: datetime
    updated_at: datetime
    result: dict[str, Any] | None = None
    error_code: str | None = None
    error_detail: str | None = None


async def _mark_dispatched(session: Any, outbox: OperationDispatchOutbox) -> None:
    outbox.state = "dispatched"
    outbox.dispatched_at = datetime.now(UTC)
    try:
        await session.commit()
    except Exception:
        await session.rollback()
        logger.exception("Temporal workflow started but outbox acknowledgement could not be persisted")


def organization_uuid(principal: Principal) -> UUID:
    if not principal.organization_id:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "The authenticated principal has no organization_id",
        )
    try:
        return UUID(str(principal.organization_id))
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "organization_id is not a UUID") from exc


@router.get("/dashboard/mission-control", response_model=MissionControlResponse)
async def mission_control(
    session: SessionDep,
    principal: Annotated[Principal, Depends(require_permission("dashboard:read"))],
    as_of: datetime | None = Query(default=None),
    top_limit: int = Query(default=5, ge=1, le=25, description="Maximum items per comparable cohort"),
) -> MissionControlResponse:
    return await MissionControlService(session).build(
        organization_id=organization_uuid(principal),
        as_of=as_of,
        top_limit=top_limit,
    )


@router.get("/model-portfolios", response_model=list[PortfolioRankItem])
async def list_model_portfolios(
    session: SessionDep,
    principal: Annotated[Principal, Depends(require_permission("portfolio:read"))],
    response: Response,
    if_none_match: Annotated[str | None, Header(alias="If-None-Match")] = None,
    as_of: datetime | None = Query(default=None),
) -> list[PortfolioRankItem] | Response:
    dashboard = await MissionControlService(session).build(
        organization_id=organization_uuid(principal),
        as_of=as_of,
        top_limit=100,
    )
    items = dashboard.top_portfolios + dashboard.excluded_portfolios
    serialized = [item.model_dump(mode="json") for item in items]
    etag = '"' + hashlib.sha256(json.dumps(serialized, sort_keys=True).encode()).hexdigest() + '"'
    if if_none_match == etag:
        return Response(status_code=status.HTTP_304_NOT_MODIFIED, headers={"ETag": etag})
    response.headers["ETag"] = etag
    return items


@router.post(
    "/agent-runs",
    response_model=OperationAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_agent_run(
    payload: AgentRunRequest,
    request: Request,
    session: SessionDep,
    principal: Annotated[Principal, Depends(require_permission("agent:run"))],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=200)],
) -> OperationAccepted:
    temporal: Client | None = request.app.state.temporal
    organization_id = organization_uuid(principal)
    request_data = {
        "organization_id": str(organization_id),
        "requested_by": principal.subject,
        "capability": payload.capability,
        "case_id": str(payload.case_id) if payload.case_id else None,
        "input_payload": payload.input_payload,
        "data_as_of": payload.data_as_of.isoformat(),
        "knowledge_cutoff": payload.knowledge_cutoff.isoformat(),
    }
    request_hash = hashlib.sha256(json.dumps(request_data, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

    existing = (
        await session.execute(
            select(Operation).where(
                Operation.organization_id == organization_id,
                Operation.operation_type == "agent-run",
                Operation.idempotency_key == idempotency_key,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        if existing.request_hash != request_hash:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "Idempotency-Key was already used with a different request",
            )
        return OperationAccepted(
            operation_id=str(existing.id),
            workflow_id=f"operation-{existing.id}",
            status=existing.state,
            submitted_at=existing.created_at,
            duplicate=True,
        )

    operation = Operation(
        id=uuid4(),
        organization_id=organization_id,
        operation_type="agent-run",
        idempotency_key=idempotency_key,
        request_hash=request_hash,
        state="pending",
        request_data=request_data,
    )
    outbox = OperationDispatchOutbox(
        id=uuid4(),
        organization_id=organization_id,
        operation_id=operation.id,
        topic="agent-run",
        state="pending",
        attempts=0,
        next_attempt_at=datetime.now(UTC),
    )
    session.add(operation)
    session.add(outbox)
    session.add(
        AuditLog(
            actor_type="human",
            actor_id=principal.subject,
            action="agent_run.submit",
            entity_type="operation",
            entity_id=operation.id,
            correlation_id=operation.id,
            details={
                "organization_id": str(organization_id),
                "capability": payload.capability,
                "idempotency_key_hash": hashlib.sha256(idempotency_key.encode()).hexdigest(),
            },
        )
    )
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        concurrent = (
            await session.execute(
                select(Operation).where(
                    Operation.organization_id == organization_id,
                    Operation.operation_type == "agent-run",
                    Operation.idempotency_key == idempotency_key,
                )
            )
        ).scalar_one_or_none()
        if concurrent is None or concurrent.request_hash != request_hash:
            raise HTTPException(status.HTTP_409_CONFLICT, "Idempotency conflict") from exc
        return OperationAccepted(
            operation_id=str(concurrent.id),
            workflow_id=f"operation-{concurrent.id}",
            status=concurrent.state,
            submitted_at=concurrent.created_at,
            duplicate=True,
        )

    workflow_id = f"operation-{operation.id}"
    if temporal is not None:
        try:
            from workflows import RunAgentInput, RunAgentWorkflow

            await temporal.start_workflow(
                RunAgentWorkflow.run,
                RunAgentInput(
                    operation_id=str(operation.id),
                    organization_id=str(organization_id),
                    capability=payload.capability,
                    case_id=str(payload.case_id) if payload.case_id else None,
                    input_payload=payload.input_payload,
                    data_as_of=payload.data_as_of.isoformat(),
                    knowledge_cutoff=payload.knowledge_cutoff.isoformat(),
                    requested_by=principal.subject,
                    idempotency_key=idempotency_key,
                ),
                id=workflow_id,
                task_queue="research-agents",
            )
            await _mark_dispatched(session, outbox)
        except WorkflowAlreadyStartedError:
            await _mark_dispatched(session, outbox)
        except Exception:
            await session.rollback()
            logger.exception("immediate Temporal dispatch failed; operation remains queued")

    return OperationAccepted(
        operation_id=str(operation.id),
        workflow_id=workflow_id,
        status=operation.state,
        submitted_at=operation.created_at,
    )


@router.get("/operations/{operation_id}", response_model=OperationStatusResponse)
async def get_operation_status(
    operation_id: UUID,
    session: SessionDep,
    principal: Annotated[Principal, Depends(require_permission("agent:read"))],
) -> OperationStatusResponse:
    operation = (
        await session.execute(
            select(Operation).where(
                Operation.id == operation_id,
                Operation.organization_id == organization_uuid(principal),
            )
        )
    ).scalar_one_or_none()
    if operation is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "operation not found")
    return OperationStatusResponse(
        operation_id=operation.id,
        workflow_id=f"operation-{operation.id}",
        status=operation.state,
        created_at=operation.created_at,
        updated_at=operation.updated_at,
        result=operation.result_data,
        error_code=operation.error_code,
        error_detail=operation.error_detail,
    )
