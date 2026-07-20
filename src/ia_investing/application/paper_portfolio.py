from __future__ import annotations

import uuid
from typing import Any

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.portfolio import Portfolio, Position


class PaperPortfolioService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        name: str,
        description: str | None = None,
        is_paper_trading: bool = True,
        base_currency: str = "BRL",
        initial_capital: float | None = None,
    ) -> dict[str, Any]:
        portfolio = Portfolio(
            name=name,
            description=description,
            is_paper_trading=is_paper_trading,
            base_currency=base_currency,
            initial_capital=initial_capital,
        )
        self._session.add(portfolio)
        await self._session.flush()
        return self._to_dict(portfolio)

    async def list_all(self) -> list[dict[str, Any]]:
        stmt = sa.select(Portfolio).order_by(Portfolio.created_at.desc())
        result = await self._session.execute(stmt)
        rows = result.scalars().all()
        return [self._to_dict(r) for r in rows]

    async def get_with_positions(self, portfolio_id: uuid.UUID) -> dict[str, Any] | None:
        stmt = sa.select(Portfolio).where(Portfolio.id == portfolio_id)
        result = await self._session.execute(stmt)
        portfolio = result.scalar_one_or_none()
        if portfolio is None:
            return None

        pos_stmt = sa.select(Position).where(Position.portfolio_id == portfolio_id)
        pos_result = await self._session.execute(pos_stmt)
        positions = pos_result.scalars().all()

        return {
            **self._to_dict(portfolio),
            "positions": [self._position_to_dict(p) for p in positions],
        }

    async def add_position(
        self,
        portfolio_id: uuid.UUID,
        ticker_symbol: str,
        quantity: float,
        avg_cost_per_share: float,
        issuer_id: str | None = None,
        current_price: float | None = None,
    ) -> dict[str, Any]:
        pos_stmt = sa.select(Portfolio).where(Portfolio.id == portfolio_id)
        pos_result = await self._session.execute(pos_stmt)
        if pos_result.scalar_one_or_none() is None:
            raise LookupError("Portfolio not found")

        position = Position(
            portfolio_id=portfolio_id,
            issuer_id=uuid.UUID(issuer_id) if issuer_id else None,
            ticker_symbol=ticker_symbol,
            quantity=quantity,
            avg_cost_per_share=avg_cost_per_share,
            current_price=current_price,
        )
        self._session.add(position)
        await self._session.flush()
        return {
            "id": str(position.id),
            "ticker_symbol": position.ticker_symbol,
            "quantity": float(position.quantity),
            "avg_cost_per_share": float(position.avg_cost_per_share),
        }

    @staticmethod
    def _to_dict(p: Portfolio) -> dict[str, Any]:
        return {
            "id": str(p.id),
            "name": p.name,
            "description": p.description,
            "is_paper_trading": p.is_paper_trading,
            "base_currency": p.base_currency,
        }

    @staticmethod
    def _position_to_dict(p: Position) -> dict[str, Any]:
        return {
            "id": str(p.id),
            "ticker_symbol": p.ticker_symbol,
            "quantity": float(p.quantity) if p.quantity else None,
            "avg_cost_per_share": float(p.avg_cost_per_share) if p.avg_cost_per_share else None,
            "weight_pct": p.weight_pct,
        }
