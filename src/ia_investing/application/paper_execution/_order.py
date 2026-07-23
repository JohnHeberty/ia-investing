from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.instrument_master import Listing
from database.models.market_data import MarketBar, TradingSession
from database.models.paper_execution import ExecutionModelVersion, PaperFill, PaperOrder, TradeIntent
from database.models.portfolio_domain import InstitutionalPortfolioVersion, ModelPortfolio, PortfolioLedgerEntry
from database.models.portfolio_versions import CashSnapshot, PositionSnapshot
from ia_investing.domain.identity import InstitutionalAccessContext, ResourceAttributes, authorize
from ia_investing.domain.paper_execution import (
    MarketSnapshot,
    TradingWindow,
    fill_to_ledger,
    simulate_order,
    validate_paper_order_request,
)

from ._base import configuration, record, record_order, require_operations_enabled


class OrderService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

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
        await require_operations_enabled(self.session, portfolio)
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
        model_config = configuration(model)
        assert intent.approval_decision is not None
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
            lot_size=model_config.lot_size,
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
            configuration=model_config,
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
                filled_at=simulated.market_timestamp + timedelta(milliseconds=model_config.latency_ms),
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
        record(self.session, intent, "PaperOrderSimulated", "paper_order.simulate", context.subject, correlation_id)
        order_event_type = {
            "accepted": "PaperOrderAccepted",
            "partially_filled": "PaperOrderPartiallyFilled",
            "filled": "PaperOrderFilled",
            "cancelled": "PaperOrderCancelled",
            "rejected": "PaperOrderRejected",
            "expired": "PaperOrderExpired",
        }.get(order.status, "PaperOrderAccepted")
        record_order(
            self.session,
            order,
            order_event_type,
            f"paper_order.{order.status}",
            context.subject,
            context.organization_id,
            correlation_id,
        )
        return order, tuple(simulated_fills)

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
