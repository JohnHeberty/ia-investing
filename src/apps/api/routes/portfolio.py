from __future__ import annotations

import uuid
from typing import Any

import polars as pl
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.core import get_async_session
from database.models.portfolio import Portfolio, Position
from portfolio import PortfolioOptimizer

router = APIRouter(prefix="/api/v1/portfolio", tags=["portfolio"])


def _portfolio_to_dict(p: Portfolio) -> dict[str, Any]:
    return {
        "id": str(p.id),
        "name": p.name,
        "description": p.description,
        "is_paper_trading": p.is_paper_trading,
        "base_currency": p.base_currency,
    }


def _position_to_dict(p: Position) -> dict[str, Any]:
    return {
        "id": str(p.id),
        "ticker_symbol": p.ticker_symbol,
        "quantity": float(p.quantity) if p.quantity else None,
        "avg_cost_per_share": float(p.avg_cost_per_share) if p.avg_cost_per_share else None,
        "weight_pct": p.weight_pct,
    }


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
    portfolio_id: str
    returns_data: list[dict[str, Any]]
    current_weights: dict[str, float] | None = None
    risk_aversion: float = 1.0
    max_weight: float = 0.10
    max_sector: float = 0.30
    max_turnover: float = 0.20


@router.post("", status_code=201)
async def create_portfolio(
    body: PortfolioCreate,
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    portfolio = Portfolio(
        name=body.name,
        description=body.description,
        is_paper_trading=body.is_paper_trading,
        base_currency=body.base_currency,
        initial_capital=body.initial_capital,
    )
    session.add(portfolio)
    await session.flush()
    d = _portfolio_to_dict(portfolio)
    return {k: d[k] for k in ("id", "name", "is_paper_trading", "base_currency")}


@router.get("")
async def list_portfolios(
    session: AsyncSession = Depends(get_async_session),
) -> list[dict[str, Any]]:
    stmt = select(Portfolio).order_by(Portfolio.created_at.desc())
    result = await session.execute(stmt)
    rows = result.scalars().all()
    return [_portfolio_to_dict(r) for r in rows]


@router.get("/{portfolio_id}")
async def get_portfolio(
    portfolio_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    stmt = select(Portfolio).where(Portfolio.id == portfolio_id)
    result = await session.execute(stmt)
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    pos_stmt = select(Position).where(Position.portfolio_id == portfolio_id)
    pos_result = await session.execute(pos_stmt)
    positions = pos_result.scalars().all()

    return {
        **_portfolio_to_dict(row),
        "positions": [_position_to_dict(p) for p in positions],
    }


@router.post("/{portfolio_id}/positions", status_code=201)
async def add_position(
    portfolio_id: uuid.UUID,
    body: PositionCreate,
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    stmt = select(Portfolio).where(Portfolio.id == portfolio_id)
    result = await session.execute(stmt)
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    position = Position(
        portfolio_id=portfolio_id,
        issuer_id=uuid.UUID(body.issuer_id) if body.issuer_id else None,
        ticker_symbol=body.ticker_symbol,
        quantity=body.quantity,
        avg_cost_per_share=body.avg_cost_per_share,
        current_price=body.current_price,
    )
    session.add(position)
    await session.flush()
    return {
        "id": str(position.id),
        "ticker_symbol": position.ticker_symbol,
        "quantity": float(position.quantity),
        "avg_cost_per_share": float(position.avg_cost_per_share),
    }


@router.post("/optimize")
async def run_optimization(body: OptimizationRequest) -> dict[str, Any]:
    returns_df = pl.DataFrame(body.returns_data)
    optimizer = PortfolioOptimizer(
        risk_aversion=body.risk_aversion,
        max_weight=body.max_weight,
        max_sector=body.max_sector,
        max_turnover=body.max_turnover,
    )
    result = await optimizer.optimize(returns_df, body.current_weights)
    return {
        "weights": result.weights,
        "expected_return": result.expected_return,
        "expected_risk": result.expected_risk,
        "sharpe_ratio": result.sharpe_ratio,
        "turnover": result.turnover,
        "transactions": result.transactions,
    }
