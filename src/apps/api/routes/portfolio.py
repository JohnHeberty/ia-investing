from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.security import AuthContext, get_auth_context
from database.core import get_async_session
from ia_investing.application.paper_portfolio import PaperPortfolioService
from ia_investing.application.portfolio import BackendPortfolioOptimizationService
from ia_investing.domain.identity import InstitutionalAccessContext

router = APIRouter(prefix="/api/v1/portfolio", tags=["portfolio"])


class PortfolioCreate(BaseModel):
    name: str
    description: str | None = None
    is_paper_trading: bool = True
    base_currency: str = "BRL"
    initial_capital: float | None = None


class PositionCreate(BaseModel):
    issuer_id: str | None = None
    ticker_symbol: str
    quantity: float
    avg_cost_per_share: float
    current_price: float | None = None


class OptimizationRequest(BaseModel):
    portfolio_id: uuid.UUID
    as_of: datetime


@router.post("", status_code=201)
async def create_portfolio(
    body: PortfolioCreate,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=255)],
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    svc = PaperPortfolioService(session)
    d = await svc.create(
        name=body.name,
        description=body.description,
        is_paper_trading=body.is_paper_trading,
        base_currency=body.base_currency,
        initial_capital=body.initial_capital,
        organization_id=auth.organization_id,
    )
    return {k: d[k] for k in ("id", "name", "is_paper_trading", "base_currency")}


@router.get("")
async def list_portfolios(
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
) -> list[dict[str, Any]]:
    return await PaperPortfolioService(session).list_all(organization_id=auth.organization_id)


@router.get("/{portfolio_id}")
async def get_portfolio(
    portfolio_id: uuid.UUID,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    result = await PaperPortfolioService(session).get_with_positions(
        portfolio_id,
        organization_id=auth.organization_id,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Portfolio not found")
    return result


@router.post("/{portfolio_id}/positions", status_code=201)
async def add_position(
    portfolio_id: uuid.UUID,
    body: PositionCreate,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=255)],
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    try:
        return await PaperPortfolioService(session).add_position(
            portfolio_id=portfolio_id,
            ticker_symbol=body.ticker_symbol,
            quantity=body.quantity,
            avg_cost_per_share=body.avg_cost_per_share,
            issuer_id=body.issuer_id,
            current_price=body.current_price,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/optimize")
async def run_optimization(
    body: OptimizationRequest,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=255)],
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    if auth.organization_id is None:
        raise HTTPException(status_code=403, detail="Institutional organization context is required")
    context = InstitutionalAccessContext(auth.subject, auth.organization_id, auth.team_ids, auth.permissions, "paper")
    try:
        run = await BackendPortfolioOptimizationService(session).optimize(body.portfolio_id, body.as_of, context)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {
        "operation_id": str(run.id),
        "status": run.status,
        "weights": run.weights,
        "trades": run.trades,
        "slacks": run.slacks,
        "diagnostics": run.diagnostics,
        "input_sha256": run.input_sha256,
    }
