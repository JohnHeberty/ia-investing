from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from apps.api.dependencies import get_execution_service
from apps.api.security import AuthContext, require_permission
from ia_investing.application.execution_service import (  # type: ignore[attr-defined]
    ExecutionService,
    InsufficientBalanceError,
    InvalidTransitionError,
)

router = APIRouter(prefix="/api/v1/executions", tags=["executions"])


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


@router.post("", status_code=201)
async def create_execution(
    body: CreateExecutionRequest,
    _auth: AuthContext = Depends(require_permission("execution:*")),
    service: ExecutionService = Depends(get_execution_service),
) -> dict[str, Any]:
    execution = await service.create_execution(
        order_id=body.order_id,
        portfolio_id=body.portfolio_id,
        action=body.action,
        quantity=body.quantity,
        price_limit=body.price_limit,
        actor_id=UUID(_auth.subject) if _auth.subject else None,
    )
    return {
        "id": str(execution.id),
        "order_id": execution.order_id,
        "state": execution.state,
        "action": execution.action,
        "quantity": str(execution.quantity),
    }


@router.get("")
async def list_executions(
    portfolio_id: UUID | None = Query(None),
    state: str | None = Query(None),
    from_date: datetime | None = Query(None),
    to_date: datetime | None = Query(None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    _auth: AuthContext = Depends(require_permission("execution:*")),
    service: ExecutionService = Depends(get_execution_service),
) -> dict[str, Any]:
    executions, total = await service.list_executions(
        portfolio_id=portfolio_id,
        state=state,
        from_date=from_date,
        to_date=to_date,
        limit=limit,
        offset=offset,
    )
    return {
        "items": [
            {
                "id": str(e.id),
                "order_id": e.order_id,
                "portfolio_id": str(e.portfolio_id),
                "action": e.action,
                "quantity": str(e.quantity),
                "state": e.state,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in executions
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/{execution_id}")
async def get_execution(
    execution_id: UUID,
    _auth: AuthContext = Depends(require_permission("execution:*")),
    service: ExecutionService = Depends(get_execution_service),
) -> dict[str, Any]:
    try:
        return await service.get_execution(execution_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{execution_id}/validate")
async def validate_execution(
    execution_id: UUID,
    _auth: AuthContext = Depends(require_permission("execution:*")),
    service: ExecutionService = Depends(get_execution_service),
) -> dict[str, Any]:
    try:
        execution = await service.validate_execution(
            execution_id=execution_id,
            actor_id=UUID(_auth.subject) if _auth.subject else None,
        )
    except (LookupError, InvalidTransitionError) as exc:
        raise HTTPException(status_code=404 if isinstance(exc, LookupError) else 409, detail=str(exc)) from exc
    return {"id": str(execution.id), "state": execution.state}


@router.post("/{execution_id}/queue")
async def queue_execution(
    execution_id: UUID,
    _auth: AuthContext = Depends(require_permission("execution:*")),
    service: ExecutionService = Depends(get_execution_service),
) -> dict[str, Any]:
    try:
        execution = await service.queue_execution(
            execution_id=execution_id,
            actor_id=UUID(_auth.subject) if _auth.subject else None,
        )
    except (LookupError, InvalidTransitionError) as exc:
        raise HTTPException(status_code=404 if isinstance(exc, LookupError) else 409, detail=str(exc)) from exc
    return {"id": str(execution.id), "state": execution.state}


@router.post("/{execution_id}/dispatch")
async def dispatch_execution(
    execution_id: UUID,
    _auth: AuthContext = Depends(require_permission("execution:*")),
    service: ExecutionService = Depends(get_execution_service),
) -> dict[str, Any]:
    try:
        execution = await service.dispatch_execution(
            execution_id=execution_id,
            actor_id=UUID(_auth.subject) if _auth.subject else None,
        )
    except (LookupError, InvalidTransitionError, InsufficientBalanceError) as exc:
        status = 404 if isinstance(exc, LookupError) else 409
        raise HTTPException(status_code=status, detail=str(exc)) from exc
    return {
        "id": str(execution.id),
        "state": execution.state,
        "dispatched_at": execution.dispatched_at.isoformat() if execution.dispatched_at else None,
    }


@router.post("/{execution_id}/confirm")
async def confirm_execution(
    execution_id: UUID,
    body: ConfirmExecutionRequest,
    _auth: AuthContext = Depends(require_permission("execution:*")),
    service: ExecutionService = Depends(get_execution_service),
) -> dict[str, Any]:
    try:
        execution = await service.confirm_execution(
            execution_id=execution_id,
            filled_quantity=body.filled_quantity,
            avg_price=body.avg_price,
            actor_id=UUID(_auth.subject) if _auth.subject else None,
        )
    except (LookupError, InvalidTransitionError) as exc:
        raise HTTPException(status_code=404 if isinstance(exc, LookupError) else 409, detail=str(exc)) from exc
    return {
        "id": str(execution.id),
        "state": execution.state,
        "filled_quantity": str(execution.filled_quantity),
        "avg_price": str(execution.avg_price),
    }


@router.post("/{execution_id}/fail")
async def fail_execution(
    execution_id: UUID,
    body: FailExecutionRequest,
    _auth: AuthContext = Depends(require_permission("execution:*")),
    service: ExecutionService = Depends(get_execution_service),
) -> dict[str, Any]:
    try:
        execution = await service.fail_execution(
            execution_id=execution_id,
            reason=body.reason,
            actor_id=UUID(_auth.subject) if _auth.subject else None,
        )
    except (LookupError, InvalidTransitionError) as exc:
        raise HTTPException(status_code=404 if isinstance(exc, LookupError) else 409, detail=str(exc)) from exc
    return {"id": str(execution.id), "state": execution.state, "reason": execution.reason}


@router.post("/{execution_id}/settle")
async def settle_execution(
    execution_id: UUID,
    _auth: AuthContext = Depends(require_permission("execution:*")),
    service: ExecutionService = Depends(get_execution_service),
) -> dict[str, Any]:
    try:
        execution = await service.settle_execution(
            execution_id=execution_id,
            actor_id=UUID(_auth.subject) if _auth.subject else None,
        )
    except (LookupError, InvalidTransitionError) as exc:
        raise HTTPException(status_code=404 if isinstance(exc, LookupError) else 409, detail=str(exc)) from exc
    return {
        "id": str(execution.id),
        "state": execution.state,
        "settled_at": execution.settled_at.isoformat() if execution.settled_at else None,
    }
