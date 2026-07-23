from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from database.models.paper_execution import (
    ChallengerEvaluation,
    OperationalAlert,
    PaperFill,
    PaperKillSwitch,
    PaperOrder,
    PaperPostMortem,
    ReconciliationBreak,
    TradeIntent,
)
from ia_investing.domain.identity import InstitutionalAccessContext

from ._alerts import AlertService
from ._dashboard import DashboardService
from ._evaluation import EvaluationService
from ._intent import IntentService
from ._order import OrderService
from ._reconciliation import ReconciliationService


class PaperExecutionService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self._intents = IntentService(session)
        self._orders = OrderService(session)
        self._reconciliation = ReconciliationService(session)
        self._alerts = AlertService(session)
        self._evaluation = EvaluationService(session)
        self._dashboard = DashboardService(session)

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
        return await self._intents.create_intent(
            portfolio_version_id=portfolio_version_id,
            instrument_id=instrument_id,
            idempotency_key=idempotency_key,
            side=side,
            quantity=quantity,
            order_type=order_type,
            limit_price=limit_price,
            earliest_execution_at=earliest_execution_at,
            expires_at=expires_at,
            reason=reason,
            context=context,
            correlation_id=correlation_id,
        )

    async def decide_intent(
        self,
        intent_id: UUID,
        *,
        approved: bool,
        rationale: str,
        context: InstitutionalAccessContext,
        correlation_id: UUID,
    ) -> TradeIntent:
        return await self._intents.decide_intent(
            intent_id, approved=approved, rationale=rationale, context=context, correlation_id=correlation_id
        )

    async def cancel_intent(
        self,
        intent_id: UUID,
        *,
        reason: str,
        context: InstitutionalAccessContext,
        correlation_id: UUID,
    ) -> TradeIntent:
        return await self._intents.cancel_intent(
            intent_id, reason=reason, context=context, correlation_id=correlation_id
        )

    async def simulate(
        self,
        intent_id: UUID,
        *,
        execution_model_version_id: UUID,
        seed: int,
        context: InstitutionalAccessContext,
        correlation_id: UUID,
    ) -> tuple[PaperOrder, tuple[PaperFill, ...]]:
        return await self._orders.simulate(
            intent_id,
            execution_model_version_id=execution_model_version_id,
            seed=seed,
            context=context,
            correlation_id=correlation_id,
        )

    async def reconcile_portfolio(
        self,
        portfolio_id: UUID,
        *,
        as_of: datetime,
        context: InstitutionalAccessContext,
        correlation_id: UUID,
    ) -> tuple[ReconciliationBreak, ...]:
        return await self._reconciliation.reconcile_portfolio(
            portfolio_id, as_of=as_of, context=context, correlation_id=correlation_id
        )

    async def resolve_break(
        self,
        break_id: UUID,
        *,
        resolution: dict[str, object],
        context: InstitutionalAccessContext,
        correlation_id: UUID,
    ) -> ReconciliationBreak:
        return await self._reconciliation.resolve_break(
            break_id, resolution=resolution, context=context, correlation_id=correlation_id
        )

    async def acknowledge_alert(
        self,
        alert_id: UUID,
        *,
        context: InstitutionalAccessContext,
        correlation_id: UUID,
    ) -> OperationalAlert:
        return await self._alerts.acknowledge_alert(alert_id, context=context, correlation_id=correlation_id)

    async def activate_kill_switch(
        self,
        *,
        portfolio_id: UUID | None,
        reason: str,
        context: InstitutionalAccessContext,
        correlation_id: UUID,
    ) -> PaperKillSwitch:
        return await self._alerts.activate_kill_switch(
            portfolio_id=portfolio_id, reason=reason, context=context, correlation_id=correlation_id
        )

    async def release_kill_switch(
        self,
        switch_id: UUID,
        *,
        context: InstitutionalAccessContext,
        correlation_id: UUID,
    ) -> PaperKillSwitch:
        return await self._alerts.release_kill_switch(switch_id, context=context, correlation_id=correlation_id)

    async def create_post_mortem(
        self,
        portfolio_id: UUID,
        *,
        period_start: datetime,
        period_end: datetime,
        expected: dict[str, object],
        realized: dict[str, object],
        attribution: dict[str, object],
        findings: list[dict[str, object]],
        dissent: list[dict[str, object]],
        context: InstitutionalAccessContext,
        correlation_id: UUID,
    ) -> PaperPostMortem:
        return await self._evaluation.create_post_mortem(
            portfolio_id,
            period_start=period_start,
            period_end=period_end,
            expected=expected,
            realized=realized,
            attribution=attribution,
            findings=findings,
            dissent=dissent,
            context=context,
            correlation_id=correlation_id,
        )

    async def create_challenger_evaluation(
        self,
        *,
        champion_portfolio_id: UUID,
        challenger_portfolio_id: UUID,
        window_start: datetime,
        window_end: datetime,
        methodology_version: str,
        comparison_config: dict[str, object],
        metrics: dict[str, object],
        evidence: dict[str, object],
        context: InstitutionalAccessContext,
        correlation_id: UUID,
    ) -> ChallengerEvaluation:
        return await self._evaluation.create_challenger_evaluation(
            champion_portfolio_id=champion_portfolio_id,
            challenger_portfolio_id=challenger_portfolio_id,
            window_start=window_start,
            window_end=window_end,
            methodology_version=methodology_version,
            comparison_config=comparison_config,
            metrics=metrics,
            evidence=evidence,
            context=context,
            correlation_id=correlation_id,
        )

    async def decide_challenger(
        self,
        evaluation_id: UUID,
        *,
        decision: str,
        context: InstitutionalAccessContext,
        correlation_id: UUID,
    ) -> ChallengerEvaluation:
        return await self._evaluation.decide_challenger(
            evaluation_id, decision=decision, context=context, correlation_id=correlation_id
        )

    async def list_trade_intents(self, organization_id: UUID) -> list[TradeIntent]:
        return await self._intents.list_trade_intents(organization_id)

    async def get_order_with_intent(
        self, order_id: UUID, organization_id: UUID
    ) -> tuple[PaperOrder, TradeIntent] | None:
        return await self._orders.get_order_with_intent(order_id, organization_id)

    async def list_fills_for_order(self, order_id: UUID) -> list[PaperFill]:
        return await self._orders.list_fills_for_order(order_id)

    async def resolve_alert(
        self,
        alert_id: UUID,
        *,
        resolution: dict[str, object],
        context: InstitutionalAccessContext,
        correlation_id: UUID,
    ) -> OperationalAlert:
        return await self._alerts.resolve_alert(
            alert_id, resolution=resolution, context=context, correlation_id=correlation_id
        )

    async def list_alerts(
        self,
        context: InstitutionalAccessContext,
        *,
        status: str | None = None,
        severity: str | None = None,
        alert_type: str | None = None,
        portfolio_id: UUID | None = None,
        limit: int = 50,
    ) -> list[OperationalAlert]:
        return await self._alerts.list_alerts(
            context, status=status, severity=severity, alert_type=alert_type, portfolio_id=portfolio_id, limit=limit
        )

    async def list_post_mortems(self, portfolio_id: UUID, *, limit: int = 50) -> list[PaperPostMortem]:
        return await self._evaluation.list_post_mortems(portfolio_id, limit=limit)

    async def list_challenger_evaluations(
        self,
        *,
        organization_id: UUID | None = None,
        portfolio_id: UUID | None = None,
        limit: int = 50,
    ) -> list[ChallengerEvaluation]:
        return await self._evaluation.list_challenger_evaluations(
            organization_id=organization_id, portfolio_id=portfolio_id, limit=limit
        )

    async def get_operational_dashboard(self, organization_id: UUID) -> dict[str, object]:
        return await self._dashboard.get_operational_dashboard(organization_id)
