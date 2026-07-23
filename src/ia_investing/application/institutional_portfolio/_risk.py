from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.instrument_master import Listing
from database.models.market_data import MarketBar
from database.models.portfolio_domain import (
    CashSnapshot,
    InstitutionalPortfolioVersion,
    InstitutionalRiskPolicy,
    InstitutionalRiskSnapshot,
    ModelPortfolio,
    NavPublication,
    PositionSnapshot,
    RiskBreach,
    RiskWaiver,
)
from ia_investing.domain.identity import InstitutionalAccessContext, ResourceAttributes, authorize
from ia_investing.domain.institutional_portfolio import (
    RiskLimitInput,
    calculate_portfolio_risk,
    canonical_hash,
    evaluate_risk_limits,
)

from ._base import audit


class RiskService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def assess_risk(
        self,
        version_id: UUID,
        policy_id: UUID,
        as_of: datetime,
        context: InstitutionalAccessContext,
    ) -> tuple[InstitutionalRiskSnapshot, tuple[RiskBreach, ...]]:
        version = await self.session.get(InstitutionalPortfolioVersion, version_id)
        policy = await self.session.get(InstitutionalRiskPolicy, policy_id)
        if version is None or policy is None or version.mandate_id != policy.mandate_id:
            raise LookupError("portfolio version or risk policy not found")
        portfolio = await self.session.get(ModelPortfolio, version.portfolio_id)
        if portfolio is None:
            raise RuntimeError("portfolio missing")
        authorize(context, "risk:assess", ResourceAttributes(portfolio.organization_id, portfolio.owner_team_id))
        if as_of.tzinfo is None:
            raise ValueError("risk cutoff must include timezone information")
        position_rows = list(
            (
                await self.session.scalars(
                    sa.select(PositionSnapshot).where(PositionSnapshot.portfolio_version_id == version.id)
                )
            ).all()
        )
        position_values: dict[str, Decimal] = {}
        average_daily_values: dict[str, Decimal] = {}
        return_series: dict[str, list[Decimal]] = {}
        max_price_age_hours = Decimal(str(policy.limits.get("max_price_age_hours", 72)))
        if max_price_age_hours <= 0:
            raise ValueError("risk policy max_price_age_hours must be positive")
        for position in position_rows:
            bars = list(
                (
                    await self.session.scalars(
                        sa.select(MarketBar)
                        .join(Listing, Listing.id == MarketBar.listing_id)
                        .where(
                            Listing.instrument_id == position.instrument_id,
                            Listing.valid_from <= as_of.date(),
                            sa.or_(Listing.valid_to.is_(None), Listing.valid_to > as_of.date()),
                            MarketBar.bar_at <= as_of,
                            MarketBar.knowledge_at <= as_of,
                        )
                        .order_by(MarketBar.bar_at.desc(), MarketBar.knowledge_at.desc())
                        .limit(253)
                    )
                ).all()
            )
            latest_by_bar: dict[datetime, MarketBar] = {}
            for bar in bars:
                latest_by_bar.setdefault(bar.bar_at, bar)
            bars = sorted(latest_by_bar.values(), key=lambda item: item.bar_at)
            if len(bars) < 2:
                raise ValueError(f"risk history is missing for instrument {position.instrument_id}")
            price_age_hours = Decimal(str((as_of - bars[-1].bar_at).total_seconds())) / Decimal(3600)
            if price_age_hours > max_price_age_hours:
                raise ValueError(f"risk price is stale for instrument {position.instrument_id}")
            instrument_key = str(position.instrument_id)
            position_values[instrument_key] = position.quantity * bars[-1].close_price
            average_daily_values[instrument_key] = sum(
                (bar.close_price * Decimal(bar.volume) for bar in bars), start=Decimal(0)
            ) / Decimal(len(bars))
            return_series[instrument_key] = [
                bars[index].close_price / bars[index - 1].close_price - Decimal(1)
                for index in range(1, len(bars))
                if bars[index - 1].close_price > 0
            ]
        cash_value = (
            await self.session.scalar(
                sa.select(sa.func.coalesce(sa.func.sum(CashSnapshot.amount), 0)).where(
                    CashSnapshot.portfolio_version_id == version.id
                )
            )
        ) or Decimal(0)
        nav_value = cash_value + sum(position_values.values(), start=Decimal(0))
        weights = {key: value / nav_value for key, value in position_values.items()} if nav_value > 0 else {}
        common_length = min((len(values) for values in return_series.values()), default=0)
        portfolio_returns = tuple(
            sum(
                (weights[key] * values[-common_length + index] for key, values in return_series.items()),
                start=Decimal(0),
            )
            for index in range(common_length)
        )
        nav_history = tuple(
            (
                await self.session.scalars(
                    sa.select(NavPublication.nav)
                    .where(NavPublication.portfolio_id == portfolio.id, NavPublication.as_of <= as_of)
                    .order_by(NavPublication.as_of, NavPublication.revision)
                )
            ).all()
        )
        raw_factor_loadings = policy.limits.get("factor_loadings", {})
        factor_loadings = {
            str(instrument): {str(factor): Decimal(str(value)) for factor, value in values.items()}
            for instrument, values in raw_factor_loadings.items()
            if isinstance(values, dict)
        }
        metrics = calculate_portfolio_risk(
            position_values=position_values,
            cash_value=cash_value,
            average_daily_values=average_daily_values,
            factor_loadings=factor_loadings,
            portfolio_returns=portfolio_returns,
            nav_history=nav_history,
        )
        raw_limits = policy.limits.get("limits", [])
        limits = tuple(
            RiskLimitInput(str(item["name"]), str(item["type"]), Decimal(str(item["maximum"])))
            for item in raw_limits
            if isinstance(item, dict)
        )
        evaluated = evaluate_risk_limits(metrics.observations, limits)
        snapshot = InstitutionalRiskSnapshot(
            portfolio_version_id=version.id,
            risk_policy_id=policy.id,
            as_of=as_of,
            input_sha256=canonical_hash({"metrics": metrics.input_sha256, "policy": policy.content_sha256}),
            exposures={key: str(value) for key, value in metrics.factor_exposures.items()},
            concentration={key: str(value) for key, value in metrics.concentration.items()},
            liquidity={key: str(value) for key, value in metrics.liquidity.items()},
            volatility=metrics.volatility,
            drawdown=metrics.drawdown,
        )
        self.session.add(snapshot)
        await self.session.flush()
        breaches = tuple(
            RiskBreach(
                risk_snapshot_id=snapshot.id,
                limit_name=item.name,
                limit_type=item.limit_type,
                observed_value=item.observed,
                limit_value=item.maximum,
                status="open",
            )
            for item in evaluated
        )
        self.session.add_all(breaches)
        await self.session.flush()
        return snapshot, breaches

    async def waive_breach(
        self,
        breach_id: UUID,
        reason: str,
        expires_at: datetime,
        context: InstitutionalAccessContext,
    ) -> RiskWaiver:
        breach = await self.session.get(RiskBreach, breach_id, with_for_update=True)
        if breach is None:
            raise LookupError("risk breach not found")
        snapshot = await self.session.get(InstitutionalRiskSnapshot, breach.risk_snapshot_id)
        version = (
            await self.session.get(InstitutionalPortfolioVersion, snapshot.portfolio_version_id)
            if snapshot is not None
            else None
        )
        portfolio = await self.session.get(ModelPortfolio, version.portfolio_id) if version is not None else None
        if portfolio is None:
            raise RuntimeError("risk breach references a missing portfolio")
        authorize(context, "risk:waive", ResourceAttributes(portfolio.organization_id, portfolio.owner_team_id))
        if breach.status != "open":
            raise ValueError("only an open breach can be waived")
        if not reason.strip():
            raise ValueError("waiver reason is required")
        if expires_at.tzinfo is None or expires_at <= datetime.now(UTC):
            raise ValueError("waiver expiry must be an aware future timestamp")
        waiver = RiskWaiver(breach_id=breach.id, granted_by=context.subject, reason=reason, expires_at=expires_at)
        breach.status = "waived"
        self.session.add(waiver)
        await self.session.flush()
        audit(
            self.session,
            context,
            "risk_breach.waive",
            "risk_breach",
            breach.id,
            {"reason": reason, "expires_at": expires_at.isoformat(), "waiver_id": str(waiver.id)},
        )
        await self.session.flush()
        return waiver

    async def list_risk_breaches(
        self, snapshot_id: UUID, organization_id: UUID
    ) -> tuple[InstitutionalRiskSnapshot, list[RiskBreach]] | None:
        snapshot = await self.session.get(InstitutionalRiskSnapshot, snapshot_id)
        if snapshot is None:
            return None
        version = await self.session.get(InstitutionalPortfolioVersion, snapshot.portfolio_version_id)
        if version is None:
            return None
        portfolio = await self.session.get(ModelPortfolio, version.portfolio_id)
        if portfolio is None or portfolio.organization_id != organization_id:
            return None
        rows = list(
            (
                await self.session.scalars(
                    sa.select(RiskBreach).where(RiskBreach.risk_snapshot_id == snapshot_id).order_by(RiskBreach.id)
                )
            ).all()
        )
        return snapshot, rows

    async def expire_waivers(self, now: datetime) -> int:
        if now.tzinfo is None:
            raise ValueError("waiver expiry cutoff must be timezone-aware")
        breach_ids = sa.select(RiskWaiver.breach_id).where(RiskWaiver.expires_at <= now)
        result = await self.session.execute(
            sa.update(RiskBreach)
            .where(RiskBreach.id.in_(breach_ids), RiskBreach.status == "waived")
            .values(status="open")
        )
        return int(result.rowcount)
