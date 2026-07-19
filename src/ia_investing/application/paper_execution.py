from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.agents import AuditLog
from database.models.instrument_master import Listing
from database.models.market_data import MarketBar, TradingSession
from database.models.paper_execution import (
    ChallengerEvaluation,
    ExecutionModelVersion,
    OperationalAlert,
    PaperFill,
    PaperKillSwitch,
    PaperOrder,
    PaperPostMortem,
    ReconciliationBreak,
    TradeIntent,
)
from database.models.portfolio_domain import (
    InstitutionalPortfolioVersion,
    ModelPortfolio,
    PortfolioLedgerEntry,
    StrategyMandate,
)
from database.models.research import DomainOutboxEvent
from ia_investing.domain.identity import InstitutionalAccessContext, ResourceAttributes, authorize, ensure_four_eyes
from ia_investing.domain.paper_execution import (
    INTENT_TRANSITIONS,
    ORDER_TRANSITIONS,
    ExecutionConfiguration,
    MarketSnapshot,
    ReconciliationFill,
    ReconciliationLedgerEntry,
    ReconciliationOrder,
    TradingWindow,
    fill_to_ledger,
    immutable_report_hash,
    reconcile_execution,
    simulate_order,
    validate_challenger_comparison,
    validate_paper_order_request,
    validate_post_mortem_lineage,
    validate_transition,
)


