from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.instrument_master import Instrument, Listing
from database.models.market_data import CorporateAction, FxRate, MarketBar, MarketIndex
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


@dataclass(frozen=True)
class MarketSnapshotData:
    """Batch-loaded market data for NAV calculation."""

    instruments: dict[UUID, Instrument]
    price_lookup: dict[UUID, tuple[UUID, str, UUID, Decimal, datetime]]
    actions_by_instrument: dict[UUID, list[CorporateAction]]
    fx_rates: dict[tuple[str, str], tuple[Decimal, UUID | None]]


class NavService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def publish_nav(
        self,
        version_id: UUID,
        as_of: datetime,
        context: InstitutionalAccessContext,
    ) -> NavPublication:
        version, portfolio = await self._resolve_portfolio(version_id, context)
        snapshots = await self._load_snapshots(version.id)
        instrument_ids = tuple(s.instrument_id for s in snapshots)
        market = await self._load_market_data(instrument_ids, snapshots, as_of, portfolio.base_currency)
        positions, invested_cost, ca_details = self._valuate_positions(snapshots, market, portfolio.base_currency)
        cash_values, cash_details, fees, taxes = await self._prepare_cash_and_ledger(
            version.id, portfolio.id, market.fx_rates, portfolio.base_currency, as_of
        )
        return await self._publish_result(
            version,
            portfolio,
            as_of,
            context,
            positions,
            cash_values,
            cash_details,
            ca_details,
            corporate_action_cash=ca_details,
            fees=fees,
            taxes=taxes,
            invested_cost=invested_cost,
        )

    async def _resolve_portfolio(
        self, version_id: UUID, context: InstitutionalAccessContext
    ) -> tuple[InstitutionalPortfolioVersion, ModelPortfolio]:
        version = await self.session.get(InstitutionalPortfolioVersion, version_id)
        if version is None:
            raise LookupError("portfolio version not found")
        portfolio = await self.session.get(ModelPortfolio, version.portfolio_id)
        if portfolio is None:
            raise RuntimeError("portfolio version references missing portfolio")
        authorize(context, "nav:publish", ResourceAttributes(portfolio.organization_id, portfolio.owner_team_id))
        return version, portfolio

    async def _load_snapshots(self, version_id: UUID) -> list[PositionSnapshot]:
        return list(
            (
                await self.session.execute(
                    sa.select(PositionSnapshot).where(PositionSnapshot.portfolio_version_id == version_id)
                )
            ).scalars()
        )

    async def _load_market_data(
        self,
        instrument_ids: tuple[UUID, ...],
        snapshots: list[PositionSnapshot],
        as_of: datetime,
        base_currency: str,
    ) -> MarketSnapshotData:
        instruments = {
            inst.id: inst
            for inst in (
                await self.session.scalars(sa.select(Instrument).where(Instrument.id.in_(instrument_ids)))
            ).all()
        }

        price_rows = (
            await self.session.execute(
                sa.select(
                    Listing.instrument_id,
                    Listing.id.label("listing_id"),
                    Listing.ticker,
                    MarketBar.id.label("bar_id"),
                    MarketBar.close_price,
                    MarketBar.knowledge_at.label("bar_knowledge_at"),
                )
                .distinct_on(Listing.instrument_id)
                .join(MarketBar, MarketBar.listing_id == Listing.id)
                .where(
                    Listing.instrument_id.in_(instrument_ids),
                    Listing.valid_from <= as_of.date(),
                    sa.or_(Listing.valid_to.is_(None), Listing.valid_to > as_of.date()),
                    MarketBar.bar_at <= as_of,
                    MarketBar.knowledge_at <= as_of,
                )
                .order_by(Listing.instrument_id, MarketBar.bar_at.desc(), MarketBar.knowledge_at.desc())
            )
        ).all()
        price_lookup: dict[UUID, tuple[UUID, str, UUID, Decimal, datetime]] = {}
        for row in price_rows:
            price_lookup[row.instrument_id] = (
                row.listing_id,
                row.ticker,
                row.bar_id,
                row.close_price,
                row.bar_knowledge_at,
            )

        min_as_of_date = min(s.as_of.date() for s in snapshots)
        corporate_action_rows = list(
            (
                await self.session.scalars(
                    sa.select(CorporateAction)
                    .where(
                        CorporateAction.instrument_id.in_(instrument_ids),
                        CorporateAction.knowledge_at <= as_of,
                        CorporateAction.ex_date.is_not(None),
                        CorporateAction.ex_date > min_as_of_date,
                        CorporateAction.ex_date <= as_of.date(),
                    )
                    .order_by(CorporateAction.ex_date, CorporateAction.knowledge_at)
                )
            ).all()
        )
        actions_by_instrument: dict[UUID, list[CorporateAction]] = {}
        for action in corporate_action_rows:
            actions_by_instrument.setdefault(action.instrument_id, []).append(action)

        fx_rates = await self._resolve_fx_rates(instruments, corporate_action_rows, base_currency, as_of)

        return MarketSnapshotData(
            instruments=instruments,
            price_lookup=price_lookup,
            actions_by_instrument=actions_by_instrument,
            fx_rates=fx_rates,
        )

    async def _resolve_fx_rates(
        self,
        instruments: dict[UUID, Instrument],
        corporate_actions: list[CorporateAction],
        target_currency: str,
        as_of: datetime,
    ) -> dict[tuple[str, str], tuple[Decimal, UUID | None]]:
        currency_pairs: set[tuple[str, str]] = set()
        for inst in instruments.values():
            if inst.currency_code != target_currency:
                currency_pairs.add((inst.currency_code, target_currency))
        for action in corporate_actions:
            inst = instruments.get(action.instrument_id)
            action_currency = action.currency_code or (inst.currency_code if inst else None)
            if action_currency and action_currency != target_currency:
                currency_pairs.add((action_currency, target_currency))

        all_fx_rates: dict[tuple[str, str], tuple[Decimal, UUID | None]] = {}
        if not currency_pairs:
            return all_fx_rates

        all_sources = list({p[0] for p in currency_pairs})
        direct_rows = (
            (
                await self.session.execute(
                    sa.select(FxRate)
                    .where(
                        FxRate.base_currency.in_(all_sources),
                        FxRate.quote_currency == target_currency,
                        FxRate.rate_at <= as_of,
                        FxRate.knowledge_at <= as_of,
                    )
                    .distinct_on(FxRate.base_currency)
                    .order_by(FxRate.base_currency, FxRate.rate_at.desc(), FxRate.knowledge_at.desc())
                )
            )
            .scalars()
            .all()
        )
        found_sources: set[str] = set()
        for rate in direct_rows:
            all_fx_rates[(rate.base_currency, target_currency)] = (rate.rate, rate.id)
            found_sources.add(rate.base_currency)

        missing = [s for s in all_sources if s not in found_sources]
        if missing:
            inverse_rows = (
                (
                    await self.session.execute(
                        sa.select(FxRate)
                        .where(
                            FxRate.base_currency == target_currency,
                            FxRate.quote_currency.in_(missing),
                            FxRate.rate_at <= as_of,
                            FxRate.knowledge_at <= as_of,
                        )
                        .distinct_on(FxRate.quote_currency)
                        .order_by(FxRate.quote_currency, FxRate.rate_at.desc(), FxRate.knowledge_at.desc())
                    )
                )
                .scalars()
                .all()
            )
            for rate in inverse_rows:
                all_fx_rates[(rate.quote_currency, target_currency)] = (Decimal(1) / rate.rate, rate.id)

        return all_fx_rates

    def _valuate_positions(
        self,
        snapshots: list[PositionSnapshot],
        market: MarketSnapshotData,
        base_currency: str,
    ) -> tuple[list[PositionValue], Decimal, list[dict[str, object]]]:
        def _get_fx(source: str, target: str) -> tuple[Decimal, UUID | None]:
            if source == target:
                return Decimal(1), None
            result = market.fx_rates.get((source, target))
            if result is None:
                raise ValueError(f"FX rate missing for {source}/{target}")
            return result

        positions: list[PositionValue] = []
        input_details: list[dict[str, object]] = []
        corporate_action_cash: list[Decimal] = []
        invested_cost = Decimal(0)

        for snapshot in snapshots:
            price_info = market.price_lookup.get(snapshot.instrument_id)
            if price_info is None:
                raise ValueError(f"price missing at as_of for instrument {snapshot.instrument_id}")
            listing_id, ticker, bar_id, close_price, bar_knowledge_at = price_info
            instrument = market.instruments.get(snapshot.instrument_id)
            if instrument is None:
                raise RuntimeError("position references missing instrument")

            fx_rate, fx_id = _get_fx(instrument.currency_code, base_currency)
            invested_cost += snapshot.quantity * snapshot.cost_basis * fx_rate
            quantity = snapshot.quantity
            snapshot_as_of_date = snapshot.as_of.date()
            actions = [
                a
                for a in market.actions_by_instrument.get(snapshot.instrument_id, [])
                if a.ex_date > snapshot_as_of_date
            ]

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
                    action_fx, action_fx_id = _get_fx(action_currency, base_currency)
                    amount = quantity * action.amount_per_unit * action_fx
                    corporate_action_cash.append(amount)
                    input_details.append(
                        {
                            "type": "corporate_action_cash",
                            "action_id": str(action.id),
                            "amount": str(amount),
                            "fx_rate_id": str(action_fx_id) if action_fx_id else None,
                        }
                    )
                applied_actions.append(str(action.id))

            base_price = close_price * fx_rate
            positions.append(PositionValue(str(snapshot.instrument_id), quantity, base_price))
            input_details.append(
                {
                    "type": "position",
                    "instrument_id": str(snapshot.instrument_id),
                    "listing_id": str(listing_id),
                    "ticker": ticker,
                    "bar_id": str(bar_id),
                    "bar_knowledge_at": bar_knowledge_at.isoformat(),
                    "currency": instrument.currency_code,
                    "fx_rate_id": str(fx_id) if fx_id else None,
                    "adjusted_quantity": str(quantity),
                    "corporate_action_ids": applied_actions,
                }
            )

        return positions, invested_cost, corporate_action_cash

    async def _prepare_cash_and_ledger(
        self,
        version_id: UUID,
        portfolio_id: UUID,
        fx_rates: dict[tuple[str, str], tuple[Decimal, UUID | None]],
        base_currency: str,
        as_of: datetime,
    ) -> tuple[list[Decimal], list[dict[str, object]], tuple[Decimal, ...], tuple[Decimal, ...]]:
        def _get_fx(source: str, target: str) -> tuple[Decimal, UUID | None]:
            if source == target:
                return Decimal(1), None
            result = fx_rates.get((source, target))
            if result is None:
                raise ValueError(f"FX rate missing for {source}/{target}")
            return result

        cash_rows = (
            await self.session.execute(
                sa.select(CashSnapshot.currency, CashSnapshot.amount).where(
                    CashSnapshot.portfolio_version_id == version_id
                )
            )
        ).all()
        converted_cash: list[Decimal] = []
        cash_details: list[dict[str, object]] = []
        for currency, amount in cash_rows:
            fx_rate, fx_id = _get_fx(currency, base_currency)
            converted = amount * fx_rate
            converted_cash.append(converted)
            cash_details.append(
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
                    PortfolioLedgerEntry.portfolio_id == portfolio_id,
                    PortfolioLedgerEntry.occurred_at <= as_of,
                    PortfolioLedgerEntry.entry_type.in_({"fee", "tax"}),
                )
            )
        ).all()
        fees = tuple(amount for entry_type, amount in ledger if entry_type == "fee")
        taxes = tuple(amount for entry_type, amount in ledger if entry_type == "tax")

        return converted_cash, cash_details, fees, taxes

    async def _publish_result(
        self,
        version: InstitutionalPortfolioVersion,
        portfolio: ModelPortfolio,
        as_of: datetime,
        context: InstitutionalAccessContext,
        positions: list[PositionValue],
        cash_values: list[Decimal],
        cash_details: list[dict[str, object]],
        ca_details: list[Decimal],
        *,
        corporate_action_cash: list[Decimal],
        fees: tuple[Decimal, ...],
        taxes: tuple[Decimal, ...],
        invested_cost: Decimal,
    ) -> NavPublication:
        result = calculate_nav(tuple(positions), (*cash_values, *corporate_action_cash), fees, taxes)
        gross_pnl = result.positions_value + sum(corporate_action_cash, start=Decimal(0)) - invested_cost
        net_pnl = gross_pnl - result.fees_value - result.taxes_value
        benchmark_value, benchmark_return, benchmark_details = await self._benchmark_performance(
            version.mandate_id, version.as_of, as_of, portfolio.base_currency
        )
        input_details: dict[str, object] = {
            "positions": [d for d in cash_details if d.get("type") == "position"],
            "cash": [d for d in cash_details if d.get("type") != "position"],
            "corporate_action_cash": [{"amount": str(a)} for a in corporate_action_cash],
            "benchmark": benchmark_details,
        }
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
