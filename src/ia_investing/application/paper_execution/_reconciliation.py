from __future__ import annotations

from dataclasses import dataclass
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
    DetectedBreak as DomainBreak,
)
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


@dataclass(frozen=True)
class ExecutionData:
    """Fetched orders, fills, and ledger entries for reconciliation."""

    portfolio: ModelPortfolio
    orders: list[tuple[PaperOrder, TradeIntent]]
    fills: list[PaperFill]
    ledger: list[PortfolioLedgerEntry]


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
        exec_data = await self._fetch_execution_data(portfolio, as_of)
        detected = self._detect_execution_breaks(exec_data)
        persisted: list[ReconciliationBreak] = []
        for item in detected:
            row = await self._persist_break(
                portfolio.id,
                as_of,
                context,
                correlation_id,
                item.rule,
                item.resource_key,
                item.expected,
                item.actual,
                item.severity,
                item.blocking,
            )
            persisted.append(row)
        version_breaks = await self._reconcile_version_breaks(
            portfolio,
            as_of,
            context,
            correlation_id,
        )
        persisted.extend(version_breaks)
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
            await self._create_compensating_entry(row, resolution)
        await audit_entity(
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

    async def _resolve_instrument_from_break(self, row: ReconciliationBreak) -> UUID | None:
        if row.rule not in ("fill_missing_ledger", "fill_ledger_identity"):
            return None
        fill = await self.session.scalar(sa.select(PaperFill).where(PaperFill.event_key == row.resource_key))
        if fill is None:
            return None
        order = await self.session.get(PaperOrder, fill.order_id)
        if order is None:
            return None
        intent = await self.session.get(TradeIntent, order.trade_intent_id)
        return intent.instrument_id if intent is not None else None

    async def _create_compensating_entry(self, row: ReconciliationBreak, resolution: dict[str, object]) -> None:
        portfolio = await self.session.get(ModelPortfolio, row.portfolio_id)
        if portfolio is None:
            return
        instrument_id = await self._resolve_instrument_from_break(row)
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

    async def _fetch_execution_data(self, portfolio: ModelPortfolio, as_of: datetime) -> ExecutionData:
        order_rows = (
            await self.session.execute(
                sa.select(PaperOrder, TradeIntent)
                .join(TradeIntent, TradeIntent.id == PaperOrder.trade_intent_id)
                .where(TradeIntent.portfolio_id == portfolio.id, PaperOrder.created_at <= as_of)
            )
        ).all()
        order_ids = [order.id for order, _intent in order_rows]
        fills: list[PaperFill] = []
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
        return ExecutionData(
            portfolio=portfolio,
            orders=list(order_rows),
            fills=fills,
            ledger=ledger,
        )

    def _detect_execution_breaks(self, data: ExecutionData) -> tuple[DomainBreak, ...]:
        side_by_order = {str(order.id): intent.side for order, intent in data.orders}
        return reconcile_execution(
            tuple(
                ReconciliationOrder(str(order.id), order.requested_quantity, order.filled_quantity, order.status)
                for order, _intent in data.orders
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
                for fill in data.fills
            ),
            tuple(
                ReconciliationLedgerEntry(item.source_reference, item.amount, item.quantity or Decimal(0))
                for item in data.ledger
            ),
        )

    async def _persist_break(
        self,
        portfolio_id: UUID,
        as_of: datetime,
        context: InstitutionalAccessContext,
        correlation_id: UUID,
        rule: str,
        resource_key: str,
        expected: dict[str, object] | None,
        actual: dict[str, object] | None,
        severity: str,
        blocking: bool,
    ) -> ReconciliationBreak:
        from database.models.paper_execution import OperationalAlert

        existing = await self.session.scalar(
            sa.select(ReconciliationBreak).where(
                ReconciliationBreak.portfolio_id == portfolio_id,
                ReconciliationBreak.as_of == as_of,
                ReconciliationBreak.rule == rule,
                ReconciliationBreak.resource_key == resource_key,
            )
        )
        if existing is not None:
            return existing
        row = ReconciliationBreak(
            organization_id=context.organization_id,
            portfolio_id=portfolio_id,
            as_of=as_of,
            rule=rule,
            resource_key=resource_key,
            expected=expected,
            actual=actual,
            severity=severity,
            owner_role="operations",
            status="open",
            blocking=blocking,
        )
        self.session.add(row)
        await self.session.flush()
        dedup_key = f"reconciliation:{portfolio_id}:{as_of.date()}:{rule}:{resource_key}"
        self.session.add(
            OperationalAlert(
                organization_id=context.organization_id,
                portfolio_id=portfolio_id,
                deduplication_key=dedup_key,
                alert_type="reconciliation_break",
                severity=severity,
                rule_version="reconciliation-v1",
                route="operations",
                status="open",
                payload={"break_id": str(row.id), "rule": rule, "blocking": blocking},
            )
        )
        await audit_entity(
            self.session,
            "reconciliation_break.detect",
            "reconciliation_break",
            row.id,
            context.subject,
            context.organization_id,
            correlation_id,
            {"rule": rule, "severity": severity, "blocking": blocking},
        )
        return row

    async def _reconcile_version_breaks(
        self,
        portfolio: ModelPortfolio,
        as_of: datetime,
        context: InstitutionalAccessContext,
        correlation_id: UUID,
    ) -> list[ReconciliationBreak]:
        latest_version = await self.session.scalar(
            sa.select(InstitutionalPortfolioVersion)
            .where(
                InstitutionalPortfolioVersion.portfolio_id == portfolio.id,
                InstitutionalPortfolioVersion.status.in_(["approved", "draft"]),
            )
            .order_by(InstitutionalPortfolioVersion.version.desc())
            .limit(1)
        )
        if latest_version is None:
            return []
        position_breaks = await self._reconcile_positions(portfolio.id, latest_version.id, as_of)
        cash_breaks = await self._reconcile_cash(portfolio.id, latest_version.id, as_of)
        persisted: list[ReconciliationBreak] = []
        for item in position_breaks + cash_breaks:
            row = await self._persist_break(
                portfolio.id,
                as_of,
                context,
                correlation_id,
                item.rule,
                item.instrument_id,
                item.expected,
                item.actual,
                item.severity,
                item.blocking,
            )
            persisted.append(row)
        return persisted

    async def _reconcile_positions(
        self, portfolio_id: UUID, version_id: UUID, as_of: datetime
    ) -> tuple[DomainBreak, ...]:
        position_rows = list(
            (
                await self.session.scalars(
                    sa.select(PositionSnapshot).where(PositionSnapshot.portfolio_version_id == version_id)
                )
            ).all()
        )
        ledger_position_entries = list(
            (
                await self.session.scalars(
                    sa.select(PortfolioLedgerEntry).where(
                        PortfolioLedgerEntry.portfolio_id == portfolio_id,
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
        return reconcile_positions(ledger_positions, snapshot_positions)

    async def _reconcile_cash(self, portfolio_id: UUID, version_id: UUID, as_of: datetime) -> tuple[DomainBreak, ...]:
        cash_entries = list(
            (
                await self.session.scalars(
                    sa.select(PortfolioLedgerEntry).where(
                        PortfolioLedgerEntry.portfolio_id == portfolio_id,
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
                    sa.select(CashSnapshot).where(CashSnapshot.portfolio_version_id == version_id)
                )
            ).all()
        )
        snapshot_cash = tuple(SnapshotCash(item.currency, item.amount) for item in cash_rows)
        return reconcile_cash(ledger_cash, snapshot_cash)
