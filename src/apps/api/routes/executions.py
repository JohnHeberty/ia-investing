from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field

from apps.api._errors import map_error
from apps.api.dependencies import get_execution_service
from apps.api.security import AuthContext, require_permission, safe_uuid
from ia_investing.application._audit_mixin import AuditMixin
from ia_investing.application.execution_service import (  # type: ignore[attr-defined]
    ExecutionService,
    InsufficientBalanceError,
    InvalidTransitionError,
)

router = APIRouter(prefix="/api/v1/executions", tags=["executions"])
_audit = AuditMixin()


class CreateExecutionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    order_id: str = Field(min_length=1, max_length=100)
    portfolio_id: UUID
    action: str = Field(pattern=r"^(buy|sell)$")
    quantity: Decimal = Field(gt=0)
    price_limit: Decimal | None = None


class ConfirmExecutionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    filled_quantity: Decimal = Field(gt=0)
    avg_price: Decimal = Field(gt=0)


class FailExecutionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=1, max_length=500)


class ExecutionCreatedResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    order_id: str
    state: str
    action: str
    quantity: str


class ExecutionListItem(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    order_id: str
    portfolio_id: str
    action: str
    quantity: str
    state: str
    created_at: str | None = None


class PaginatedExecutions(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    items: list[ExecutionListItem]
    total: int
    limit: int
    offset: int


class ExecutionStateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    state: str


class ExecutionDispatchedResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    state: str
    dispatched_at: str | None = None


class ExecutionConfirmedResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    state: str
    filled_quantity: str
    avg_price: str


class ExecutionFailedResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    state: str
    reason: str


class ExecutionSettledResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    state: str
    settled_at: str | None = None


def _actor_id(auth: AuthContext) -> UUID | None:
    try:
        return safe_uuid(auth.subject)
    except (ValueError, AttributeError):
        return None


@router.post("", status_code=201, response_model=ExecutionCreatedResponse)
async def create_execution(
    body: CreateExecutionRequest,
    auth: AuthContext = Depends(require_permission("execution:*")),
    service: ExecutionService = Depends(get_execution_service),
) -> ExecutionCreatedResponse:
    execution = await service.create_execution(
        order_id=body.order_id,
        portfolio_id=body.portfolio_id,
        action=body.action,
        quantity=body.quantity,
        price_limit=body.price_limit,
        actor_id=_actor_id(auth),
    )
    await _audit._audit(
        session=service._session,
        tenant_id=auth.organization_id,
        actor_id=_actor_id(auth),
        action="create",
        resource_type="execution",
        resource_id=execution.id,
    )
    return ExecutionCreatedResponse(
        id=str(execution.id),
        order_id=execution.order_id,
        state=execution.state,
        action=execution.action,
        quantity=str(execution.quantity),
    )


@router.get("", response_model=PaginatedExecutions)
async def list_executions(
    portfolio_id: UUID | None = Query(None),
    state: str | None = Query(None),
    from_date: datetime | None = Query(None),
    to_date: datetime | None = Query(None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    auth: AuthContext = Depends(require_permission("execution:*")),
    service: ExecutionService = Depends(get_execution_service),
) -> PaginatedExecutions:
    executions, total = await service.list_executions(
        portfolio_id=portfolio_id,
        state=state,
        from_date=from_date,
        to_date=to_date,
        limit=limit,
        offset=offset,
    )
    return PaginatedExecutions(
        items=[
            ExecutionListItem(
                id=str(e.id),
                order_id=e.order_id,
                portfolio_id=str(e.portfolio_id),
                action=e.action,
                quantity=str(e.quantity),
                state=e.state,
                created_at=e.created_at.isoformat() if e.created_at else None,
            )
            for e in executions
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{execution_id}", response_model=dict[str, Any])
async def get_execution(
    execution_id: UUID,
    auth: AuthContext = Depends(require_permission("execution:*")),
    service: ExecutionService = Depends(get_execution_service),
) -> dict[str, Any]:
    try:
        return await service.get_execution(execution_id)
    except LookupError as exc:
        raise map_error(exc) from exc


@router.post("/{execution_id}/validate", response_model=ExecutionStateResponse)
async def validate_execution(
    execution_id: UUID,
    auth: AuthContext = Depends(require_permission("execution:*")),
    service: ExecutionService = Depends(get_execution_service),
) -> ExecutionStateResponse:
    try:
        execution = await service.validate_execution(
            execution_id=execution_id,
            actor_id=_actor_id(auth),
        )
    except (LookupError, InvalidTransitionError) as exc:
        raise map_error(exc) from exc
    await _audit._audit(
        session=service._session,
        tenant_id=auth.organization_id,
        actor_id=_actor_id(auth),
        action="update",
        resource_type="execution",
        resource_id=execution_id,
        changes={"action": "validate"},
    )
    return ExecutionStateResponse(id=str(execution.id), state=execution.state)


@router.post("/{execution_id}/queue", response_model=ExecutionStateResponse)
async def queue_execution(
    execution_id: UUID,
    auth: AuthContext = Depends(require_permission("execution:*")),
    service: ExecutionService = Depends(get_execution_service),
) -> ExecutionStateResponse:
    try:
        execution = await service.queue_execution(
            execution_id=execution_id,
            actor_id=_actor_id(auth),
        )
    except (LookupError, InvalidTransitionError) as exc:
        raise map_error(exc) from exc
    await _audit._audit(
        session=service._session,
        tenant_id=auth.organization_id,
        actor_id=_actor_id(auth),
        action="update",
        resource_type="execution",
        resource_id=execution_id,
        changes={"action": "queue"},
    )
    return ExecutionStateResponse(id=str(execution.id), state=execution.state)


@router.post("/{execution_id}/dispatch", response_model=ExecutionDispatchedResponse)
async def dispatch_execution(
    execution_id: UUID,
    auth: AuthContext = Depends(require_permission("execution:*")),
    service: ExecutionService = Depends(get_execution_service),
) -> ExecutionDispatchedResponse:
    try:
        execution = await service.dispatch_execution(
            execution_id=execution_id,
            actor_id=_actor_id(auth),
        )
    except (LookupError, InvalidTransitionError, InsufficientBalanceError) as exc:
        raise map_error(exc) from exc
    await _audit._audit(
        session=service._session,
        tenant_id=auth.organization_id,
        actor_id=_actor_id(auth),
        action="execute",
        resource_type="execution",
        resource_id=execution_id,
    )
    return ExecutionDispatchedResponse(
        id=str(execution.id),
        state=execution.state,
        dispatched_at=execution.dispatched_at.isoformat() if execution.dispatched_at else None,
    )


@router.post("/{execution_id}/confirm", response_model=ExecutionConfirmedResponse)
async def confirm_execution(
    execution_id: UUID,
    body: ConfirmExecutionRequest,
    auth: AuthContext = Depends(require_permission("execution:*")),
    service: ExecutionService = Depends(get_execution_service),
) -> ExecutionConfirmedResponse:
    try:
        execution = await service.confirm_execution(
            execution_id=execution_id,
            filled_quantity=body.filled_quantity,
            avg_price=body.avg_price,
            actor_id=_actor_id(auth),
        )
    except (LookupError, InvalidTransitionError) as exc:
        raise map_error(exc) from exc
    await _audit._audit(
        session=service._session,
        tenant_id=auth.organization_id,
        actor_id=_actor_id(auth),
        action="update",
        resource_type="execution",
        resource_id=execution_id,
        changes={"action": "confirm"},
    )
    return ExecutionConfirmedResponse(
        id=str(execution.id),
        state=execution.state,
        filled_quantity=str(execution.filled_quantity),
        avg_price=str(execution.avg_price),
    )


@router.post("/{execution_id}/fail", response_model=ExecutionFailedResponse)
async def fail_execution(
    execution_id: UUID,
    body: FailExecutionRequest,
    auth: AuthContext = Depends(require_permission("execution:*")),
    service: ExecutionService = Depends(get_execution_service),
) -> ExecutionFailedResponse:
    try:
        execution = await service.fail_execution(
            execution_id=execution_id,
            reason=body.reason,
            actor_id=_actor_id(auth),
        )
    except (LookupError, InvalidTransitionError) as exc:
        raise map_error(exc) from exc
    await _audit._audit(
        session=service._session,
        tenant_id=auth.organization_id,
        actor_id=_actor_id(auth),
        action="update",
        resource_type="execution",
        resource_id=execution_id,
        changes={"action": "fail", "reason": body.reason},
    )
    return ExecutionFailedResponse(
        id=str(execution.id),
        state=execution.state,
        reason=execution.reason or "unspecified failure",
    )


@router.post("/{execution_id}/settle", response_model=ExecutionSettledResponse)
async def settle_execution(
    execution_id: UUID,
    auth: AuthContext = Depends(require_permission("execution:*")),
    service: ExecutionService = Depends(get_execution_service),
) -> ExecutionSettledResponse:
    try:
        execution = await service.settle_execution(
            execution_id=execution_id,
            actor_id=_actor_id(auth),
        )
    except (LookupError, InvalidTransitionError) as exc:
        raise map_error(exc) from exc
    await _audit._audit(
        session=service._session,
        tenant_id=auth.organization_id,
        actor_id=_actor_id(auth),
        action="update",
        resource_type="execution",
        resource_id=execution_id,
        changes={"action": "settle"},
    )
    return ExecutionSettledResponse(
        id=str(execution.id),
        state=execution.state,
        settled_at=execution.settled_at.isoformat() if execution.settled_at else None,
    )
