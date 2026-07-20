from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, HTTPException
from opentelemetry import trace
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.security import AuthContext, get_auth_context, require_permission
from database.core import get_async_session
from ia_investing.application.agent_runtime import AgentRuntimeService

router = APIRouter(prefix="/api/v1/agent-runs", tags=["agent-runtime"])


class CreateAgentRunV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    capability: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    case_id: UUID | None = None
    input: dict[str, object]
    data_as_of: datetime
    knowledge_cutoff: datetime
    version_pin: UUID | None = None


class AgentRunV1(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: UUID
    capability_id: UUID
    agent_version_id: UUID
    case_id: UUID | None
    workflow_id: str | None
    trace_id: str
    input_sha256: str
    output_payload: dict[str, object] | None
    data_as_of: datetime
    knowledge_cutoff: datetime
    status: str
    prompt_tokens: int
    completion_tokens: int
    cost_usd: Decimal
    duration_ms: int | None
    evidence_coverage: Decimal | None
    error_code: str | None
    error_detail: str | None
    created_at: datetime


class ApprovalDecisionV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: str = Field(pattern=r"^(approved|rejected)$")
    reason: str = Field(min_length=1, max_length=2_000)


class ApprovalV1(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: UUID
    run_id: UUID
    tool_call_id: UUID
    scope: str
    impact: dict[str, object]
    requested_by: str
    requested_at: datetime
    expires_at: datetime
    status: str
    decided_by: str | None
    decision_reason: str | None
    decided_at: datetime | None


@router.post("", response_model=AgentRunV1, status_code=202)
async def create_agent_run(
    body: CreateAgentRunV1,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=255)],
    auth: AuthContext = Depends(require_permission("agent_runs:create")),
    trace_id: Annotated[str | None, Header(alias="X-Trace-ID")] = None,
    session: AsyncSession = Depends(get_async_session),
) -> AgentRunV1:
    current_span = trace.get_current_span()
    otel_trace_id = current_span.get_span_context().trace_id
    try:
        run = await AgentRuntimeService(session).create_run(
            capability=body.capability,
            case_id=body.case_id,
            input_payload=body.input,
            data_as_of=body.data_as_of,
            knowledge_cutoff=body.knowledge_cutoff,
            actor_id=auth.subject,
            permissions=auth.permissions,
            version_pin=body.version_pin,
            trace_id=f"{otel_trace_id:032x}" if otel_trace_id else trace_id,
            idempotency_key=idempotency_key,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    current_span.set_attributes(
        {
            "agent.run_id": str(run.id),
            "agent.case_id": str(run.case_id) if run.case_id else "",
            "agent.trace_id": run.trace_id,
            "agent.capability_id": str(run.capability_id),
        }
    )
    return AgentRunV1.model_validate(run)


@router.get("/{run_id}", response_model=AgentRunV1)
async def get_agent_run(
    run_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
) -> AgentRunV1:
    if "agent_runs:read" not in auth.permissions:
        raise HTTPException(status_code=403, detail="Permission denied")
    run = await AgentRuntimeService(session).get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="agent run not found")
    return AgentRunV1.model_validate(run)


@router.post("/approvals/{approval_id}/decision", response_model=ApprovalV1)
async def decide_agent_approval(
    approval_id: UUID,
    body: ApprovalDecisionV1,
    auth: AuthContext = Depends(get_auth_context),
    correlation_id: UUID | None = Header(default=None, alias="X-Correlation-ID"),
    session: AsyncSession = Depends(get_async_session),
) -> ApprovalV1:
    try:
        approval = await AgentRuntimeService(session).decide_approval(
            approval_id=approval_id,
            decision=body.decision,
            actor_id=auth.subject,
            permissions=auth.permissions,
            reason=body.reason,
            correlation_id=correlation_id or uuid4(),
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return ApprovalV1.model_validate(approval)
