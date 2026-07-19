from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field

from apps.api.dependencies import get_operation_service
from apps.api.security import AuthContext, require_permission
from ia_investing.application.operations import AgentRunCommand, IdempotencyConflictError, OperationService
from ia_investing.contracts.v1 import OperationAcceptedV1, OperationStatusV1

router = APIRouter(prefix="/api/v1", tags=["operations"])


class AgentRunCommandV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent_name: str = Field(min_length=1, max_length=100)
    input_data: dict[str, Any]


@router.post("/agent-runs", response_model=OperationAcceptedV1, status_code=202)
async def submit_agent_run(
    body: AgentRunCommandV1,
    response: Response,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=200)],
    _auth: AuthContext = Depends(require_permission("agent_runs:create")),
    service: OperationService = Depends(get_operation_service),
) -> OperationAcceptedV1:
    try:
        accepted = await service.submit_agent_run(
            AgentRunCommand(
                agent_name=body.agent_name,
                input_data=body.input_data,
                actor_subject=_auth.subject,
            ),
            idempotency_key,
        )
    except IdempotencyConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    response.headers["Location"] = f"/api/v1/operations/{accepted.operation_id}"
    return accepted


@router.get("/operations/{operation_id}", response_model=OperationStatusV1)
async def get_operation(
    operation_id: UUID,
    _auth: AuthContext = Depends(require_permission("operations:read")),
    service: OperationService = Depends(get_operation_service),
) -> OperationStatusV1:
    operation = await service.get(operation_id)
    if operation is None:
        raise HTTPException(status_code=404, detail="Operation not found")
    return operation
