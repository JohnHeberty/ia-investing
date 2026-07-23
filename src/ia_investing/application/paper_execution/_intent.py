from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.paper_execution import PaperOrder, TradeIntent
from database.models.portfolio_domain import InstitutionalPortfolioVersion, ModelPortfolio, StrategyMandate
from ia_investing.domain.identity import InstitutionalAccessContext, ResourceAttributes, authorize, ensure_four_eyes
from ia_investing.domain.paper_execution import INTENT_TRANSITIONS, ORDER_TRANSITIONS, validate_transition

from ._base import audit_entity, record, record_order, require_operations_enabled


class IntentService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_intent(
        self,
        *,
        portfolio_version_id: UUID,
        instrument_id: UUID,
        idempotency_key: str,
        side: str,
        quantity: Decimal,
        order_type: str,
        limit_price: Decimal | None,
        earliest_execution_at: datetime,
        expires_at: datetime,
        reason: str,
        context: InstitutionalAccessContext,
        correlation_id: UUID,
    ) -> tuple[TradeIntent, bool]:
        version = await self.session.get(InstitutionalPortfolioVersion, portfolio_version_id)
        if version is None or version.status != "approved":
            raise ValueError("paper intent requires an approved portfolio version")
        portfolio = await self.session.get(ModelPortfolio, version.portfolio_id)
        if portfolio is None:
            raise LookupError("portfolio not found")
        authorize(
            context,
            "portfolio:propose",
            ResourceAttributes(portfolio.organization_id, portfolio.owner_team_id, portfolio.environment),
        )
        if earliest_execution_at.tzinfo is None or expires_at.tzinfo is None:
            raise ValueError("execution window must include timezone information")
        if earliest_execution_at < version.as_of:
            raise ValueError("execution cannot precede the approved portfolio snapshot")
        mandate = await self.session.get(StrategyMandate, portfolio.mandate_id)
        if mandate is None:
            raise LookupError("mandate not found")
        instrument_ids = {str(item) for item in mandate.universe_definition.get("instrument_ids", [])}
        if instrument_ids and str(instrument_id) not in instrument_ids:
            raise ValueError("instrument is outside the mandate universe")
        await require_operations_enabled(self.session, portfolio)
        existing = (
            await self.session.execute(
                sa.select(TradeIntent).where(
                    TradeIntent.organization_id == context.organization_id,
                    TradeIntent.idempotency_key == idempotency_key,
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            expected = (portfolio_version_id, instrument_id, side, quantity, order_type, limit_price)
            actual = (
                existing.portfolio_version_id,
                existing.instrument_id,
                existing.side,
                existing.quantity,
                existing.order_type,
                existing.limit_price,
            )
            if actual != expected:
                raise ValueError("idempotency key was used with a different paper intent")
            return existing, False
        intent = TradeIntent(
            organization_id=context.organization_id,
            portfolio_id=portfolio.id,
            portfolio_version_id=version.id,
            instrument_id=instrument_id,
            idempotency_key=idempotency_key,
            side=side,
            quantity=quantity,
            order_type=order_type,
            limit_price=limit_price,
            earliest_execution_at=earliest_execution_at,
            expires_at=expires_at,
            reason=reason,
            status="pending_approval",
            environment="paper",
            created_by=context.subject,
        )
        self.session.add(intent)
        await self.session.flush()
        record(self.session, intent, "TradeIntentCreated", "paper_trade_intent.create", context.subject, correlation_id)
        return intent, True

    async def decide_intent(
        self,
        intent_id: UUID,
        *,
        approved: bool,
        rationale: str,
        context: InstitutionalAccessContext,
        correlation_id: UUID,
    ) -> TradeIntent:
        intent = await self.session.get(TradeIntent, intent_id, with_for_update=True)
        if intent is None or intent.organization_id != context.organization_id:
            raise LookupError("paper trade intent not found")
        authorize(context, "portfolio:approve", ResourceAttributes(intent.organization_id))
        ensure_four_eyes(intent.created_by, context.subject)
        target = "approved" if approved else "cancelled"
        validate_transition(intent.status, target, INTENT_TRANSITIONS)
        intent.status = target
        intent.approval_decision = {
            "approved": approved,
            "rationale": rationale,
            "decided_at": datetime.now(UTC).isoformat(),
        }
        intent.approved_by = context.subject if approved else None
        intent.updated_at = datetime.now(UTC)
        event = "TradeIntentApproved" if approved else "TradeIntentRejected"
        record(self.session, intent, event, "paper_trade_intent.decide", context.subject, correlation_id)
        return intent

    async def cancel_intent(
        self,
        intent_id: UUID,
        *,
        reason: str,
        context: InstitutionalAccessContext,
        correlation_id: UUID,
    ) -> TradeIntent:
        intent = await self.session.get(TradeIntent, intent_id, with_for_update=True)
        if intent is None or intent.organization_id != context.organization_id:
            raise LookupError("paper trade intent not found")
        authorize(context, "paper_orders:operate", ResourceAttributes(intent.organization_id))
        validate_transition(intent.status, "cancelled", INTENT_TRANSITIONS)
        order = await self.session.scalar(
            sa.select(PaperOrder).where(PaperOrder.trade_intent_id == intent.id).with_for_update()
        )
        if order is not None and order.status not in {"cancelled", "rejected", "expired", "filled"}:
            validate_transition(order.status, "cancelled", ORDER_TRANSITIONS)
            order.status = "cancelled"
            order.completed_at = datetime.now(UTC)
        intent.status = "cancelled"
        intent.updated_at = datetime.now(UTC)
        record(
            self.session,
            intent,
            "PaperTradeIntentCancelled",
            "paper_trade_intent.cancel",
            context.subject,
            correlation_id,
        )
        audit_entity(
            self.session,
            "paper_trade_intent.cancel.reason",
            "paper_trade_intent",
            intent.id,
            context.subject,
            context.organization_id,
            correlation_id,
            {"reason": reason},
        )
        if order is not None:
            record_order(
                self.session,
                order,
                "PaperOrderCancelled",
                "paper_order.cancel",
                context.subject,
                context.organization_id,
                correlation_id,
            )
        return intent

    async def list_trade_intents(self, organization_id: UUID) -> list[TradeIntent]:
        return list(
            (
                await self.session.scalars(
                    sa.select(TradeIntent)
                    .where(TradeIntent.organization_id == organization_id)
                    .order_by(TradeIntent.created_at.desc())
                )
            ).all()
        )
