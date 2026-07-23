from __future__ import annotations

from datetime import date as DateType
from decimal import Decimal

from sqlalchemy import select

from ia_investing.database.models.instrument_master import Instrument, Listing
from ia_investing.integrations.connectors.models import B3ListingProfile
from ia_investing.platform.database.runtime import DatabaseRuntime


class B3Resolver:
    def __init__(self, db: DatabaseRuntime) -> None:
        self._db = db

    async def lookup_by_ticker(self, ticker: str) -> B3ListingProfile | None:
        async with self._db.session() as session:
            row = (
                await session.execute(
                    select(
                        Listing.ticker,
                        Listing.exchange_code,
                        Listing.market_segment,
                    )
                    .select_from(Listing)
                    .join(Instrument, Listing.instrument_id == Instrument.id)
                    .where(
                        Listing.ticker == ticker.upper().strip(),
                        Listing.valid_to.is_(None),
                        Instrument.is_active.is_(True),
                    )
                )
            ).one_or_none()

            if row is None:
                return None

            return B3ListingProfile(
                ticker=str(row.ticker),
                exchange=str(row.exchange_code),
                market_segment=str(row.market_segment) if row.market_segment else None,
                listing_status="active",
                average_volume_30d=Decimal(0),
                closing_price=None,
                last_trade_date=None,
            )
