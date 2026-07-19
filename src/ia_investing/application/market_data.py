from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.market_data import (
    CorporateAction,
    FxRate,
    MarketBar,
    MarketQuote,
    TradingSession,
    YieldCurvePoint,
)
from ia_investing.application.financial_facts import require_aware


@dataclass(frozen=True, slots=True)
class SplitEvent:
    action_type: str
    ex_date: date
    ratio: Decimal
    knowledge_at: datetime


def split_adjustment_factor(events: list[SplitEvent], price_date: date, as_of: datetime) -> Decimal:
    """Return a PIT-safe factor using only actions known at ``as_of``."""
    require_aware(as_of, "as_of")
    factor = Decimal(1)
    for event in events:
        require_aware(event.knowledge_at, "event.knowledge_at")
        if event.knowledge_at > as_of or event.ex_date <= price_date or event.ex_date > as_of.date():
            continue
        if event.action_type == "split":
            factor /= event.ratio
        elif event.action_type == "reverse_split":
            factor *= event.ratio
    return factor


class MarketDataRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def bars_as_of(
        self,
        listing_id: UUID,
        start: datetime,
        end: datetime,
        as_of: datetime,
    ) -> list[MarketBar]:
        for name, value in (("start", start), ("end", end), ("as_of", as_of)):
            require_aware(value, name)
        rows = await self.session.execute(
            sa.select(MarketBar)
            .where(
                MarketBar.listing_id == listing_id,
                MarketBar.bar_at >= start,
                MarketBar.bar_at < end,
                MarketBar.knowledge_at <= as_of,
            )
            .distinct(MarketBar.bar_at)
            .order_by(MarketBar.bar_at, MarketBar.knowledge_at.desc())
        )
        return list(rows.scalars().all())

    async def corporate_actions_as_of(self, instrument_id: UUID, as_of: datetime) -> list[CorporateAction]:
        require_aware(as_of, "as_of")
        rows = await self.session.execute(
            sa.select(CorporateAction)
            .where(CorporateAction.instrument_id == instrument_id, CorporateAction.knowledge_at <= as_of)
            .order_by(CorporateAction.announcement_date, CorporateAction.knowledge_at)
        )
        return list(rows.scalars().all())

    async def latest_quote_as_of(self, listing_id: UUID, as_of: datetime) -> MarketQuote | None:
        require_aware(as_of, "as_of")
        return (
            await self.session.execute(
                sa.select(MarketQuote)
                .where(
                    MarketQuote.listing_id == listing_id,
                    MarketQuote.quoted_at <= as_of,
                    MarketQuote.knowledge_at <= as_of,
                )
                .order_by(MarketQuote.quoted_at.desc(), MarketQuote.knowledge_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()

    async def fx_rate_as_of(
        self,
        base_currency: str,
        quote_currency: str,
        as_of: datetime,
    ) -> FxRate | None:
        require_aware(as_of, "as_of")
        if base_currency == quote_currency:
            raise ValueError("FX pair must contain different currencies")
        return (
            await self.session.execute(
                sa.select(FxRate)
                .where(
                    FxRate.base_currency == base_currency,
                    FxRate.quote_currency == quote_currency,
                    FxRate.rate_at <= as_of,
                    FxRate.knowledge_at <= as_of,
                )
                .order_by(FxRate.rate_at.desc(), FxRate.knowledge_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()

    async def yield_curve_as_of(
        self,
        curve_code: str,
        as_of: datetime,
    ) -> list[YieldCurvePoint]:
        require_aware(as_of, "as_of")
        rows = await self.session.execute(
            sa.select(YieldCurvePoint)
            .where(
                YieldCurvePoint.curve_code == curve_code,
                YieldCurvePoint.observed_at <= as_of,
                YieldCurvePoint.knowledge_at <= as_of,
            )
            .distinct(YieldCurvePoint.tenor_days)
            .order_by(
                YieldCurvePoint.tenor_days,
                YieldCurvePoint.observed_at.desc(),
                YieldCurvePoint.knowledge_at.desc(),
            )
        )
        return list(rows.scalars().all())

    async def session_as_of(self, market_code: str, session_date: date, as_of: datetime) -> TradingSession | None:
        require_aware(as_of, "as_of")
        return (
            await self.session.execute(
                sa.select(TradingSession)
                .where(
                    TradingSession.market_code == market_code,
                    TradingSession.session_date == session_date,
                    TradingSession.knowledge_at <= as_of,
                )
                .order_by(TradingSession.knowledge_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
