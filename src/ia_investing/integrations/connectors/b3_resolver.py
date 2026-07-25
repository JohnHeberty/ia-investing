from __future__ import annotations

import logging
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select

from connectors.b3._cotahist import get_cotahist_year
from connectors.base import HttpClient
from database.models.instrument_master import Instrument, Listing
from ia_investing.integrations.connectors.models import B3ListingProfile
from ia_investing.platform.database.runtime import DatabaseRuntime

logger = logging.getLogger(__name__)


class B3Resolver:
    def __init__(self, db: DatabaseRuntime, client: HttpClient | None = None) -> None:
        self._db = db
        self._client = client or HttpClient(timeout=60.0)

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

            profile = B3ListingProfile(
                ticker=str(row.ticker),
                exchange=str(row.exchange_code),
                market_segment=str(row.market_segment) if row.market_segment else None,
                listing_status="active",
            )

        now = datetime.now(UTC)
        try:
            trades = await get_cotahist_year(
                year=now.year,
                ticker=ticker.upper().strip(),
                client=self._client,
            )
        except Exception as exc:
            logger.warning("COTAHIST fetch failed for %s: %s", ticker, exc)
            return profile

        if not trades:
            return profile

        last_trade = trades[-1]
        profile.closing_price = Decimal(str(last_trade.preco_ultimo)).quantize(Decimal("0.01"))
        profile.last_trade_date = last_trade.trade_date

        recent = trades[-30:] if len(trades) >= 30 else trades
        avg_volume = sum(t.qtd_titulos_negociados for t in recent) / len(recent)
        profile.average_volume_30d = Decimal(str(int(avg_volume)))

        return profile
