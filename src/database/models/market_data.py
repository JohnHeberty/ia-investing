from __future__ import annotations

from datetime import UTC, date, datetime, time
from decimal import Decimal
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class TradingSession(Base):
    __tablename__ = "trading_sessions"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    market_code: Mapped[str] = mapped_column(sa.String(20))
    session_date: Mapped[date]
    is_open: Mapped[bool]
    opens_at: Mapped[time | None] = mapped_column(sa.Time(timezone=True))
    closes_at: Mapped[time | None] = mapped_column(sa.Time(timezone=True))
    reason: Mapped[str | None] = mapped_column(sa.String(200))
    calendar_version: Mapped[str] = mapped_column(sa.String(50))
    knowledge_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True))

    __table_args__ = (
        sa.UniqueConstraint("market_code", "session_date", "calendar_version", name="uq_trading_sessions_version"),
        sa.CheckConstraint(
            "(is_open AND opens_at IS NOT NULL AND closes_at IS NOT NULL) OR "
            "(NOT is_open AND opens_at IS NULL AND closes_at IS NULL)",
            name="hours_match_open_status",
        ),
    )


class MarketBar(Base):
    __tablename__ = "market_bars"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    listing_id: Mapped[UUID] = mapped_column(sa.ForeignKey("listings.id", ondelete="CASCADE"), index=True)
    interval: Mapped[str] = mapped_column(sa.String(10))
    bar_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True))
    open_price: Mapped[Decimal] = mapped_column(sa.Numeric(20, 8))
    high_price: Mapped[Decimal] = mapped_column(sa.Numeric(20, 8))
    low_price: Mapped[Decimal] = mapped_column(sa.Numeric(20, 8))
    close_price: Mapped[Decimal] = mapped_column(sa.Numeric(20, 8))
    volume: Mapped[int]
    source_object_version_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("source_object_versions.id", ondelete="RESTRICT")
    )
    knowledge_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), index=True)

    __table_args__ = (
        sa.UniqueConstraint("listing_id", "interval", "bar_at", "knowledge_at", name="uq_market_bars_pit"),
        sa.CheckConstraint("high_price >= low_price", name="valid_high_low"),
        sa.CheckConstraint("volume >= 0", name="nonnegative_volume"),
    )


class MarketQuote(Base):
    __tablename__ = "market_quotes"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    listing_id: Mapped[UUID] = mapped_column(sa.ForeignKey("listings.id", ondelete="CASCADE"), index=True)
    quoted_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), index=True)
    bid_price: Mapped[Decimal | None] = mapped_column(sa.Numeric(20, 8))
    ask_price: Mapped[Decimal | None] = mapped_column(sa.Numeric(20, 8))
    last_price: Mapped[Decimal | None] = mapped_column(sa.Numeric(20, 8))
    source_object_version_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("source_object_versions.id", ondelete="RESTRICT")
    )
    knowledge_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), index=True)

    __table_args__ = (
        sa.UniqueConstraint("listing_id", "quoted_at", "knowledge_at", name="uq_market_quotes_pit"),
        sa.CheckConstraint(
            "bid_price IS NOT NULL OR ask_price IS NOT NULL OR last_price IS NOT NULL",
            name="at_least_one_price",
        ),
        sa.CheckConstraint(
            "bid_price IS NULL OR ask_price IS NULL OR bid_price <= ask_price",
            name="valid_spread",
        ),
    )


class FxRate(Base):
    __tablename__ = "fx_rates"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    base_currency: Mapped[str] = mapped_column(sa.String(3))
    quote_currency: Mapped[str] = mapped_column(sa.String(3))
    rate_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), index=True)
    rate: Mapped[Decimal] = mapped_column(sa.Numeric(28, 12))
    source_object_version_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("source_object_versions.id", ondelete="RESTRICT")
    )
    knowledge_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), index=True)

    __table_args__ = (
        sa.UniqueConstraint("base_currency", "quote_currency", "rate_at", "knowledge_at", name="uq_fx_rates_pit"),
        sa.CheckConstraint("base_currency ~ '^[A-Z]{3}$'", name="base_currency_format"),
        sa.CheckConstraint("quote_currency ~ '^[A-Z]{3}$'", name="quote_currency_format"),
        sa.CheckConstraint("base_currency <> quote_currency", name="different_currencies"),
        sa.CheckConstraint("rate > 0", name="positive_rate"),
    )


