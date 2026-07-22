from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.security import AuthContext, require_permission
from database.core import get_async_session
from ia_investing.application.rebalance_service import RebalanceService

router = APIRouter(prefix="/api/v1/rebalance", tags=["rebalance"])


class ProposeRequest(BaseModel):
    target_allocations: dict[str, float]
    rationale: str = Field(min_length=1, max_length=2000)


class ApproveRequest(BaseModel):
    notes: str | None = None


class ExecuteStepRequest(BaseModel):
    trade_ids: list[uuid.UUID]


class CancelRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=1000)


async def get_rebalance_service(
    session: AsyncSession = Depends(get_async_session),
) -> RebalanceService:
    return RebalanceService(session)


RebalanceSvc = Annotated[RebalanceService, Depends(get_rebalance_service)]
AuthCtx = Annotated[AuthContext, Depends(require_permission("rebalance:*"))]


@router.get("/{portfolio_id}/drift")
async def get_drift(
    portfolio_id: uuid.UUID,
    svc: RebalanceSvc,
    auth: AuthCtx,
) -> dict[str, Any]:
    try:
        return await svc.get_drift_summary(portfolio_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{portfolio_id}/propose", status_code=201)
async def propose_rebalance(
    portfolio_id: uuid.UUID,
    body: ProposeRequest,
    svc: RebalanceSvc,
    auth: AuthCtx,
) -> dict[str, Any]:
    try:
        return await svc.propose_rebalance(
            portfolio_id=portfolio_id,
            target_allocations=body.target_allocations,
            rationale=body.rationale,
            created_by=auth.subject,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/proposals")
async def list_proposals(
    svc: RebalanceSvc,
    auth: AuthCtx,
    status: str | None = Query(default=None),
    portfolio_id: uuid.UUID | None = Query(default=None),
) -> list[dict[str, Any]]:
    return await svc.list_proposals(status=status, portfolio_id=portfolio_id)


@router.get("/proposals/{proposal_id}")
async def get_proposal(
    proposal_id: uuid.UUID,
    svc: RebalanceSvc,
    auth: AuthCtx,
) -> dict[str, Any]:
    try:
        return await svc.get_rebalance_status(proposal_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/proposals/{proposal_id}/approve")
async def approve_proposal(
    proposal_id: uuid.UUID,
    body: ApproveRequest,
    svc: RebalanceSvc,
    auth: AuthCtx,
) -> dict[str, Any]:
    try:
        return await svc.approve_rebalance(
            proposal_id=proposal_id,
            approver_id=auth.subject,
            notes=body.notes,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/proposals/{proposal_id}/execute-step")
async def execute_step(
    proposal_id: uuid.UUID,
    body: ExecuteStepRequest,
    svc: RebalanceSvc,
    auth: AuthCtx,
) -> dict[str, Any]:
    try:
        return await svc.execute_rebalance_step(
            proposal_id=proposal_id,
            trade_ids=body.trade_ids,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/proposals/{proposal_id}/complete")
async def complete_proposal(
    proposal_id: uuid.UUID,
    svc: RebalanceSvc,
    auth: AuthCtx,
) -> dict[str, Any]:
    try:
        return await svc.complete_rebalance(proposal_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/proposals/{proposal_id}/cancel")
async def cancel_proposal(
    proposal_id: uuid.UUID,
    body: CancelRequest,
    svc: RebalanceSvc,
    auth: AuthCtx,
) -> dict[str, Any]:
    try:
        return await svc.cancel_rebalance(
            proposal_id=proposal_id,
            reason=body.reason,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/{portfolio_id}/history")
async def get_history(
    portfolio_id: uuid.UUID,
    svc: RebalanceSvc,
    auth: AuthCtx,
) -> list[dict[str, Any]]:
    try:
        return await svc.get_history(portfolio_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
