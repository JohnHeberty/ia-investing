from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

import cvxpy as cp
import polars as pl
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.instrument_master import Listing
from database.models.market_data import MarketBar
from database.models.portfolio_domain import ModelPortfolio, OptimizationRun, StrategyMandate
from ia_investing.domain.identity import InstitutionalAccessContext, ResourceAttributes, authorize
from ia_investing.domain.institutional_portfolio import canonical_hash, investable_universe
from portfolio import OptimizerConfig, PortfolioOptimizer


class PortfolioOptimizationService:
    async def optimize(
        self,
        *,
        returns_data: list[dict[str, Any]],
        current_weights: dict[str, float] | None,
        risk_aversion: float,
        max_weight: float,
        max_sector: float,
        max_turnover: float,
    ) -> dict[str, Any]:
        optimizer = PortfolioOptimizer(
            risk_aversion=risk_aversion,
            max_weight=max_weight,
            max_sector=max_sector,
            max_turnover=max_turnover,
        )
        result = await optimizer.optimize(pl.DataFrame(returns_data), current_weights)
        return {
            "status": result.status,
            "weights": result.weights,
            "expected_return": result.expected_return,
            "expected_risk": result.expected_risk,
            "sharpe_ratio": result.sharpe_ratio,
            "turnover": result.turnover,
            "transactions": result.transactions,
            "diagnostics": result.diagnostics,
            "slacks": result.slacks,
        }


class BackendPortfolioOptimizationService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def optimize(
        self,
        portfolio_id: UUID,
        as_of: datetime,
        context: InstitutionalAccessContext,
    ) -> OptimizationRun:
        portfolio = await self.session.get(ModelPortfolio, portfolio_id)
        if portfolio is None:
            raise LookupError("portfolio not found")
        authorize(context, "portfolio:optimize", ResourceAttributes(portfolio.organization_id, portfolio.owner_team_id))
        mandate = await self.session.get(StrategyMandate, portfolio.mandate_id)
        if mandate is None:
            raise RuntimeError("portfolio mandate is missing")
        raw_ids = mandate.universe_definition.get("instrument_ids", [])
        try:
            instrument_ids = tuple(UUID(str(value)) for value in raw_ids)  # type: ignore[attr-defined]
        except (TypeError, ValueError) as exc:
            raise ValueError("mandate universe contains invalid instrument IDs") from exc
        restricted = frozenset(str(UUID(str(value))) for value in mandate.exclusions.get("restricted", []))  # type: ignore[attr-defined]
        investable = tuple(
            UUID(item) for item in investable_universe(tuple(map(str, instrument_ids)), restricted=restricted)
        )

        price_rows = (
            await self.session.execute(
                sa.select(Listing.instrument_id, MarketBar.bar_at, MarketBar.close_price)
                .join(MarketBar, MarketBar.listing_id == Listing.id)
                .where(
                    Listing.instrument_id.in_(investable),
                    MarketBar.interval == "1d",
                    MarketBar.bar_at <= as_of,
                    MarketBar.knowledge_at <= as_of,
                )
                .order_by(MarketBar.bar_at)
            )
        ).all()
        prices: dict[UUID, dict[datetime, Decimal]] = {instrument_id: {} for instrument_id in investable}
        for instrument_id, bar_at, close_price in price_rows:
            prices[instrument_id][bar_at] = close_price
        common_dates = sorted(set.intersection(*(set(series) for series in prices.values())))
        if len(common_dates) < 3:
            raise ValueError("insufficient aligned point-in-time price history")
        returns_data: dict[str, list[float]] = {}
        for instrument_id, series in prices.items():
            values = [series[bar_at] for bar_at in common_dates]
            returns_data[str(instrument_id)] = [
                float(values[index] / values[index - 1] - 1) for index in range(1, len(values))
            ]

        max_weight = float(mandate.concentration_limits.get("position", "0.10"))  # type: ignore[arg-type]
        optimizer = PortfolioOptimizer(
            OptimizerConfig(
                max_weight=max_weight,
                max_turnover=float(mandate.max_turnover),
                min_cash_weight=float(mandate.min_cash_weight),
                max_cash_weight=float(mandate.max_cash_weight),
                timeout_seconds=30,
            )
        )
        input_payload = {
            "portfolio_id": portfolio.id,
            "as_of": as_of,
            "mandate_hash": mandate.content_sha256,
            "instrument_ids": investable,
            "price_dates": common_dates,
            "returns": returns_data,
        }
        input_sha256 = canonical_hash(input_payload)
        existing = (
            await self.session.execute(
                sa.select(OptimizationRun).where(
                    OptimizationRun.portfolio_id == portfolio.id,
                    OptimizationRun.as_of == as_of,
                    OptimizationRun.input_sha256 == input_sha256,
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            return existing
        result = await optimizer.optimize(pl.DataFrame(returns_data))
        run = OptimizationRun(
            portfolio_id=portfolio.id,
            as_of=as_of,
            input_sha256=input_sha256,
            solver="SCS",
            solver_version=cp.__version__,
            tolerances={"max_iters": 10_000, "epsilon": 1e-8, "timeout_seconds": 30},
            status=result.status,
            weights=result.weights,
            trades=result.transactions,
            slacks=result.slacks,
            diagnostics=result.diagnostics,
        )
        self.session.add(run)
        await self.session.flush()
        return run
