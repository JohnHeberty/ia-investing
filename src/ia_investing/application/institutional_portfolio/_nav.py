from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.instrument_master import Instrument, Listing
from database.models.market_data import CorporateAction, MarketBar, MarketIndex
from database.models.portfolio_domain import (
    CashSnapshot,
    InstitutionalPortfolioVersion,
    ModelPortfolio,
    NavPublication,
    PortfolioLedgerEntry,
    PositionSnapshot,
    StrategyMandate,
)
from ia_investing.domain.identity import InstitutionalAccessContext, ResourceAttributes, authorize
from ia_investing.domain.institutional_portfolio import (
    PositionValue,
    calculate_nav,
    canonical_hash,
)

from ._base import fx_multiplier, latest_instrument_bar


class NavService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def publish_nav(
        self,
        version_id: UUID,
        as_of: datetime,
        context: InstitutionalAccessContext,
    ) -> NavPublication:
        version = await self.session.get(InstitutionalPortfolioVersion, version_id)
        if version is None:
            raise LookupError("portfolio version not found")
        portfolio = await self.session.get(ModelPortfolio, version.portfolio_id)
        if portfolio is None:
            raise RuntimeError("portfolio version references missing portfolio")
        authorize(context, "nav:publish", ResourceAttributes(portfolio.organization_id, portfolio.owner_team_id))
        snapshots = list(
            (
                await self.session.execute(
                    sa.select(PositionSnapshot).where(PositionSnapshot.portfolio_version_id == version.id)
                )
            ).scalars()
        )
        positions: list[PositionValue] = []
        input_details: dict[str, object] = {"positions": [], "cash": [], "corporate_action_cash": []}
        corporate_action_cash: list[Decimal] = []
        invested_cost = Decimal(0)
        for snapshot in snapshots:
            price_row = (
                await self.session.execute(
                    sa.select(Listing, MarketBar)
                    .join(MarketBar, MarketBar.listing_id == Listing.id)
                    .where(
                        Listing.instrument_id == snapshot.instrument_id,
                        Listing.valid_from <= as_of.date(),
                        sa.or_(Listing.valid_to.is_(None), Listing.valid_to > as_of.date()),
                        MarketBar.bar_at <= as_of,
                        MarketBar.knowledge_at <= as_of,
                    )
                    .order_by(MarketBar.bar_at.desc(), MarketBar.knowledge_at.desc())
                    .limit(1)
                )
            ).first()
            if price_row is None:
                raise ValueError(f"price missing at as_of for instrument {snapshot.instrument_id}")
            listing, bar = price_row
            instrument = await self.session.get(Instrument, snapshot.instrument_id)
            if instrument is None:
                raise RuntimeError("position references missing instrument")
            fx_rate, fx_id = await fx_multiplier(self.session, instrument.currency_code, portfolio.base_currency, as_of)
            invested_cost += snapshot.quantity * snapshot.cost_basis * fx_rate
            quantity = snapshot.quantity
            actions = list(
                (
                    await self.session.scalars(
                        sa.select(CorporateAction)
                        .where(
                            CorporateAction.instrument_id == snapshot.instrument_id,
                            CorporateAction.knowledge_at <= as_of,
                            CorporateAction.ex_date.is_not(None),
                            CorporateAction.ex_date > snapshot.as_of.date(),
                            CorporateAction.ex_date <= as_of.date(),
                        )
                        .order_by(CorporateAction.ex_date, CorporateAction.knowledge_at)
                    )
                ).all()
            )
            applied_actions: list[str] = []
            for action in (item for item in actions if item.action_type in {"split", "reverse_split"}):
                if action.action_type == "split" and action.ratio is not None:
                    quantity *= action.ratio
                elif action.action_type == "reverse_split" and action.ratio is not None:
                    quantity /= action.ratio
                applied_actions.append(str(action.id))
            for action in (item for item in actions if item.action_type in {"dividend", "jcp"}):
                if action.amount_per_unit is not None:
                    action_currency = action.currency_code or instrument.currency_code
                    action_fx, action_fx_id = await fx_multiplier(
                        self.session, action_currency, portfolio.base_currency, as_of
                    )
                    amount = quantity * action.amount_per_unit * action_fx
                    corporate_action_cash.append(amount)
                    cast_cash = input_details["corporate_action_cash"]
                    if isinstance(cast_cash, list):
                        cast_cash.append(
                            {
                                "action_id": str(action.id),
                                "amount": str(amount),
                                "fx_rate_id": str(action_fx_id) if action_fx_id else None,
                            }
                        )
                applied_actions.append(str(action.id))
            base_price = bar.close_price * fx_rate
            positions.append(PositionValue(str(snapshot.instrument_id), quantity, base_price))
            cast_positions = input_details["positions"]
            if isinstance(cast_positions, list):
                cast_positions.append(
                    {
                        "instrument_id": str(snapshot.instrument_id),
                        "listing_id": str(listing.id),
                        "ticker": listing.ticker,
                        "bar_id": str(bar.id),
                        "bar_knowledge_at": bar.knowledge_at.isoformat(),
                        "currency": instrument.currency_code,
                        "fx_rate_id": str(fx_id) if fx_id else None,
                        "adjusted_quantity": str(quantity),
                        "corporate_action_ids": applied_actions,
                    }
                )
        cash_rows = (
            await self.session.execute(
                sa.select(CashSnapshot.currency, CashSnapshot.amount).where(
                    CashSnapshot.portfolio_version_id == version.id
                )
            )
        ).all()
        converted_cash: list[Decimal] = []
        for currency, amount in cash_rows:
            fx_rate, fx_id = await fx_multiplier(self.session, currency, portfolio.base_currency, as_of)
            converted = amount * fx_rate
            converted_cash.append(converted)
            cast_cash_rows = input_details["cash"]
            if isinstance(cast_cash_rows, list):
                cast_cash_rows.append(
                    {
                        "currency": currency,
                        "amount": str(amount),
                        "converted": str(converted),
                        "fx_rate_id": str(fx_id) if fx_id else None,
                    }
                )
        ledger = (
            await self.session.execute(
                sa.select(PortfolioLedgerEntry.entry_type, PortfolioLedgerEntry.amount).where(
                    PortfolioLedgerEntry.portfolio_id == portfolio.id,
                    PortfolioLedgerEntry.occurred_at <= as_of,
                    PortfolioLedgerEntry.entry_type.in_({"fee", "tax"}),
                )
            )
        ).all()
        fees = tuple(amount for entry_type, amount in ledger if entry_type == "fee")
        taxes = tuple(amount for entry_type, amount in ledger if entry_type == "tax")
        result = calculate_nav(tuple(positions), (*converted_cash, *corporate_action_cash), fees, taxes)
        gross_pnl = result.positions_value + sum(corporate_action_cash, start=Decimal(0)) - invested_cost
        net_pnl = gross_pnl - result.fees_value - result.taxes_value
        benchmark_value, benchmark_return, benchmark_details = await self._benchmark_performance(
            version.mandate_id, version.as_of, as_of, portfolio.base_currency
        )
        input_details["benchmark"] = benchmark_details
        revision = (
            await self.session.scalar(
                sa.select(sa.func.coalesce(sa.func.max(NavPublication.revision), 0) + 1).where(
                    NavPublication.portfolio_id == portfolio.id,
                    NavPublication.as_of == as_of,
                )
            )
        ) or 1
        publication = NavPublication(
            portfolio_id=portfolio.id,
            portfolio_version_id=version.id,
            as_of=as_of,
            revision=revision,
            methodology_version="nav-v2-pit-fx-actions",
            input_sha256=canonical_hash({"calculation_input_sha256": result.input_sha256, "provenance": input_details}),
            input_details=input_details,
            cash_value=result.cash_value,
            positions_value=result.positions_value,
            gross_pnl=gross_pnl,
            net_pnl=net_pnl,
            fees_value=result.fees_value,
            taxes_value=result.taxes_value,
            nav=result.nav,
            benchmark_value=benchmark_value,
            benchmark_return=benchmark_return,
            reconciled=result.reconciled,
            published_by=context.subject,
        )
        self.session.add(publication)
        await self.session.flush()
        return publication

    async def _benchmark_performance(
        self,
        mandate_id: UUID,
        start_at: datetime,
        as_of: datetime,
        base_currency: str,
    ) -> tuple[Decimal | None, Decimal | None, dict[str, object]]:
        mandate = await self.session.get(StrategyMandate, mandate_id)
        index = await self.session.get(MarketIndex, mandate.benchmark_index_id) if mandate is not None else None
        if index is None or index.instrument_id is None:
            return None, None, {"status": "unavailable", "reason": "benchmark instrument is not mapped"}
        start_bar = await latest_instrument_bar(self.session, index.instrument_id, start_at, as_of)
        end_bar = await latest_instrument_bar(self.session, index.instrument_id, as_of, as_of)
        if start_bar is None or end_bar is None or start_bar.close_price <= 0:
            return None, None, {"status": "unavailable", "reason": "benchmark prices are missing"}
        fx, fx_id = await fx_multiplier(self.session, index.currency_code, base_currency, as_of)
        return (
            end_bar.close_price * fx,
            end_bar.close_price / start_bar.close_price - Decimal(1),
            {
                "status": "available",
                "index_id": str(index.id),
                "instrument_id": str(index.instrument_id),
                "start_bar_id": str(start_bar.id),
                "end_bar_id": str(end_bar.id),
                "fx_rate_id": str(fx_id) if fx_id else None,
            },
        )

    async def list_nav_publications(self, portfolio_id: UUID, *, as_of: datetime | None = None) -> list[NavPublication]:
        stmt = (
            sa.select(NavPublication)
            .where(NavPublication.portfolio_id == portfolio_id)
            .order_by(NavPublication.as_of.desc(), NavPublication.revision.desc())
        )
        if as_of is not None:
            stmt = stmt.where(NavPublication.as_of <= as_of)
        return list((await self.session.scalars(stmt)).all())
