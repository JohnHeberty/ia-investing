from __future__ import annotations

import asyncio
import logging
import uuid
from decimal import Decimal
from typing import Any

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.portfolio import Portfolio, Position
from ia_investing.market_data import get_current_price

logger = logging.getLogger(__name__)


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
        organization_id: uuid.UUID | None = None,
    ) -> dict[str, Any]:
        portfolio = Portfolio(
            name=name,
            description=description,
            is_paper_trading=is_paper_trading,
            base_currency=base_currency,
            initial_capital=initial_capital,
            organization_id=organization_id,
        )
        self._session.add(portfolio)
        await self._session.flush()
        return self._to_dict(portfolio)

    async def list_all(self, organization_id: uuid.UUID) -> list[dict[str, Any]]:
        stmt = (
            sa.select(Portfolio)
            .where(Portfolio.organization_id == organization_id)
            .order_by(Portfolio.created_at.desc())
        )
        result = await self._session.execute(stmt)
        portfolios = result.scalars().all()

        portfolio_ids = [p.id for p in portfolios]
        all_positions: list[Position] = []
        if portfolio_ids:
            pos_stmt = sa.select(Position).where(Position.portfolio_id.in_(portfolio_ids))
            pos_result = await self._session.execute(pos_stmt)
            all_positions = list(pos_result.scalars().all())

        positions_by_portfolio: dict[uuid.UUID, list[Position]] = {}
        for pos in all_positions:
            positions_by_portfolio.setdefault(pos.portfolio_id, []).append(pos)

        return [
            {
                **self._to_dict(p),
                "positions": [self._position_to_dict(pos) for pos in positions_by_portfolio.get(p.id, [])],
            }
            for p in portfolios
        ]

    async def get_with_positions(
        self,
        portfolio_id: uuid.UUID,
        organization_id: uuid.UUID | None = None,
    ) -> dict[str, Any] | None:
        stmt = sa.select(Portfolio).where(Portfolio.id == portfolio_id)
        if organization_id is not None:
            stmt = stmt.where(Portfolio.organization_id == organization_id)
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

        if current_price is None:
            try:
                price_data = await asyncio.to_thread(get_current_price, ticker_symbol)
                if price_data and price_data.get("price"):
                    current_price = float(price_data["price"])
            except Exception:
                logger.warning("Unable to refresh market price for %s", ticker_symbol, exc_info=True)

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

        await self._recalculate_weights(portfolio_id)

        return self._position_to_dict(position)

    async def update_position(
        self,
        portfolio_id: uuid.UUID,
        position_id: uuid.UUID,
        ticker_symbol: str | None = None,
        quantity: float | None = None,
        avg_cost_per_share: float | None = None,
        current_price: float | None = None,
    ) -> dict[str, Any] | None:
        stmt = sa.select(Position).where(
            Position.id == position_id,
            Position.portfolio_id == portfolio_id,
        )
        result = await self._session.execute(stmt)
        position = result.scalar_one_or_none()
        if position is None:
            return None

        if ticker_symbol is not None:
            position.ticker_symbol = ticker_symbol
            if current_price is None:
                try:
                    price_data = await asyncio.to_thread(get_current_price, ticker_symbol)
                    if price_data and price_data.get("price"):
                        current_price = float(price_data["price"])
                except Exception:
                    logger.warning("Unable to refresh market price for %s", ticker_symbol, exc_info=True)
        if quantity is not None:
            position.quantity = Decimal(str(quantity))
        if avg_cost_per_share is not None:
            position.avg_cost_per_share = Decimal(str(avg_cost_per_share))
        if current_price is not None:
            position.current_price = Decimal(str(current_price))

        await self._session.flush()
        await self._recalculate_weights(portfolio_id)
        return self._position_to_dict(position)

    async def delete_position(
        self,
        portfolio_id: uuid.UUID,
        position_id: uuid.UUID,
    ) -> bool:
        stmt = sa.select(Position).where(
            Position.id == position_id,
            Position.portfolio_id == portfolio_id,
        )
        result = await self._session.execute(stmt)
        position = result.scalar_one_or_none()
        if position is None:
            return False
        await self._session.delete(position)
        await self._session.flush()
        await self._recalculate_weights(portfolio_id)
        return True

    async def delete_portfolio(
        self,
        portfolio_id: uuid.UUID,
        organization_id: uuid.UUID | None = None,
    ) -> bool:
        stmt = sa.select(Portfolio).where(Portfolio.id == portfolio_id)
        if organization_id is not None:
            stmt = stmt.where(Portfolio.organization_id == organization_id)
        result = await self._session.execute(stmt)
        portfolio = result.scalar_one_or_none()
        if portfolio is None:
            return False

        from database.models.execution import Execution

        exec_stmt = sa.select(sa.func.count(Execution.id)).where(Execution.portfolio_id == portfolio_id)
        exec_count = (await self._session.execute(exec_stmt)).scalar_one()
        if exec_count > 0:
            raise RuntimeError("Portfolio has active executions and cannot be deleted")

        await self._session.delete(portfolio)
        await self._session.flush()
        return True

    async def _recalculate_weights(self, portfolio_id: uuid.UUID) -> None:
        pos_stmt = sa.select(Position).where(Position.portfolio_id == portfolio_id)
        result = await self._session.execute(pos_stmt)
        positions = result.scalars().all()

        total_value = 0.0
        for pos in positions:
            if pos.current_price:
                price = float(pos.current_price)
            else:
                logger.warning(
                    "Position %s (%s) has no current_price, falling back to avg_cost_per_share",
                    pos.id,
                    pos.ticker_symbol,
                )
                price = float(pos.avg_cost_per_share)
            total_value += float(pos.quantity) * price

        for pos in positions:
            if total_value > 0:
                price = float(pos.current_price) if pos.current_price else float(pos.avg_cost_per_share)
                pos.weight_pct = Decimal(str((float(pos.quantity) * price) / total_value))
            else:
                pos.weight_pct = Decimal("0")

        await self._session.flush()

    @staticmethod
    def _to_dict(p: Portfolio) -> dict[str, Any]:
        return {
            "id": str(p.id),
            "name": p.name,
            "description": p.description,
            "is_paper_trading": p.is_paper_trading,
            "base_currency": p.base_currency,
            "organization_id": str(p.organization_id) if p.organization_id else None,
        }

    @staticmethod
    def _position_to_dict(p: Position) -> dict[str, Any]:
        return {
            "id": str(p.id),
            "ticker_symbol": p.ticker_symbol,
            "quantity": float(p.quantity) if p.quantity else None,
            "avg_cost_per_share": float(p.avg_cost_per_share) if p.avg_cost_per_share else None,
            "current_price": float(p.current_price) if p.current_price else None,
            "weight_pct": float(p.weight_pct) if p.weight_pct is not None else None,
        }
