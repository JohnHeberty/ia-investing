from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api._errors import map_error
from apps.api.security import AuthContext, get_auth_context, safe_uuid
from database.core import get_async_session
from ia_investing.application._audit_mixin import AuditMixin
from ia_investing.application.paper_portfolio import PaperPortfolioService
from ia_investing.application.portfolio import BackendPortfolioOptimizationService
from ia_investing.domain.identity import InstitutionalAccessContext

router = APIRouter(prefix="/api/v1/portfolio", tags=["portfolio"])
_audit = AuditMixin()


class PortfolioCreate(BaseModel):
    name: str
    description: str | None = None
    is_paper_trading: bool = True
    base_currency: str = "BRL"
    initial_capital: float | None = None


class PositionCreate(BaseModel):
    issuer_id: str | None = None
    ticker_symbol: str
    quantity: float = Field(gt=0)
    avg_cost_per_share: float = Field(gt=0)
    current_price: float | None = None


class PositionUpdate(BaseModel):
    ticker_symbol: str | None = None
    quantity: float | None = None
    avg_cost_per_share: float | None = None
    current_price: float | None = None


class OptimizationRequest(BaseModel):
    portfolio_id: uuid.UUID
    as_of: datetime


class PortfolioCreatedResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str | None = None
    name: str | None = None
    is_paper_trading: bool | None = None
    base_currency: str | None = None


class PortfolioListItem(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    is_paper_trading: bool
    base_currency: str


class PortfolioDetailResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    name: str
    positions: list[Any]


class PortfolioOptimizationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    operation_id: str
    status: str
    weights: dict[str, Any]
    trades: list[Any]
    slacks: dict[str, Any]
    diagnostics: dict[str, Any]
    input_sha256: str


@router.post("", status_code=201, response_model=PortfolioCreatedResponse)
async def create_portfolio(
    body: PortfolioCreate,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=255)],
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
) -> PortfolioCreatedResponse:
    svc = PaperPortfolioService(session)
    d = await svc.create(
        name=body.name,
        description=body.description,
        is_paper_trading=body.is_paper_trading,
        base_currency=body.base_currency,
        initial_capital=body.initial_capital,
        organization_id=auth.organization_id,
    )
    portfolio_id = d.get("id")
    actor_uuid = None
    if auth.subject:
        try:
            actor_uuid = UUID(auth.subject)
        except ValueError:
            actor_uuid = None
    if auth.organization_id:
        await _audit._audit(
            session=session,
            tenant_id=auth.organization_id,
            actor_id=actor_uuid,
            action="create",
            resource_type="portfolio",
            resource_id=UUID(portfolio_id) if portfolio_id else None,
        )
    return PortfolioCreatedResponse(**{k: d.get(k) for k in ("id", "name", "is_paper_trading", "base_currency")})


