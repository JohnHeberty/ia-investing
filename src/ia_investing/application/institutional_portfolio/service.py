from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from database.models.portfolio_domain import (
    InstitutionalPortfolioVersion,
    InstitutionalRiskSnapshot,
    ModelPortfolio,
    NavPublication,
    PositionSnapshot,
    RiskBreach,
    RiskWaiver,
    StrategyMandate,
)
from ia_investing.domain.identity import InstitutionalAccessContext

from ._approval import ApprovalService
from ._mandate import MandateService
from ._nav import NavService
from ._portfolio import PortfolioLifecycleService
from ._risk import RiskService
from ._version import PortfolioVersionService


class InstitutionalPortfolioService:
    def __init__(self, session: AsyncSession) -> None:
        self._mandate = MandateService(session)
        self._portfolio = PortfolioLifecycleService(session)
        self._version = PortfolioVersionService(session)
        self._approval = ApprovalService(session)
        self._nav = NavService(session)
        self._risk = RiskService(session)

    async def create_mandate(
        self,
        payload: dict[str, object],
        context: InstitutionalAccessContext,
    ) -> StrategyMandate:
        return await self._mandate.create_mandate(payload, context)

    async def create_portfolio(
        self,
        *,
        mandate_id: UUID,
        owner_team_id: UUID,
        name: str,
        context: InstitutionalAccessContext,
    ) -> ModelPortfolio:
        return await self._portfolio.create_portfolio(
            mandate_id=mandate_id, owner_team_id=owner_team_id, name=name, context=context
        )

    async def transition(
        self,
        portfolio_id: UUID,
        target: str,
        expected_version: int,
        reason: str,
        context: InstitutionalAccessContext,
    ) -> ModelPortfolio:
        return await self._portfolio.transition(portfolio_id, target, expected_version, reason, context)

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
        return await self._version.create_version(
            portfolio_id=portfolio_id,
            as_of=as_of,
            positions=positions,
            cash=cash,
            proposal=proposal,
            thesis_version_ids=thesis_version_ids,
            valuation_run_ids=valuation_run_ids,
            context=context,
        )

    async def approve_version(
        self,
        version_id: UUID,
        optimization_run_id: UUID,
        risk_snapshot_id: UUID,
        decision: dict[str, object],
        context: InstitutionalAccessContext,
    ) -> InstitutionalPortfolioVersion:
        return await self._approval.approve_version(
            version_id, optimization_run_id, risk_snapshot_id, decision, context
        )

    async def publish_nav(
        self,
        version_id: UUID,
        as_of: datetime,
        context: InstitutionalAccessContext,
    ) -> NavPublication:
        return await self._nav.publish_nav(version_id, as_of, context)

    async def assess_risk(
        self,
        version_id: UUID,
        policy_id: UUID,
        as_of: datetime,
        context: InstitutionalAccessContext,
    ) -> tuple[InstitutionalRiskSnapshot, tuple[RiskBreach, ...]]:
        return await self._risk.assess_risk(version_id, policy_id, as_of, context)

    async def waive_breach(
        self,
        breach_id: UUID,
        reason: str,
        expires_at: datetime,
        context: InstitutionalAccessContext,
    ) -> RiskWaiver:
        return await self._risk.waive_breach(breach_id, reason, expires_at, context)

    async def get_portfolio(self, portfolio_id: UUID, organization_id: UUID) -> ModelPortfolio | None:
        return await self._portfolio.get_portfolio(portfolio_id, organization_id)

    async def list_model_portfolios(
        self,
        organization_id: UUID,
        *,
        limit: int = 50,
        after: UUID | None = None,
        state: str | None = None,
    ) -> tuple[list[ModelPortfolio], bool]:
        return await self._portfolio.list_model_portfolios(organization_id, limit=limit, after=after, state=state)

    async def get_portfolio_version_with_portfolio(
        self, version_id: UUID, organization_id: UUID
    ) -> tuple[InstitutionalPortfolioVersion, ModelPortfolio] | None:
        return await self._version.get_portfolio_version_with_portfolio(version_id, organization_id)

    async def list_positions(self, version_id: UUID) -> list[PositionSnapshot]:
        return await self._version.list_positions(version_id)

    async def list_nav_publications(self, portfolio_id: UUID, *, as_of: datetime | None = None) -> list[NavPublication]:
        return await self._nav.list_nav_publications(portfolio_id, as_of=as_of)

    async def list_risk_breaches(
        self, snapshot_id: UUID, organization_id: UUID
    ) -> tuple[InstitutionalRiskSnapshot, list[RiskBreach]] | None:
        return await self._risk.list_risk_breaches(snapshot_id, organization_id)

    async def expire_waivers(self, now: datetime) -> int:
        return await self._risk.expire_waivers(now)