class YieldCurvePoint(Base):
    __tablename__ = "yield_curve_points"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    curve_code: Mapped[str] = mapped_column(sa.String(50))
    currency_code: Mapped[str] = mapped_column(sa.String(3))
    tenor_days: Mapped[int]
    observed_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), index=True)
    annual_rate: Mapped[Decimal] = mapped_column(sa.Numeric(18, 12))
    source_object_version_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("source_object_versions.id", ondelete="RESTRICT")
    )
    knowledge_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), index=True)

    __table_args__ = (
        sa.UniqueConstraint(
            "curve_code", "tenor_days", "observed_at", "knowledge_at", name="uq_yield_curve_points_pit"
        ),
        sa.CheckConstraint("currency_code ~ '^[A-Z]{3}$'", name="currency_code_format"),
        sa.CheckConstraint("tenor_days > 0", name="positive_tenor"),
        sa.CheckConstraint("annual_rate > -1", name="supported_rate_domain"),
    )


class CorporateAction(Base):
    __tablename__ = "corporate_actions"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    instrument_id: Mapped[UUID] = mapped_column(sa.ForeignKey("instruments.id", ondelete="CASCADE"), index=True)
    action_type: Mapped[str] = mapped_column(sa.String(30))
    announcement_date: Mapped[date]
    ex_date: Mapped[date | None]
    record_date: Mapped[date | None]
    payment_date: Mapped[date | None]
    amount_per_unit: Mapped[Decimal | None] = mapped_column(sa.Numeric(20, 8))
    ratio: Mapped[Decimal | None] = mapped_column(sa.Numeric(20, 10))
    currency_code: Mapped[str | None] = mapped_column(sa.String(3))
    source_object_version_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("source_object_versions.id", ondelete="RESTRICT")
    )
    knowledge_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True))

    __table_args__ = (
        sa.UniqueConstraint(
            "instrument_id",
            "action_type",
            "announcement_date",
            "ex_date",
            "knowledge_at",
            name="uq_corporate_actions_pit",
        ),
        sa.CheckConstraint(
            "action_type IN ('dividend', 'jcp', 'split', 'reverse_split', 'subscription', 'buyback', 'bonus')",
            name="action_type_values",
        ),
        sa.CheckConstraint("amount_per_unit IS NULL OR amount_per_unit >= 0", name="nonnegative_amount"),
        sa.CheckConstraint("ratio IS NULL OR ratio > 0", name="positive_ratio"),
    )


class MarketIndex(Base):
    __tablename__ = "market_indices"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    code: Mapped[str] = mapped_column(sa.String(30), unique=True)
    name: Mapped[str] = mapped_column(sa.String(200))
    provider: Mapped[str] = mapped_column(sa.String(100))
    currency_code: Mapped[str] = mapped_column(sa.String(3))
    instrument_id: Mapped[UUID | None] = mapped_column(sa.ForeignKey("instruments.id", ondelete="RESTRICT"))


class IndexConstituent(Base):
    __tablename__ = "index_constituents"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    index_id: Mapped[UUID] = mapped_column(sa.ForeignKey("market_indices.id", ondelete="CASCADE"), index=True)
    instrument_id: Mapped[UUID] = mapped_column(sa.ForeignKey("instruments.id", ondelete="CASCADE"), index=True)
    weight: Mapped[Decimal | None] = mapped_column(sa.Numeric(10, 8))
    valid_from: Mapped[date]
    valid_to: Mapped[date | None]
    knowledge_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True))

    __table_args__ = (
        sa.UniqueConstraint(
            "index_id",
            "instrument_id",
            "valid_from",
            "knowledge_at",
            name="uq_index_constituents_pit",
        ),
        sa.CheckConstraint("weight IS NULL OR weight BETWEEN 0 AND 1", name="weight_range"),
        sa.CheckConstraint("valid_to IS NULL OR valid_to > valid_from", name="valid_window"),
    )
