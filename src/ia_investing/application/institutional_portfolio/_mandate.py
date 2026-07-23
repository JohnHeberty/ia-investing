from __future__ import annotations

from decimal import Decimal
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.portfolio_domain import StrategyMandate
from ia_investing.domain.identity import InstitutionalAccessContext, ResourceAttributes, authorize
from ia_investing.domain.institutional_portfolio import canonical_hash, validate_mandate

from ._base import audit


class MandateService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_mandate(
        self,
        payload: dict[str, object],
        context: InstitutionalAccessContext,
    ) -> StrategyMandate:
        authorize(context, "mandate:create", ResourceAttributes(context.organization_id))
        validate_mandate(
            min_cash_weight=Decimal(str(payload["min_cash_weight"])),
            max_cash_weight=Decimal(str(payload["max_cash_weight"])),
            max_turnover=Decimal(str(payload["max_turnover"])),
            max_drawdown=Decimal(str(payload["max_drawdown"])),
            benchmark_in_universe=bool(payload.get("benchmark_in_universe", False)),
        )
        content_hash = canonical_hash(payload)
        existing = (
            await self.session.execute(
                sa.select(StrategyMandate).where(
                    StrategyMandate.organization_id == context.organization_id,
                    StrategyMandate.logical_id == payload["logical_id"],
                    StrategyMandate.content_sha256 == content_hash,
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            return existing
        next_version = (
            await self.session.scalar(
                sa.select(sa.func.coalesce(sa.func.max(StrategyMandate.version), 0) + 1).where(
                    StrategyMandate.organization_id == context.organization_id,
                    StrategyMandate.logical_id == payload["logical_id"],
                )
            )
        ) or 1
        mandate = StrategyMandate(
            organization_id=context.organization_id,
            logical_id=str(payload["logical_id"]),
            version=next_version,
            objective=str(payload["objective"]),
            strategy_type=str(payload["strategy_type"]),
            universe_definition=dict(payload["universe_definition"]),  # type: ignore[call-overload]
            benchmark_index_id=UUID(str(payload["benchmark_index_id"])),
            base_currency=str(payload.get("base_currency", "BRL")),
            investment_horizon_days=int(str(payload["investment_horizon_days"])),
            rebalance_policy=dict(payload["rebalance_policy"]),  # type: ignore[call-overload]
            risk_budget=dict(payload["risk_budget"]),  # type: ignore[call-overload]
            target_volatility=Decimal(str(payload["target_volatility"])) if payload.get("target_volatility") else None,
            max_drawdown=Decimal(str(payload["max_drawdown"])),
            concentration_limits=dict(payload["concentration_limits"]),  # type: ignore[call-overload]
            factor_limits=dict(payload["factor_limits"]),  # type: ignore[call-overload]
            liquidity_policy=dict(payload["liquidity_policy"]),  # type: ignore[call-overload]
            min_cash_weight=Decimal(str(payload["min_cash_weight"])),
            max_cash_weight=Decimal(str(payload["max_cash_weight"])),
            max_turnover=Decimal(str(payload["max_turnover"])),
            exclusions=dict(payload["exclusions"]),  # type: ignore[call-overload]
            cost_policy=dict(payload["cost_policy"]),  # type: ignore[call-overload]
            tax_policy=dict(payload["tax_policy"]),  # type: ignore[call-overload]
            approval_policy=dict(payload["approval_policy"]),  # type: ignore[call-overload]
            content_sha256=content_hash,
            status="draft",
            created_by=context.subject,
        )
        self.session.add(mandate)
        await self.session.flush()
        audit(self.session, context, "mandate.create", "strategy_mandate", mandate.id, {"version": next_version})
        await self.session.flush()
        return mandate
