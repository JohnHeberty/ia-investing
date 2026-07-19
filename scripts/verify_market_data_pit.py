from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import sqlalchemy as sa

from database.core import session_scope
from database.models.catalog import Issuer
from database.models.data_foundation import SourceObjectVersion
from database.models.instrument_master import Instrument, Listing
from database.models.market_data import FxRate, MarketQuote, YieldCurvePoint
from ia_investing.application.market_data import MarketDataRepository


async def verify() -> None:
    async with session_scope() as session:
        issuer_id = await session.scalar(sa.select(Issuer.id).order_by(Issuer.id).limit(1))
        source_version_id = await session.scalar(
            sa.select(SourceObjectVersion.id).order_by(SourceObjectVersion.id).limit(1)
        )
        if issuer_id is None or source_version_id is None:
            raise RuntimeError("verification requires one issuer and source object version")
        instrument = Instrument(
            issuer_id=issuer_id,
            instrument_type="common_share",
            share_class="ON",
            currency_code="BRL",
            is_active=True,
        )
        session.add(instrument)
        await session.flush()
        listing = Listing(
            instrument_id=instrument.id,
            exchange_code="B3",
            ticker=f"PIT{instrument.id.hex[:4].upper()}",
            market_segment="verification",
            valid_from=date(2020, 1, 1),
            valid_to=None,
        )
        session.add(listing)
        await session.flush()
        observed = datetime(2026, 7, 18, 18, tzinfo=UTC)
        cutoff = observed + timedelta(hours=1)
        future_knowledge = cutoff + timedelta(hours=1)
        session.add_all(
            [
                MarketQuote(
                    listing_id=listing.id,
                    quoted_at=observed,
                    bid_price=Decimal("99"),
                    ask_price=Decimal("101"),
                    last_price=Decimal("100"),
                    source_object_version_id=source_version_id,
                    knowledge_at=observed,
                ),
                MarketQuote(
                    listing_id=listing.id,
                    quoted_at=observed,
                    bid_price=Decimal("109"),
                    ask_price=Decimal("111"),
                    last_price=Decimal("110"),
                    source_object_version_id=source_version_id,
                    knowledge_at=future_knowledge,
                ),
                FxRate(
                    base_currency="USD",
                    quote_currency="BRL",
                    rate_at=observed,
                    rate=Decimal("5.40"),
                    source_object_version_id=source_version_id,
                    knowledge_at=observed,
                ),
                FxRate(
                    base_currency="USD",
                    quote_currency="BRL",
                    rate_at=observed,
                    rate=Decimal("5.50"),
                    source_object_version_id=source_version_id,
                    knowledge_at=future_knowledge,
                ),
                YieldCurvePoint(
                    curve_code="DI1",
                    currency_code="BRL",
                    tenor_days=252,
                    observed_at=observed,
                    annual_rate=Decimal("0.12"),
                    source_object_version_id=source_version_id,
                    knowledge_at=observed,
                ),
                YieldCurvePoint(
                    curve_code="DI1",
                    currency_code="BRL",
                    tenor_days=252,
                    observed_at=observed,
                    annual_rate=Decimal("0.13"),
                    source_object_version_id=source_version_id,
                    knowledge_at=future_knowledge,
                ),
                YieldCurvePoint(
                    curve_code="DI1",
                    currency_code="BRL",
                    tenor_days=504,
                    observed_at=observed,
                    annual_rate=Decimal("0.11"),
                    source_object_version_id=source_version_id,
                    knowledge_at=observed,
                ),
            ]
        )
        await session.flush()
        repository = MarketDataRepository(session)
        quote = await repository.latest_quote_as_of(listing.id, cutoff)
        fx = await repository.fx_rate_as_of("USD", "BRL", cutoff)
        curve = await repository.yield_curve_as_of("DI1", cutoff)
        if quote is None or quote.last_price != Decimal("100"):
            raise AssertionError("quote query leaked a future revision")
        if fx is None or fx.rate != Decimal("5.40"):
            raise AssertionError("FX query leaked a future revision")
        if {item.tenor_days: item.annual_rate for item in curve} != {
            252: Decimal("0.12"),
            504: Decimal("0.11"),
        }:
            raise AssertionError("yield curve query leaked a future revision")
        print(
            "market-data-pit-ok",
            f"listing_id={listing.id}",
            f"quote={quote.last_price}",
            f"fx={fx.rate}",
            f"curve_points={len(curve)}",
        )


if __name__ == "__main__":
    asyncio.run(verify())
