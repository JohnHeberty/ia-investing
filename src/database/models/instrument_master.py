from __future__ import annotations

from datetime import date, datetime
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ExcludeConstraint
from sqlalchemy.orm import Mapped, mapped_column

from ._utils import utcnow
from .base import Base


class LegalEntity(Base):
    __tablename__ = "legal_entities"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    legal_name: Mapped[str] = mapped_column(sa.String(300))
    country_code: Mapped[str] = mapped_column(sa.String(2))
    tax_identifier: Mapped[str] = mapped_column(sa.String(32))
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=utcnow)

    __table_args__ = (
        sa.UniqueConstraint("country_code", "tax_identifier", name="uq_legal_entities_country_tax_id"),
        sa.CheckConstraint("country_code ~ '^[A-Z]{2}$'", name="country_code_format"),
    )


class Instrument(Base):
    __tablename__ = "instruments"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    issuer_id: Mapped[UUID] = mapped_column(sa.ForeignKey("issuers.id", ondelete="RESTRICT"), index=True)
    instrument_type: Mapped[str] = mapped_column(sa.String(30))
    share_class: Mapped[str | None] = mapped_column(sa.String(50))
    currency_code: Mapped[str] = mapped_column(sa.String(3), default="BRL")
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=utcnow)

    __table_args__ = (
        sa.CheckConstraint(
            "instrument_type IN ('common_share', 'preferred_share', 'unit', 'bdr', 'etf', 'fund', 'bond')",
            name="instrument_type_values",
        ),
        sa.CheckConstraint("currency_code ~ '^[A-Z]{3}$'", name="currency_code_format"),
    )


class Listing(Base):
    __tablename__ = "listings"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    instrument_id: Mapped[UUID] = mapped_column(sa.ForeignKey("instruments.id", ondelete="CASCADE"), index=True)
    exchange_code: Mapped[str] = mapped_column(sa.String(20))
    ticker: Mapped[str] = mapped_column(sa.String(20))
    market_segment: Mapped[str | None] = mapped_column(sa.String(50))
    valid_from: Mapped[date]
    valid_to: Mapped[date | None]
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=utcnow)

    __table_args__ = (
        sa.CheckConstraint("valid_to IS NULL OR valid_to > valid_from", name="valid_window"),
        ExcludeConstraint(
            ("exchange_code", "="),
            ("ticker", "="),
            (sa.text("daterange(valid_from, valid_to, '[)')"), "&&"),
            name="ex_listings_ticker_window",
            using="gist",
        ),
    )


class InstrumentIdentifier(Base):
    __tablename__ = "instrument_identifiers"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    instrument_id: Mapped[UUID] = mapped_column(sa.ForeignKey("instruments.id", ondelete="CASCADE"), index=True)
    identifier_type: Mapped[str] = mapped_column(sa.String(30))
    identifier_value: Mapped[str] = mapped_column(sa.String(100))
    valid_from: Mapped[date]
    valid_to: Mapped[date | None]

    __table_args__ = (
        sa.CheckConstraint("valid_to IS NULL OR valid_to > valid_from", name="valid_window"),
        ExcludeConstraint(
            ("identifier_type", "="),
            ("identifier_value", "="),
            (sa.text("daterange(valid_from, valid_to, '[)')"), "&&"),
            name="ex_instrument_identifiers_value_window",
            using="gist",
        ),
    )


class IssuerAlias(Base):
    __tablename__ = "issuer_aliases"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    issuer_id: Mapped[UUID] = mapped_column(sa.ForeignKey("issuers.id", ondelete="CASCADE"), index=True)
    alias: Mapped[str] = mapped_column(sa.String(300))
    alias_normalized: Mapped[str] = mapped_column(sa.String(300), index=True)
    valid_from: Mapped[date]
    valid_to: Mapped[date | None]

    __table_args__ = (
        sa.UniqueConstraint("issuer_id", "alias_normalized", "valid_from", name="uq_issuer_aliases_window_start"),
        sa.CheckConstraint("valid_to IS NULL OR valid_to > valid_from", name="valid_window"),
    )


class PeerRelationship(Base):
    __tablename__ = "peer_relationships"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    issuer_id: Mapped[UUID] = mapped_column(sa.ForeignKey("issuers.id", ondelete="CASCADE"), index=True)
    peer_issuer_id: Mapped[UUID] = mapped_column(sa.ForeignKey("issuers.id", ondelete="CASCADE"), index=True)
    rationale: Mapped[str] = mapped_column(sa.Text)
    valid_from: Mapped[date]
    valid_to: Mapped[date | None]

    __table_args__ = (
        sa.UniqueConstraint("issuer_id", "peer_issuer_id", "valid_from", name="uq_peer_relationships_window_start"),
        sa.CheckConstraint("issuer_id <> peer_issuer_id", name="different_issuers"),
        sa.CheckConstraint("valid_to IS NULL OR valid_to > valid_from", name="valid_window"),
    )