@router.get("")
async def list_portfolios(
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> list[PortfolioListItem]:
    if auth.organization_id is None:
        raise HTTPException(status_code=403, detail="organization context is required")
    all_items = await PaperPortfolioService(session).list_all(organization_id=auth.organization_id)
    return [PortfolioListItem(**item) for item in all_items[offset : offset + limit]]


@router.get("/{portfolio_id}", response_model=dict[str, Any])
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
        raise map_error(LookupError("Portfolio not found"))
    return result


@router.delete("/{portfolio_id}", status_code=200)
async def delete_portfolio(
    portfolio_id: uuid.UUID,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    try:
        deleted = await PaperPortfolioService(session).delete_portfolio(
            portfolio_id, organization_id=auth.organization_id
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not deleted:
        raise HTTPException(status_code=404, detail="Portfolio not found")
    if auth.organization_id:
        await _audit._audit(
            session=session,
            tenant_id=auth.organization_id,
            actor_id=safe_uuid(auth.subject),
            action="delete",
            resource_type="portfolio",
            resource_id=portfolio_id,
        )
    return {"id": str(portfolio_id), "deleted": True}


@router.post("/{portfolio_id}/positions", status_code=201, response_model=dict[str, Any])
async def add_position(
    portfolio_id: uuid.UUID,
    body: PositionCreate,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=255)],
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    if auth.organization_id is None:
        raise HTTPException(status_code=403, detail="organization context is required")
    try:
        result = await PaperPortfolioService(session).add_position(
            portfolio_id=portfolio_id,
            ticker_symbol=body.ticker_symbol,
            quantity=body.quantity,
            avg_cost_per_share=body.avg_cost_per_share,
            issuer_id=body.issuer_id,
            current_price=body.current_price,
        )
    except LookupError as exc:
        raise map_error(exc) from exc
    actor_uuid = None
    if auth.subject:
        try:
            actor_uuid = UUID(auth.subject)
        except ValueError:
            actor_uuid = None
    if auth.organization_id:
        await _audit._audit(
            session=session,
            tenant_id=auth.organization_id,
            actor_id=actor_uuid,
            action="create",
            resource_type="portfolio_position",
            resource_id=portfolio_id,
        )
    return result


@router.put("/{portfolio_id}/positions/{position_id}", response_model=dict[str, Any])
async def update_position(
    portfolio_id: uuid.UUID,
    position_id: uuid.UUID,
    body: PositionUpdate,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    if auth.organization_id is None:
        raise HTTPException(status_code=403, detail="organization context is required")
    result = await PaperPortfolioService(session).update_position(
        portfolio_id=portfolio_id,
        position_id=position_id,
        ticker_symbol=body.ticker_symbol,
        quantity=body.quantity,
        avg_cost_per_share=body.avg_cost_per_share,
        current_price=body.current_price,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Position not found")
    await _audit._audit(
        session=session,
        tenant_id=auth.organization_id,
        actor_id=safe_uuid(auth.subject),
        action="update",
        resource_type="portfolio_position",
        resource_id=portfolio_id,
    )
    return result


@router.delete("/{portfolio_id}/positions/{position_id}", status_code=200)
async def delete_position(
    portfolio_id: uuid.UUID,
    position_id: uuid.UUID,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    if auth.organization_id is None:
        raise HTTPException(status_code=403, detail="organization context is required")
    deleted = await PaperPortfolioService(session).delete_position(portfolio_id, position_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Position not found")
    await _audit._audit(
        session=session,
        tenant_id=auth.organization_id,
        actor_id=safe_uuid(auth.subject),
        action="delete",
        resource_type="portfolio_position",
        resource_id=portfolio_id,
    )
    return {"deleted": True}


@router.post("/optimize", response_model=PortfolioOptimizationResponse)
async def run_optimization(
    body: OptimizationRequest,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=255)],
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
) -> PortfolioOptimizationResponse:
    if auth.organization_id is None:
        raise HTTPException(status_code=403, detail="Institutional organization context is required")
    context = InstitutionalAccessContext(auth.subject, auth.organization_id, auth.team_ids, auth.permissions, "paper")
    try:
        run = await BackendPortfolioOptimizationService(session).optimize(body.portfolio_id, body.as_of, context)
    except LookupError as exc:
        raise map_error(exc) from exc
    except PermissionError as exc:
        raise map_error(exc) from exc
    except ValueError as exc:
        raise map_error(exc) from exc
    if run is None:
        raise HTTPException(status_code=404, detail="Optimization run not found")
    await _audit._audit(
        session=session,
        tenant_id=auth.organization_id,
        actor_id=safe_uuid(auth.subject),
        action="execute",
        resource_type="portfolio_optimization",
        resource_id=run.id,
    )
    return PortfolioOptimizationResponse(
        operation_id=str(run.id),
        status=run.status,
        weights=run.weights,
        trades=run.trades,
        slacks=run.slacks,
        diagnostics=run.diagnostics,
        input_sha256=run.input_sha256,
    )
