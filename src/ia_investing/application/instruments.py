from __future__ import annotations

import re
import unicodedata
from datetime import date
from typing import Literal
from uuid import UUID

import sqlalchemy as sa
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.catalog import Issuer
from database.models.instrument_master import Instrument, InstrumentIdentifier, IssuerAlias, Listing


class AmbiguousInstrumentError(ValueError):
    pass


class InstrumentResolutionV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    resolution_type: Literal["listing", "identifier", "issuer"]
    issuer_id: UUID
    issuer_name: str
    instrument_id: UUID | None = None
    listing_id: UUID | None = None
    ticker: str | None = None
    as_of: date


def normalize_alias(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    ascii_value = "".join(character for character in decomposed if not unicodedata.combining(character))
    return re.sub(r"\s+", " ", ascii_value.strip().casefold())


def _active_window(
    model: type[Listing] | type[InstrumentIdentifier] | type[IssuerAlias],
    as_of: date,
) -> sa.ColumnElement[bool]:
    return sa.and_(model.valid_from <= as_of, sa.or_(model.valid_to.is_(None), model.valid_to > as_of))


class InstrumentMasterService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def resolve(self, query: str, as_of: date) -> InstrumentResolutionV1 | None:
        normalized = normalize_alias(query)
        ticker = query.strip().upper()
        listing_rows = (
            await self.session.execute(
                sa.select(Listing, Instrument, Issuer)
                .join(Instrument, Instrument.id == Listing.instrument_id)
                .join(Issuer, Issuer.id == Instrument.issuer_id)
                .where(sa.func.upper(Listing.ticker) == ticker, _active_window(Listing, as_of))
            )
        ).all()
        if len(listing_rows) > 1:
            raise AmbiguousInstrumentError("ticker resolves to multiple active listings")
        if listing_rows:
            listing, instrument, issuer = listing_rows[0]
            return InstrumentResolutionV1(
                resolution_type="listing",
                issuer_id=issuer.id,
                issuer_name=issuer.name_pt,
                instrument_id=instrument.id,
                listing_id=listing.id,
                ticker=listing.ticker,
                as_of=as_of,
            )

        identifier_rows = (
            await self.session.execute(
                sa.select(InstrumentIdentifier, Instrument, Issuer)
                .join(Instrument, Instrument.id == InstrumentIdentifier.instrument_id)
                .join(Issuer, Issuer.id == Instrument.issuer_id)
                .where(
                    sa.func.upper(InstrumentIdentifier.identifier_value) == ticker,
                    _active_window(InstrumentIdentifier, as_of),
                )
            )
        ).all()
        if len(identifier_rows) > 1:
            raise AmbiguousInstrumentError("identifier resolves to multiple active instruments")
        if identifier_rows:
            _identifier, instrument, issuer = identifier_rows[0]
            return InstrumentResolutionV1(
                resolution_type="identifier",
                issuer_id=issuer.id,
                issuer_name=issuer.name_pt,
                instrument_id=instrument.id,
                as_of=as_of,
            )

        digits = re.sub(r"\D", "", query)
        issuer_conditions = [Issuer.name_pt.ilike(query.strip())]
        if len(digits) == 14:
            issuer_conditions.append(Issuer.cnpj == digits)
        issuer_rows = (
            (
                await self.session.execute(
                    sa.select(Issuer)
                    .outerjoin(IssuerAlias, IssuerAlias.issuer_id == Issuer.id)
                    .where(
                        sa.or_(
                            *issuer_conditions,
                            sa.and_(
                                IssuerAlias.alias_normalized == normalized,
                                _active_window(IssuerAlias, as_of),
                            ),
                        )
                    )
                )
            )
            .scalars()
            .unique()
            .all()
        )
        if len(issuer_rows) > 1:
            raise AmbiguousInstrumentError("name or alias resolves to multiple issuers")
        if not issuer_rows:
            return None
        issuer = issuer_rows[0]
        return InstrumentResolutionV1(
            resolution_type="issuer",
            issuer_id=issuer.id,
            issuer_name=issuer.name_pt,
            as_of=as_of,
        )
