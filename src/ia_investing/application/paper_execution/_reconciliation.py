from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.paper_execution import PaperFill, PaperOrder, ReconciliationBreak, TradeIntent
from database.models.portfolio_domain import InstitutionalPortfolioVersion, ModelPortfolio, PortfolioLedgerEntry
from database.models.portfolio_versions import CashSnapshot, PositionSnapshot
from ia_investing.domain.identity import InstitutionalAccessContext
from ia_investing.domain.paper_execution import (
    LedgerCashEntry,
    LedgerPositionEntry,
    ReconciliationFill,
    ReconciliationLedgerEntry,
    ReconciliationOrder,
    SnapshotCash,
    SnapshotPosition,
    reconcile_cash,
    reconcile_execution,
    reconcile_positions,
)

from ._base import audit_entity


class ReconciliationService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

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
            from database.models.paper_execution import OperationalAlert

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
            dedup_key = f"reconciliation:{portfolio.id}:{as_of.date()}:{item.rule}:{item.resource_key}"
            self.session.add(
                OperationalAlert(
                    organization_id=context.organization_id,
                    portfolio_id=portfolio.id,
                    deduplication_key=dedup_key,
                    alert_type="reconciliation_break",
                    severity=item.severity,
                    rule_version="reconciliation-v1",
                    route="operations",
                    status="open",
                    payload={"break_id": str(row.id), "rule": item.rule, "blocking": item.blocking},
                )
            )
            audit_entity(
                self.session,
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
                dedup_key = f"reconciliation:{portfolio.id}:{as_of.date()}:{pb.rule}:{pb.instrument_id}"
                self.session.add(
                    OperationalAlert(
                        organization_id=context.organization_id,
                        portfolio_id=portfolio.id,
                        deduplication_key=dedup_key,
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
                dedup_key = f"reconciliation:{portfolio.id}:{as_of.date()}:{cb.rule}:{cb.instrument_id}"
                self.session.add(
                    OperationalAlert(
                        organization_id=context.organization_id,
                        portfolio_id=portfolio.id,
                        deduplication_key=dedup_key,
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
                instrument_id: UUID | None = None
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
                qty_delta = Decimal(str(actual.get("quantity", "0"))) - Decimal(str(expected.get("quantity", "0")))
                amt_delta = Decimal(str(actual.get("amount", "0"))) - Decimal(str(expected.get("amount", "0")))
                if qty_delta != 0 or amt_delta != 0:
                    self.session.add(
                        PortfolioLedgerEntry(
                            portfolio_id=row.portfolio_id,
                            instrument_id=instrument_id,
                            entry_type="trade",
                            currency=portfolio.base_currency,
                            amount=-amt_delta,
                            quantity=-qty_delta if qty_delta != 0 else None,
                            occurred_at=datetime.now(UTC),
                            source_reference=str(resolution["compensating_reference"]),
                        )
                    )
        audit_entity(
            self.session,
            "reconciliation_break.resolve",
            "reconciliation_break",
            row.id,
            context.subject,
            context.organization_id,
            correlation_id,
            row.resolution,
        )
        return row