class PaperExecutionService:
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
        await self._require_operations_enabled(portfolio)
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
        self._record(intent, "TradeIntentCreated", "paper_trade_intent.create", context.subject, correlation_id)
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
        self._record(intent, event, "paper_trade_intent.decide", context.subject, correlation_id)
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
        self._record(intent, "PaperTradeIntentCancelled", "paper_trade_intent.cancel", context.subject, correlation_id)
        self._audit_entity(
            "paper_trade_intent.cancel.reason",
            "paper_trade_intent",
            intent.id,
            context.subject,
            context.organization_id,
            correlation_id,
            {"reason": reason},
        )
        return intent

    async def simulate(
        self,
        intent_id: UUID,
        *,
        execution_model_version_id: UUID,
        seed: int,
        context: InstitutionalAccessContext,
        correlation_id: UUID,
    ) -> tuple[PaperOrder, tuple[PaperFill, ...]]:
        intent = await self.session.get(TradeIntent, intent_id, with_for_update=True)
        if intent is None or intent.organization_id != context.organization_id:
            raise LookupError("paper trade intent not found")
        authorize(context, "paper_orders:operate", ResourceAttributes(intent.organization_id))
        if intent.status != "approved" or not intent.approved_by:
            raise ValueError("only an approved paper intent can be simulated")
        portfolio = await self.session.get(ModelPortfolio, intent.portfolio_id)
        if portfolio is None:
            raise LookupError("portfolio not found")
        await self._require_operations_enabled(portfolio)
        model = await self.session.get(ExecutionModelVersion, execution_model_version_id)
        if model is None or model.organization_id != context.organization_id or model.status != "approved":
            raise ValueError("an approved execution model version is required")
        submit_key = f"paper-intent:{intent.id}:model:{model.id}"
        existing = (
            await self.session.execute(sa.select(PaperOrder).where(PaperOrder.submit_key == submit_key))
        ).scalar_one_or_none()
        if existing is not None:
            fills = tuple(
                (
                    await self.session.scalars(
                        sa.select(PaperFill).where(PaperFill.order_id == existing.id).order_by(PaperFill.sequence)
                    )
                ).all()
            )
            return existing, fills
        configuration = self._configuration(model)
        approved_at = datetime.fromisoformat(str(intent.approval_decision["decided_at"]))
        calendar_rows = list(
            (
                await self.session.scalars(
                    sa.select(TradingSession)
                    .where(
                        TradingSession.market_code == "B3",
                        TradingSession.session_date >= intent.earliest_execution_at.date(),
                        TradingSession.session_date <= intent.expires_at.date(),
                        TradingSession.is_open.is_(True),
                        TradingSession.knowledge_at <= approved_at,
                    )
                    .order_by(TradingSession.session_date, TradingSession.knowledge_at.desc())
                )
            ).all()
        )
        latest_sessions: dict[object, TradingSession] = {}
        for market_session in calendar_rows:
            latest_sessions.setdefault(market_session.session_date, market_session)
        windows = tuple(
            TradingWindow(
                datetime.combine(item.session_date, item.opens_at),
                datetime.combine(item.session_date, item.closes_at),
            )
            for item in latest_sessions.values()
            if item.opens_at is not None and item.closes_at is not None
        )
        validate_paper_order_request(
            order_type=intent.order_type,
            limit_price=intent.limit_price,
            quantity=intent.quantity,
            lot_size=configuration.lot_size,
            earliest_execution_at=intent.earliest_execution_at,
            expires_at=intent.expires_at,
            trading_windows=windows,
        )
        bars = (
            (
                await self.session.execute(
                    sa.select(MarketBar)
                    .join(Listing, Listing.id == MarketBar.listing_id)
                    .where(
                        Listing.instrument_id == intent.instrument_id,
                        Listing.valid_from <= MarketBar.bar_at.cast(sa.Date),
                        sa.or_(Listing.valid_to.is_(None), Listing.valid_to > MarketBar.bar_at.cast(sa.Date)),
                        MarketBar.bar_at >= intent.earliest_execution_at,
                        MarketBar.bar_at <= intent.expires_at,
                        MarketBar.knowledge_at <= MarketBar.bar_at,
                    )
                    .order_by(MarketBar.bar_at, MarketBar.knowledge_at)
                )
            )
            .scalars()
            .all()
        )
        snapshots = tuple(
            MarketSnapshot(bar.bar_at, bar.close_price, Decimal(bar.volume), True)
            for bar in bars
            if any(window.opens_at <= bar.bar_at <= window.closes_at for window in windows)
        )
        result = simulate_order(
            side=intent.side,
            quantity=intent.quantity,
            signal_at=intent.earliest_execution_at,
            approved_at=approved_at,
            expires_at=intent.expires_at,
            snapshots=snapshots,
            configuration=configuration,
            seed=seed,
            limit_price=intent.limit_price,
        )
        order = PaperOrder(
            trade_intent_id=intent.id,
            execution_model_version_id=model.id,
            submit_key=submit_key,
            status=result.status,
            requested_quantity=intent.quantity,
            filled_quantity=intent.quantity - result.unfilled_quantity,
            input_snapshot={"bar_ids": [str(bar.id) for bar in bars], "configuration": model.configuration},
            input_sha256=result.input_sha256,
            seed=seed,
            environment="paper",
            accepted_at=approved_at,
            completed_at=datetime.now(UTC) if result.status in {"filled", "expired"} else None,
        )
        self.session.add(order)
        await self.session.flush()
        fills: list[PaperFill] = []
        for simulated in result.fills:
            fill = PaperFill(
                order_id=order.id,
                event_key=f"{order.id}:fill:{simulated.sequence}",
                sequence=simulated.sequence,
                quantity=simulated.quantity,
                price=simulated.price,
                gross_value=simulated.gross_value,
                fee_value=simulated.fee_value,
                tax_value=simulated.tax_value,
                slippage_bps=simulated.slippage_bps,
                market_timestamp=simulated.market_timestamp,
                filled_at=simulated.market_timestamp + timedelta(milliseconds=configuration.latency_ms),
                environment="paper",
            )
            self.session.add(fill)
            fills.append(fill)
            delta = fill_to_ledger(intent.side, simulated)
            self.session.add(
                PortfolioLedgerEntry(
                    portfolio_id=intent.portfolio_id,
                    instrument_id=intent.instrument_id,
                    entry_type="trade",
                    currency=portfolio.base_currency,
                    amount=delta.cash_delta,
                    quantity=delta.instrument_quantity,
                    occurred_at=fill.filled_at,
                    source_reference=f"paper-fill:{fill.event_key}",
                )
            )
        intent.status = "completed" if result.status == "filled" else "submitted" if fills else "expired"
        intent.updated_at = datetime.now(UTC)
        self._record(intent, "PaperOrderSimulated", "paper_order.simulate", context.subject, correlation_id)
        return order, tuple(fills)

    async def reconcile_portfolio(
        self,
        portfolio_id: UUID,
        *,
        as_of: datetime,
        context: InstitutionalAccessContext,
        correlation_id: UUID,
    ) -> tuple[ReconciliationBreak, ...]:
        if "reconciliation:write" not in context.permissions:
            raise PermissionError("permission required: reconciliation:write")
        if as_of.tzinfo is None:
            raise ValueError("reconciliation cutoff must include timezone information")
        portfolio = await self.session.get(ModelPortfolio, portfolio_id)
        if portfolio is None or portfolio.organization_id != context.organization_id:
            raise LookupError("portfolio not found")
        order_rows = (
            await self.session.execute(
                sa.select(PaperOrder, TradeIntent)
                .join(TradeIntent, TradeIntent.id == PaperOrder.trade_intent_id)
                .where(TradeIntent.portfolio_id == portfolio.id, PaperOrder.created_at <= as_of)
            )
        ).all()
        order_ids = [order.id for order, _intent in order_rows]
        fills = []
        if order_ids:
            fills = list(
                (
                    await self.session.scalars(
                        sa.select(PaperFill).where(PaperFill.order_id.in_(order_ids), PaperFill.filled_at <= as_of)
                    )
                ).all()
            )
        ledger = list(
            (
                await self.session.scalars(
                    sa.select(PortfolioLedgerEntry).where(
                        PortfolioLedgerEntry.portfolio_id == portfolio.id,
                        PortfolioLedgerEntry.occurred_at <= as_of,
                        PortfolioLedgerEntry.source_reference.like("paper-fill:%"),
                    )
                )
            ).all()
        )
        side_by_order = {str(order.id): intent.side for order, intent in order_rows}
        detected = reconcile_execution(
            tuple(
                ReconciliationOrder(str(order.id), order.requested_quantity, order.filled_quantity, order.status)
                for order, _intent in order_rows
            ),
            tuple(
                ReconciliationFill(
                    str(fill.order_id),
                    fill.event_key,
                    fill.quantity,
                    fill.gross_value,
                    fill.fee_value,
                    fill.tax_value,
                    side_by_order[str(fill.order_id)],
                )
                for fill in fills
            ),
            tuple(
                ReconciliationLedgerEntry(item.source_reference, item.amount, item.quantity or Decimal(0))
                for item in ledger
            ),
        )
        persisted: list[ReconciliationBreak] = []
        for item in detected:
            existing = await self.session.scalar(
                sa.select(ReconciliationBreak).where(
                    ReconciliationBreak.portfolio_id == portfolio.id,
                    ReconciliationBreak.as_of == as_of,
                    ReconciliationBreak.rule == item.rule,
                    ReconciliationBreak.resource_key == item.resource_key,
                )
            )
            if existing is not None:
                persisted.append(existing)
                continue
            row = ReconciliationBreak(
                organization_id=context.organization_id,
                portfolio_id=portfolio.id,
                as_of=as_of,
                rule=item.rule,
                resource_key=item.resource_key,
                expected=item.expected,
                actual=item.actual,
                severity=item.severity,
                owner_role="operations",
                status="open",
                blocking=item.blocking,
            )
            self.session.add(row)
            await self.session.flush()
            persisted.append(row)
            deduplication_key = f"reconciliation:{portfolio.id}:{as_of.date()}:{item.rule}:{item.resource_key}"
            self.session.add(
                OperationalAlert(
                    organization_id=context.organization_id,
                    portfolio_id=portfolio.id,
                    deduplication_key=deduplication_key,
                    alert_type="reconciliation_break",
                    severity=item.severity,
                    rule_version="reconciliation-v1",
                    route="operations",
                    status="open",
                    payload={"break_id": str(row.id), "rule": item.rule, "blocking": item.blocking},
                )
            )
            self._audit_entity(
                "reconciliation_break.detect",
                "reconciliation_break",
                row.id,
                context.subject,
                context.organization_id,
                correlation_id,
                {"rule": item.rule, "severity": item.severity, "blocking": item.blocking},
            )
        return tuple(persisted)

    async def resolve_break(
        self,
        break_id: UUID,
        *,
        resolution: dict[str, object],
        context: InstitutionalAccessContext,
        correlation_id: UUID,
    ) -> ReconciliationBreak:
        if "reconciliation:write" not in context.permissions:
            raise PermissionError("permission required: reconciliation:write")
        row = await self.session.get(ReconciliationBreak, break_id, with_for_update=True)
        if row is None or row.organization_id != context.organization_id:
            raise LookupError("reconciliation break not found")
        if row.status == "resolved":
            return row
        if not resolution.get("evidence") or not resolution.get("method"):
            raise ValueError("resolution requires method and evidence")
        row.status = "resolved"
        row.resolution = {**resolution, "resolved_by": context.subject}
        row.resolved_at = datetime.now(UTC)
        self._audit_entity(
            "reconciliation_break.resolve",
            "reconciliation_break",
            row.id,
            context.subject,
            context.organization_id,
            correlation_id,
            row.resolution,
        )
        return row

    async def acknowledge_alert(
        self,
        alert_id: UUID,
        *,
        context: InstitutionalAccessContext,
        correlation_id: UUID,
    ) -> OperationalAlert:
        if "alerts:acknowledge" not in context.permissions:
            raise PermissionError("permission required: alerts:acknowledge")
        alert = await self.session.get(OperationalAlert, alert_id, with_for_update=True)
        if alert is None or alert.organization_id != context.organization_id:
            raise LookupError("operational alert not found")
        if alert.status == "open":
            alert.status = "acknowledged"
            alert.acknowledged_by = context.subject
            alert.acknowledged_at = datetime.now(UTC)
            self._audit_entity(
                "operational_alert.acknowledge",
                "operational_alert",
                alert.id,
                context.subject,
                context.organization_id,
                correlation_id,
                {"deduplication_key": alert.deduplication_key},
            )
        return alert

    async def activate_kill_switch(
        self,
        *,
        portfolio_id: UUID | None,
        reason: str,
        context: InstitutionalAccessContext,
        correlation_id: UUID,
    ) -> PaperKillSwitch:
        if "paper_orders:kill" not in context.permissions:
            raise PermissionError("permission required: paper_orders:kill")
        if portfolio_id is not None:
            portfolio = await self.session.get(ModelPortfolio, portfolio_id)
            if portfolio is None or portfolio.organization_id != context.organization_id:
                raise LookupError("portfolio not found")
        existing = await self.session.scalar(
            sa.select(PaperKillSwitch).where(
                PaperKillSwitch.organization_id == context.organization_id,
                PaperKillSwitch.portfolio_id == portfolio_id,
                PaperKillSwitch.active.is_(True),
            )
        )
        if existing is not None:
            return existing
        switch = PaperKillSwitch(
            organization_id=context.organization_id,
            portfolio_id=portfolio_id,
            active=True,
            reason=reason,
            activated_by=context.subject,
        )
        self.session.add(switch)
        await self.session.flush()
        self._audit_entity(
            "paper_kill_switch.activate",
            "paper_kill_switch",
            switch.id,
            context.subject,
            context.organization_id,
            correlation_id,
            {"portfolio_id": str(portfolio_id) if portfolio_id else None, "reason": reason},
        )
        return switch

    async def release_kill_switch(
        self,
        switch_id: UUID,
        *,
        context: InstitutionalAccessContext,
        correlation_id: UUID,
    ) -> PaperKillSwitch:
        if "paper_orders:kill" not in context.permissions:
            raise PermissionError("permission required: paper_orders:kill")
        switch = await self.session.get(PaperKillSwitch, switch_id, with_for_update=True)
        if switch is None or switch.organization_id != context.organization_id:
            raise LookupError("paper kill switch not found")
        if switch.active:
            ensure_four_eyes(switch.activated_by, context.subject)
            switch.active = False
            switch.released_by = context.subject
            switch.released_at = datetime.now(UTC)
            self._audit_entity(
                "paper_kill_switch.release",
                "paper_kill_switch",
                switch.id,
                context.subject,
                context.organization_id,
                correlation_id,
                {"activated_by": switch.activated_by},
            )
        return switch

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
        if "postmortem:write" not in context.permissions:
            raise PermissionError("permission required: postmortem:write")
        portfolio = await self.session.get(ModelPortfolio, portfolio_id)
        if portfolio is None or portfolio.organization_id != context.organization_id:
            raise LookupError("portfolio not found")
        if period_start.tzinfo is None or period_end.tzinfo is None or period_end <= period_start:
            raise ValueError("post-mortem period must be a valid timezone-aware window")
        validate_post_mortem_lineage(attribution)
        version = (
            await self.session.scalar(
                sa.select(sa.func.max(PaperPostMortem.version)).where(PaperPostMortem.portfolio_id == portfolio.id)
            )
            or 0
        ) + 1
        payload = {
            "portfolio_id": str(portfolio.id),
            "version": version,
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
            "expected": expected,
            "realized": realized,
            "attribution": attribution,
            "findings": findings,
            "dissent": dissent,
        }
        row = PaperPostMortem(
            organization_id=context.organization_id,
            portfolio_id=portfolio.id,
            version=version,
            period_start=period_start,
            period_end=period_end,
            expected=expected,
            realized=realized,
            attribution=attribution,
            findings=findings,
            dissent=dissent,
            content_sha256=immutable_report_hash(payload),
            created_by=context.subject,
        )
        self.session.add(row)
        await self.session.flush()
        self._audit_entity(
            "paper_post_mortem.create",
            "paper_post_mortem",
            row.id,
            context.subject,
            context.organization_id,
            correlation_id,
            {"version": version, "content_sha256": row.content_sha256},
        )
        return row

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
        if "portfolio:propose" not in context.permissions:
            raise PermissionError("permission required: portfolio:propose")
        champion = await self.session.get(ModelPortfolio, champion_portfolio_id)
        challenger = await self.session.get(ModelPortfolio, challenger_portfolio_id)
        if (
            champion is None
            or challenger is None
            or champion.organization_id != context.organization_id
            or challenger.organization_id != context.organization_id
        ):
            raise LookupError("champion or challenger portfolio not found")
        if champion.mandate_id != challenger.mandate_id:
            raise ValueError("champion and challenger must share the same mandate")
        if champion.environment != "paper" or challenger.environment != "paper":
            raise ValueError("champion/challenger comparison is paper-only")
        comparison_sha256 = validate_challenger_comparison(comparison_config)
        row = ChallengerEvaluation(
            mandate_id=champion.mandate_id,
            champion_portfolio_id=champion.id,
            challenger_portfolio_id=challenger.id,
            window_start=window_start,
            window_end=window_end,
            methodology_version=methodology_version,
            comparison_sha256=comparison_sha256,
            comparison_config=comparison_config,
            metrics=metrics,
            evidence=evidence,
            decision="pending_committee",
            created_by=context.subject,
        )
        self.session.add(row)
        await self.session.flush()
        self._audit_entity(
            "challenger_evaluation.create",
            "challenger_evaluation",
            row.id,
            context.subject,
            context.organization_id,
            correlation_id,
            {"comparison_sha256": comparison_sha256},
        )
        return row

    async def decide_challenger(
        self,
        evaluation_id: UUID,
        *,
        decision: str,
        context: InstitutionalAccessContext,
        correlation_id: UUID,
    ) -> ChallengerEvaluation:
        if "committee:vote" not in context.permissions:
            raise PermissionError("permission required: committee:vote")
        row = await self.session.get(ChallengerEvaluation, evaluation_id, with_for_update=True)
        if row is None:
            raise LookupError("challenger evaluation not found")
        champion = await self.session.get(ModelPortfolio, row.champion_portfolio_id)
        if champion is None or champion.organization_id != context.organization_id:
            raise LookupError("challenger evaluation not found")
        ensure_four_eyes(row.created_by, context.subject)
        if row.decision != "pending_committee":
            raise ValueError("challenger evaluation has already been decided")
        if decision not in {"retained", "promoted", "rejected"}:
            raise ValueError("invalid challenger decision")
        row.decision = decision
        row.decided_by = context.subject
        row.decided_at = datetime.now(UTC)
        self._audit_entity(
            "challenger_evaluation.decide",
            "challenger_evaluation",
            row.id,
            context.subject,
            context.organization_id,
            correlation_id,
            {"decision": decision},
        )
        return row

    async def _require_operations_enabled(self, portfolio: ModelPortfolio) -> None:
        kill_switch = await self.session.scalar(
            sa.select(sa.func.count(PaperKillSwitch.id)).where(
                PaperKillSwitch.organization_id == portfolio.organization_id,
                PaperKillSwitch.active.is_(True),
                sa.or_(PaperKillSwitch.portfolio_id.is_(None), PaperKillSwitch.portfolio_id == portfolio.id),
            )
        )
        blocking_break = await self.session.scalar(
            sa.select(sa.func.count(ReconciliationBreak.id)).where(
                ReconciliationBreak.portfolio_id == portfolio.id,
                ReconciliationBreak.blocking.is_(True),
                ReconciliationBreak.status.in_(("open", "acknowledged")),
            )
        )
        if kill_switch:
            raise PermissionError("paper kill switch is active")
        if blocking_break:
            raise PermissionError("critical reconciliation break blocks paper execution")

    @staticmethod
    def _configuration(model: ExecutionModelVersion) -> ExecutionConfiguration:
        payload = model.configuration
        return ExecutionConfiguration(
            version=f"{model.logical_id}:{model.version}",
            lot_size=Decimal(str(payload["lot_size"])),
            max_participation=Decimal(str(payload["max_participation"])),
            spread_bps=Decimal(str(payload["spread_bps"])),
            impact_bps_at_full_participation=Decimal(str(payload["impact_bps_at_full_participation"])),
            fee_bps=Decimal(str(payload["fee_bps"])),
            tax_bps=Decimal(str(payload["tax_bps"])),
            latency_ms=int(payload["latency_ms"]),
        )

    def _record(
        self,
        intent: TradeIntent,
        event_type: str,
        action: str,
        actor: str,
        correlation_id: UUID,
    ) -> None:
        event_id = uuid4()
        self.session.add(
            DomainOutboxEvent(
                aggregate_type="paper_trade_intent",
                aggregate_id=intent.id,
                aggregate_version=1,
                event_type=event_type,
                payload={"status": intent.status, "environment": "paper"},
                correlation_id=correlation_id,
                idempotency_key=f"paper-intent:{intent.id}:{event_type}:{event_id}",
            )
        )
        self._audit_entity(
            action,
            "paper_trade_intent",
            intent.id,
            actor,
            intent.organization_id,
            correlation_id,
            {"event_type": event_type, "status": intent.status, "environment": "paper"},
        )

    def _audit_entity(
        self,
        action: str,
        entity_type: str,
        entity_id: UUID,
        actor: str,
        organization_id: UUID,
        correlation_id: UUID,
        details: dict[str, object],
    ) -> None:
        self.session.add(
            AuditLog(
                actor_type="human",
                actor_id=actor,
                action=action,
                entity_type=entity_type,
                entity_id=entity_id,
                correlation_id=correlation_id,
                details={**details, "organization_id": str(organization_id)},
            )
        )
