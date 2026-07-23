from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.agents import AuditLog
from database.models.instrument_master import Listing
from database.models.market_data import FxRate, MarketBar
from ia_investing.domain.identity import InstitutionalAccessContext


class PortfolioConcurrencyError(RuntimeError):
    pass


async def latest_instrument_bar(
    session: AsyncSession,
    instrument_id: UUID,
    price_cutoff: datetime,
    knowledge_cutoff: datetime,
) -> MarketBar | None:
    return (  # type: ignore[no-any-return]
        await session.execute(
            sa.select(MarketBar)
            .join(Listing, Listing.id == MarketBar.listing_id)
            .where(
                Listing.instrument_id == instrument_id,
                Listing.valid_from <= price_cutoff.date(),
                sa.or_(Listing.valid_to.is_(None), Listing.valid_to > price_cutoff.date()),
                MarketBar.bar_at <= price_cutoff,
                MarketBar.knowledge_at <= knowledge_cutoff,
            )
            .order_by(MarketBar.bar_at.desc(), MarketBar.knowledge_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


async def fx_multiplier(
    session: AsyncSession,
    source_currency: str,
    target_currency: str,
    as_of: datetime,
) -> tuple[Decimal, UUID | None]:
    if source_currency == target_currency:
        return Decimal(1), None
    direct = (
        await session.execute(
            sa.select(FxRate)
            .where(
                FxRate.base_currency == source_currency,
                FxRate.quote_currency == target_currency,
                FxRate.rate_at <= as_of,
                FxRate.knowledge_at <= as_of,
            )
            .order_by(FxRate.rate_at.desc(), FxRate.knowledge_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if direct is not None:
        return direct.rate, direct.id
    inverse = (
        await session.execute(
            sa.select(FxRate)
            .where(
                FxRate.base_currency == target_currency,
                FxRate.quote_currency == source_currency,
                FxRate.rate_at <= as_of,
                FxRate.knowledge_at <= as_of,
            )
            .order_by(FxRate.rate_at.desc(), FxRate.knowledge_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if inverse is None:
        raise ValueError(f"FX rate missing at as_of for {source_currency}/{target_currency}")
    return Decimal(1) / inverse.rate, inverse.id


def audit(
    session: AsyncSession,
    context: InstitutionalAccessContext,
    action: str,
    entity_type: str,
    entity_id: UUID,
    details: dict[str, object],
) -> None:
    session.add(
        AuditLog(
            actor_type="human",
            actor_id=context.subject,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            correlation_id=uuid4(),
            details={"organization_id": str(context.organization_id), **details},
        )
    )
