from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.portfolio_domain import (
    CashSnapshot,
    InstitutionalPortfolioVersion,
    ModelPortfolio,
    PortfolioVersionThesis,
    PortfolioVersionValuation,
    PositionSnapshot,
    StrategyMandate,
)
from ia_investing.domain.identity import InstitutionalAccessContext, ResourceAttributes, authorize
from ia_investing.domain.institutional_portfolio import canonical_hash


class PortfolioVersionService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_version(
        self,
        *,
        portfolio_id: UUID,
        as_of: datetime,
        positions: tuple[tuple[UUID, Decimal, Decimal], ...],
        cash: tuple[tuple[str, Decimal], ...],
        proposal: dict[str, object],
        thesis_version_ids: tuple[UUID, ...],
        valuation_run_ids: tuple[UUID, ...],
        context: InstitutionalAccessContext,
    ) -> InstitutionalPortfolioVersion:
        portfolio = await self.session.get(ModelPortfolio, portfolio_id)
        if portfolio is None:
            raise LookupError("portfolio not found")
        authorize(context, "portfolio:propose", ResourceAttributes(portfolio.organization_id, portfolio.owner_team_id))
        mandate = await self.session.get(StrategyMandate, portfolio.mandate_id)
        if mandate is None:
            raise RuntimeError("portfolio references a missing mandate")
        if as_of.tzinfo is None:
            raise ValueError("as_of must be timezone-aware")
        if any(quantity < 0 or cost_basis < 0 for _, quantity, cost_basis in positions):
            raise ValueError("position quantity and cost basis must be nonnegative")
        if any(amount < 0 for _, amount in cash):
            raise ValueError("cash snapshots must be nonnegative")
        restricted = set(mandate.exclusions.get("restricted", []))  # type: ignore[call-overload]
        selected = {str(instrument_id) for instrument_id, _, _ in positions}
        if selected & restricted:
            raise ValueError(f"portfolio contains restricted instruments: {sorted(selected & restricted)}")
        next_version = (
            await self.session.scalar(
                sa.select(sa.func.coalesce(sa.func.max(InstitutionalPortfolioVersion.version), 0) + 1).where(
                    InstitutionalPortfolioVersion.portfolio_id == portfolio.id
                )
            )
        ) or 1
        snapshot_payload = {
            "as_of": as_of,
            "positions": positions,
            "cash": cash,
            "theses": thesis_version_ids,
            "valuations": valuation_run_ids,
        }
        approved_weights = dict(proposal.get("target_weights", {}))  # type: ignore[call-overload]
        version = InstitutionalPortfolioVersion(
            portfolio_id=portfolio.id,
            mandate_id=portfolio.mandate_id,
            version=next_version,
            as_of=as_of,
            input_snapshot_sha256=canonical_hash(snapshot_payload),
            weights_sha256=canonical_hash(approved_weights),
            approved_weights=approved_weights,
            proposal=proposal,
            status="proposed",
            created_by=context.subject,
        )
        self.session.add(version)
        await self.session.flush()
        for instrument_id, quantity, cost_basis in positions:
            self.session.add(
                PositionSnapshot(
                    portfolio_version_id=version.id,
                    instrument_id=instrument_id,
                    quantity=quantity,
                    cost_basis=cost_basis,
                    as_of=as_of,
                )
            )
        for currency, amount in cash:
            self.session.add(
                CashSnapshot(portfolio_version_id=version.id, currency=currency, amount=amount, as_of=as_of)
            )
        for thesis_version_id in thesis_version_ids:
            self.session.add(
                PortfolioVersionThesis(portfolio_version_id=version.id, thesis_version_id=thesis_version_id)
            )
        for valuation_run_id in valuation_run_ids:
            self.session.add(
                PortfolioVersionValuation(portfolio_version_id=version.id, valuation_run_id=valuation_run_id)
            )
        await self.session.flush()
        return version

    async def get_portfolio_version_with_portfolio(
        self, version_id: UUID, organization_id: UUID
    ) -> tuple[InstitutionalPortfolioVersion, ModelPortfolio] | None:
        version = await self.session.get(InstitutionalPortfolioVersion, version_id)
        if version is None:
            return None
        portfolio = await self.session.get(ModelPortfolio, version.portfolio_id)
        if portfolio is None or portfolio.organization_id != organization_id:
            return None
        return version, portfolio

    async def list_positions(self, version_id: UUID) -> list[PositionSnapshot]:
        return list(
            (
                await self.session.scalars(
                    sa.select(PositionSnapshot)
                    .where(PositionSnapshot.portfolio_version_id == version_id)
                    .order_by(PositionSnapshot.instrument_id)
                )
            ).all()
        )
