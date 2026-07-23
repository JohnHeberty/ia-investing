from __future__ import annotations

from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.portfolio_domain import ModelPortfolio, StrategyMandate
from ia_investing.domain.identity import InstitutionalAccessContext, ResourceAttributes, authorize
from ia_investing.domain.institutional_portfolio import validate_portfolio_transition

from ._base import PortfolioConcurrencyError, audit


class PortfolioLifecycleService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_portfolio(
        self,
        *,
        mandate_id: UUID,
        owner_team_id: UUID,
        name: str,
        context: InstitutionalAccessContext,
    ) -> ModelPortfolio:
        authorize(context, "portfolio:create", ResourceAttributes(context.organization_id, owner_team_id))
        mandate = await self.session.get(StrategyMandate, mandate_id)
        if mandate is None or mandate.organization_id != context.organization_id:
            raise LookupError("mandate not found in organization")
        portfolio = ModelPortfolio(
            organization_id=context.organization_id,
            owner_team_id=owner_team_id,
            mandate_id=mandate.id,
            name=name,
            base_currency=mandate.base_currency,
            state="draft",
            environment="paper",
            created_by=context.subject,
        )
        self.session.add(portfolio)
        await self.session.flush()
        audit(
            self.session,
            context,
            "portfolio.create",
            "model_portfolio",
            portfolio.id,
            {"mandate_id": str(mandate.id)},
        )
        await self.session.flush()
        return portfolio

    async def transition(
        self,
        portfolio_id: UUID,
        target: str,
        expected_version: int,
        reason: str,
        context: InstitutionalAccessContext,
    ) -> ModelPortfolio:
        portfolio = await self.session.get(ModelPortfolio, portfolio_id, with_for_update=True)
        if portfolio is None:
            raise LookupError("portfolio not found")
        authorize(
            context,
            "portfolio:transition",
            ResourceAttributes(
                portfolio.organization_id, portfolio.owner_team_id, portfolio.environment, portfolio.state
            ),
        )
        if portfolio.lock_version != expected_version:
            raise PortfolioConcurrencyError("portfolio version does not match If-Match")
        validate_portfolio_transition(portfolio.state, target)
        before = portfolio.state
        portfolio.state = target
        portfolio.lock_version += 1
        audit(
            self.session,
            context,
            "portfolio.transition",
            "model_portfolio",
            portfolio.id,
            {"from": before, "to": target, "reason": reason},
        )
        await self.session.flush()
        return portfolio

    async def get_portfolio(self, portfolio_id: UUID, organization_id: UUID) -> ModelPortfolio | None:
        portfolio = await self.session.get(ModelPortfolio, portfolio_id)
        if portfolio is None or portfolio.organization_id != organization_id:
            return None
        return portfolio

    async def list_model_portfolios(
        self,
        organization_id: UUID,
        *,
        limit: int = 50,
        after: UUID | None = None,
        state: str | None = None,
    ) -> tuple[list[ModelPortfolio], bool]:
        stmt = (
            sa.select(ModelPortfolio)
            .where(ModelPortfolio.organization_id == organization_id)
            .order_by(ModelPortfolio.id)
            .limit(limit + 1)
        )
        if after is not None:
            stmt = stmt.where(ModelPortfolio.id > after)
        if state is not None:
            stmt = stmt.where(ModelPortfolio.state == state)
        rows = list((await self.session.scalars(stmt)).all())
        has_more = len(rows) > limit
        if has_more:
            rows = rows[:limit]
        return rows, has_more
