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
from database.models.portfolio_versions import CashSnapshot, PositionSnapshot
from database.models.research import DomainOutboxEvent
from ia_investing.domain.identity import InstitutionalAccessContext, ResourceAttributes, authorize, ensure_four_eyes
from ia_investing.domain.paper_execution import (
    INTENT_TRANSITIONS,
    ORDER_TRANSITIONS,
    ExecutionConfiguration,
    LedgerCashEntry,
    LedgerPositionEntry,
    MarketSnapshot,
    ReconciliationFill,
    ReconciliationLedgerEntry,
    ReconciliationOrder,
    SnapshotCash,
    SnapshotPosition,
    TradingWindow,
    fill_to_ledger,
    immutable_report_hash,
    reconcile_cash,
    reconcile_execution,
    reconcile_positions,
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
        if order is not None:
            self._record_order(
                order,
                "PaperOrderCancelled",
                "paper_order.cancel",
                context.subject,
                context.organization_id,
                correlation_id,
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
        simulated_fills: list[PaperFill] = []
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
            simulated_fills.append(fill)
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
        if simulated_fills:
            deltas = [fill_to_ledger(intent.side, s) for s in result.fills]
            total_qty = sum(d.instrument_quantity for d in deltas)
            total_cash = sum(d.cash_delta for d in deltas)
            latest_version = await self.session.scalar(
                sa.select(InstitutionalPortfolioVersion)
                .where(
                    InstitutionalPortfolioVersion.portfolio_id == intent.portfolio_id,
                    InstitutionalPortfolioVersion.status.in_(["approved", "draft"]),
                )
                .order_by(InstitutionalPortfolioVersion.version.desc())
                .limit(1)
            )
            version_id = latest_version.id if latest_version else intent.portfolio_version_id
            existing_pos = await self.session.scalar(
                sa.select(PositionSnapshot).where(
                    PositionSnapshot.portfolio_version_id == version_id,
                    PositionSnapshot.instrument_id == intent.instrument_id,
                )
            )
            if existing_pos is not None:
                new_qty = existing_pos.quantity + total_qty
                if new_qty < 0:
                    raise ValueError("sell would result in negative position")
                existing_pos.quantity = new_qty
                existing_pos.as_of = datetime.now(UTC)
            elif total_qty > 0:
                self.session.add(
                    PositionSnapshot(
                        portfolio_version_id=version_id,
                        instrument_id=intent.instrument_id,
                        quantity=total_qty,
                        cost_basis=Decimal(0),
                        as_of=datetime.now(UTC),
                    )
                )
            existing_cash = await self.session.scalar(
                sa.select(CashSnapshot).where(
                    CashSnapshot.portfolio_version_id == version_id,
                    CashSnapshot.currency == portfolio.base_currency,
                )
            )
            if existing_cash is not None:
                existing_cash.amount = existing_cash.amount + total_cash
                existing_cash.as_of = datetime.now(UTC)
            else:
                self.session.add(
                    CashSnapshot(
                        portfolio_version_id=version_id,
                        currency=portfolio.base_currency,
                        amount=total_cash,
                        as_of=datetime.now(UTC),
                    )
                )
        intent.status = "completed" if result.status == "filled" else "submitted" if simulated_fills else "expired"
        intent.updated_at = datetime.now(UTC)
        self._record(intent, "PaperOrderSimulated", "paper_order.simulate", context.subject, correlation_id)
        order_event_type = {
            "accepted": "PaperOrderAccepted",
            "partially_filled": "PaperOrderPartiallyFilled",
            "filled": "PaperOrderFilled",
            "cancelled": "PaperOrderCancelled",
            "rejected": "PaperOrderRejected",
            "expired": "PaperOrderExpired",
        }.get(order.status, "PaperOrderAccepted")
        self._record_order(
            order,
            order_event_type,
            f"paper_order.{order.status}",
            context.subject,
            context.organization_id,
            correlation_id,
        )
        return order, tuple(simulated_fills)

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
        latest_version = await self.session.scalar(
            sa.select(InstitutionalPortfolioVersion)
            .where(
                InstitutionalPortfolioVersion.portfolio_id == portfolio.id,
                InstitutionalPortfolioVersion.status.in_(["approved", "draft"]),
            )
            .order_by(InstitutionalPortfolioVersion.version.desc())
            .limit(1)
        )
        if latest_version is not None:
            position_rows = list(
                (
                    await self.session.scalars(
                        sa.select(PositionSnapshot).where(
                            PositionSnapshot.portfolio_version_id == latest_version.id,
                        )
                    )
                ).all()
            )
            ledger_position_entries = list(
                (
                    await self.session.scalars(
                        sa.select(PortfolioLedgerEntry).where(
                            PortfolioLedgerEntry.portfolio_id == portfolio.id,
                            PortfolioLedgerEntry.occurred_at <= as_of,
                            PortfolioLedgerEntry.instrument_id.isnot(None),
                        )
                    )
                ).all()
            )
            ledger_positions = tuple(
                LedgerPositionEntry(str(item.instrument_id), item.quantity or Decimal(0))
                for item in ledger_position_entries
            )
            snapshot_positions = tuple(
                SnapshotPosition(str(item.instrument_id), item.quantity, item.cost_basis) for item in position_rows
            )
            position_breaks = reconcile_positions(ledger_positions, snapshot_positions)
            for pb in position_breaks:
                existing = await self.session.scalar(
                    sa.select(ReconciliationBreak).where(
                        ReconciliationBreak.portfolio_id == portfolio.id,
                        ReconciliationBreak.as_of == as_of,
                        ReconciliationBreak.rule == pb.rule,
                        ReconciliationBreak.resource_key == pb.instrument_id,
                    )
                )
                if existing is not None:
                    persisted.append(existing)
                    continue
                row = ReconciliationBreak(
                    organization_id=context.organization_id,
                    portfolio_id=portfolio.id,
                    as_of=as_of,
                    rule=pb.rule,
                    resource_key=pb.instrument_id,
                    expected=pb.expected,
                    actual=pb.actual,
                    severity=pb.severity,
                    owner_role="operations",
                    status="open",
                    blocking=pb.blocking,
                )
                self.session.add(row)
                await self.session.flush()
                persisted.append(row)
                deduplication_key = f"reconciliation:{portfolio.id}:{as_of.date()}:{pb.rule}:{pb.instrument_id}"
                self.session.add(
                    OperationalAlert(
                        organization_id=context.organization_id,
                        portfolio_id=portfolio.id,
                        deduplication_key=deduplication_key,
                        alert_type="reconciliation_break",
                        severity=pb.severity,
                        rule_version="reconciliation-v1",
                        route="operations",
                        status="open",
                        payload={"break_id": str(row.id), "rule": pb.rule, "blocking": pb.blocking},
                    )
                )
            cash_entries = list(
                (
                    await self.session.scalars(
                        sa.select(PortfolioLedgerEntry).where(
                            PortfolioLedgerEntry.portfolio_id == portfolio.id,
                            PortfolioLedgerEntry.occurred_at <= as_of,
                            PortfolioLedgerEntry.instrument_id.is_(None),
                        )
                    )
                ).all()
            )
            ledger_cash = tuple(LedgerCashEntry(item.currency, item.amount) for item in cash_entries)
            cash_rows = list(
                (
                    await self.session.scalars(
                        sa.select(CashSnapshot).where(
                            CashSnapshot.portfolio_version_id == latest_version.id,
                        )
                    )
                ).all()
            )
            snapshot_cash = tuple(SnapshotCash(item.currency, item.amount) for item in cash_rows)
            cash_breaks = reconcile_cash(ledger_cash, snapshot_cash)
            for cb in cash_breaks:
                existing = await self.session.scalar(
                    sa.select(ReconciliationBreak).where(
                        ReconciliationBreak.portfolio_id == portfolio.id,
                        ReconciliationBreak.as_of == as_of,
                        ReconciliationBreak.rule == cb.rule,
                        ReconciliationBreak.resource_key == cb.instrument_id,
                    )
                )
                if existing is not None:
                    persisted.append(existing)
                    continue
                row = ReconciliationBreak(
                    organization_id=context.organization_id,
                    portfolio_id=portfolio.id,
                    as_of=as_of,
                    rule=cb.rule,
                    resource_key=cb.instrument_id,
                    expected=cb.expected,
                    actual=cb.actual,
                    severity=cb.severity,
                    owner_role="operations",
                    status="open",
                    blocking=cb.blocking,
                )
                self.session.add(row)
                await self.session.flush()
                persisted.append(row)
                deduplication_key = f"reconciliation:{portfolio.id}:{as_of.date()}:{cb.rule}:{cb.instrument_id}"
                self.session.add(
                    OperationalAlert(
                        organization_id=context.organization_id,
                        portfolio_id=portfolio.id,
                        deduplication_key=deduplication_key,
                        alert_type="reconciliation_break",
                        severity=cb.severity,
                        rule_version="reconciliation-v1",
                        route="operations",
                        status="open",
                        payload={"break_id": str(row.id), "rule": cb.rule, "blocking": cb.blocking},
                    )
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
        if resolution.get("method") == "compensating_entry" and resolution.get("compensating_reference"):
            portfolio = await self.session.get(ModelPortfolio, row.portfolio_id)
            if portfolio is not None:
                instrument_id = None
                if row.rule in ("fill_missing_ledger", "fill_ledger_identity"):
                    event_key = row.resource_key
                    fill = await self.session.scalar(sa.select(PaperFill).where(PaperFill.event_key == event_key))
                    if fill is not None:
                        order = await self.session.get(PaperOrder, fill.order_id)
                        if order is not None:
                            intent = await self.session.get(TradeIntent, order.trade_intent_id)
                            if intent is not None:
                                instrument_id = intent.instrument_id
                expected = row.expected or {}
                actual = row.actual or {}
                quantity_delta = Decimal(str(actual.get("quantity", "0"))) - Decimal(str(expected.get("quantity", "0")))
                amount_delta = Decimal(str(actual.get("amount", "0"))) - Decimal(str(expected.get("amount", "0")))
                if quantity_delta != 0 or amount_delta != 0:
                    self.session.add(
                        PortfolioLedgerEntry(
                            portfolio_id=row.portfolio_id,
                            instrument_id=instrument_id,
                            entry_type="trade",
                            currency=portfolio.base_currency,
                            amount=-amount_delta,
                            quantity=-quantity_delta if quantity_delta != 0 else None,
                            occurred_at=datetime.now(UTC),
                            source_reference=str(resolution["compensating_reference"]),
                        )
                    )
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
        if decision == "promoted":
            challenger_latest = await self.session.scalar(
                sa.select(InstitutionalPortfolioVersion)
                .where(
                    InstitutionalPortfolioVersion.portfolio_id == row.challenger_portfolio_id,
                    InstitutionalPortfolioVersion.status.in_(["approved", "draft"]),
                )
                .order_by(InstitutionalPortfolioVersion.version.desc())
                .limit(1)
            )
            if challenger_latest is not None:
                next_version = challenger_latest.version + 1
                new_version = InstitutionalPortfolioVersion(
                    portfolio_id=row.challenger_portfolio_id,
                    mandate_id=row.mandate_id,
                    version=next_version,
                    as_of=datetime.now(UTC),
                    input_snapshot_sha256=challenger_latest.input_snapshot_sha256,
                    weights_sha256=challenger_latest.weights_sha256,
                    approved_weights=challenger_latest.approved_weights,
                    proposal={
                        "source": "challenger_promotion",
                        "evaluation_id": str(row.id),
                        "promoted_from_version": challenger_latest.version,
                    },
                    decision={
                        "decided_by": context.subject,
                        "decided_at": datetime.now(UTC).isoformat(),
                        "reason": "challenger_promotion",
                    },
                    status="approved",
                    created_by=context.subject,
                    approved_by=context.subject,
                )
                self.session.add(new_version)
                await self.session.flush()
                self._audit_entity(
                    "portfolio_version.create",
                    "institutional_portfolio_version",
                    new_version.id,
                    context.subject,
                    context.organization_id,
                    correlation_id,
                    {
                        "version": next_version,
                        "portfolio_id": str(row.challenger_portfolio_id),
                    },
                )
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

    async def get_order_with_intent(
        self, order_id: UUID, organization_id: UUID
    ) -> tuple[PaperOrder, TradeIntent] | None:
        order = await self.session.get(PaperOrder, order_id)
        if order is None:
            return None
        intent = await self.session.get(TradeIntent, order.trade_intent_id)
        if intent is None or intent.organization_id != organization_id:
            return None
        return order, intent

    async def list_fills_for_order(self, order_id: UUID) -> list[PaperFill]:
        return list(
            (
                await self.session.scalars(
                    sa.select(PaperFill).where(PaperFill.order_id == order_id).order_by(PaperFill.sequence)
                )
            ).all()
        )

    async def resolve_alert(
        self,
        alert_id: UUID,
        *,
        resolution: dict[str, object],
        context: InstitutionalAccessContext,
        correlation_id: UUID,
    ) -> OperationalAlert:
        if "alerts:acknowledge" not in context.permissions:
            raise PermissionError("permission required: alerts:acknowledge")
        alert = await self.session.get(OperationalAlert, alert_id, with_for_update=True)
        if alert is None or alert.organization_id != context.organization_id:
            raise LookupError("operational alert not found")
        if alert.status in ("resolved",):
            return alert
        if alert.status == "open":
            alert.status = "acknowledged"
            alert.acknowledged_by = context.subject
            alert.acknowledged_at = datetime.now(UTC)
        alert.status = "resolved"
        alert.payload = {**alert.payload, "resolution": resolution, "resolved_by": context.subject}
        self._audit_entity(
            "operational_alert.resolve",
            "operational_alert",
            alert.id,
            context.subject,
            context.organization_id,
            correlation_id,
            {"deduplication_key": alert.deduplication_key, "resolution": resolution},
        )
        return alert

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
        if "alerts:read" not in context.permissions:
            raise PermissionError("permission required: alerts:read")
        stmt = sa.select(OperationalAlert).where(OperationalAlert.organization_id == context.organization_id)
        if status is not None:
            stmt = stmt.where(OperationalAlert.status == status)
        if severity is not None:
            stmt = stmt.where(OperationalAlert.severity == severity)
        if alert_type is not None:
            stmt = stmt.where(OperationalAlert.alert_type == alert_type)
        if portfolio_id is not None:
            stmt = stmt.where(OperationalAlert.portfolio_id == portfolio_id)
        stmt = stmt.order_by(OperationalAlert.created_at.desc()).limit(limit)
        return list((await self.session.scalars(stmt)).all())

    async def list_post_mortems(
        self,
        portfolio_id: UUID,
        *,
        limit: int = 50,
    ) -> list[PaperPostMortem]:
        stmt = sa.select(PaperPostMortem).where(PaperPostMortem.portfolio_id == portfolio_id)
        stmt = stmt.order_by(PaperPostMortem.created_at.desc()).limit(limit)
        return list((await self.session.scalars(stmt)).all())

    async def list_challenger_evaluations(
        self,
        *,
        organization_id: UUID | None = None,
        portfolio_id: UUID | None = None,
        limit: int = 50,
    ) -> list[ChallengerEvaluation]:
        stmt = sa.select(ChallengerEvaluation)
        if organization_id is not None:
            stmt = stmt.join(ModelPortfolio, ModelPortfolio.id == ChallengerEvaluation.champion_portfolio_id)
            stmt = stmt.where(ModelPortfolio.organization_id == organization_id)
        if portfolio_id is not None:
            stmt = stmt.where(ChallengerEvaluation.champion_portfolio_id == portfolio_id)
        stmt = stmt.order_by(ChallengerEvaluation.window_end.desc()).limit(limit)
        return list((await self.session.scalars(stmt)).all())

    async def get_operational_dashboard(
        self,
        organization_id: UUID,
    ) -> dict[str, object]:
        now = datetime.now(UTC)

        order_count = await self.session.scalar(
            sa.select(sa.func.count(PaperOrder.id)).where(
                PaperOrder.environment == "paper",
            )
        )
        fill_count = await self.session.scalar(
            sa.select(sa.func.count(PaperFill.id)).where(
                PaperFill.environment == "paper",
            )
        )
        active_breaks = await self.session.scalar(
            sa.select(sa.func.count(ReconciliationBreak.id)).where(
                ReconciliationBreak.status.in_(("open", "acknowledged")),
            )
        )
        blocking_breaks = await self.session.scalar(
            sa.select(sa.func.count(ReconciliationBreak.id)).where(
                ReconciliationBreak.status.in_(("open", "acknowledged")),
                ReconciliationBreak.blocking.is_(True),
            )
        )
        open_alerts = await self.session.scalar(
            sa.select(sa.func.count(OperationalAlert.id)).where(
                OperationalAlert.status == "open",
            )
        )
        critical_alerts = await self.session.scalar(
            sa.select(sa.func.count(OperationalAlert.id)).where(
                OperationalAlert.status == "open",
                OperationalAlert.severity == "critical",
            )
        )
        kill_switches = await self.session.scalar(
            sa.select(sa.func.count(PaperKillSwitch.id)).where(
                PaperKillSwitch.active.is_(True),
            )
        )

        return {
            "as_of": now.isoformat(),
            "orders_total": int(order_count or 0),
            "fills_total": int(fill_count or 0),
            "reconciliation_breaks_open": int(active_breaks or 0),
            "reconciliation_breaks_blocking": int(blocking_breaks or 0),
            "alerts_open": int(open_alerts or 0),
            "alerts_critical": int(critical_alerts or 0),
            "kill_switches_active": int(kill_switches or 0),
            "slo": {
                "execution_success_rate": "N/A (paper environment)",
                "reconciliation_freshness": "daily",
                "alert_acknowledgement_sla": "4h",
                "nav_publication_sla": "T+1",
            },
        }

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

    def _record_order(
        self,
        order: PaperOrder,
        event_type: str,
        action: str,
        actor: str,
        organization_id: UUID,
        correlation_id: UUID,
    ) -> None:
        event_id = uuid4()
        self.session.add(
            DomainOutboxEvent(
                aggregate_type="paper_order",
                aggregate_id=order.id,
                aggregate_version=1,
                event_type=event_type,
                payload={
                    "status": order.status,
                    "environment": "paper",
                    "filled_quantity": str(order.filled_quantity),
                    "requested_quantity": str(order.requested_quantity),
                },
                correlation_id=correlation_id,
                idempotency_key=f"paper-order:{order.id}:{event_type}:{event_id}",
            )
        )
        self._audit_entity(
            action,
            "paper_order",
            order.id,
            actor,
            organization_id,
            correlation_id,
            {"event_type": event_type, "status": order.status, "environment": "paper"},
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
