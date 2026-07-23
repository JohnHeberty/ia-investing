from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.orm import Mapped, mapped_column

from ._utils import utcnow
from .base import Base


class Sector(Base):
    __tablename__ = "sectors"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name_pt: Mapped[str] = mapped_column(sa.String(100), nullable=False)
    name_en: Mapped[str | None] = mapped_column(sa.String(100))
    code_anbima: Mapped[str | None] = mapped_column(sa.String(20))
    created_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), default=utcnow)

    industries = sa.orm.relationship("Industry", back_populates="sector")

    def __repr__(self) -> str:
        return f"Sector(name_pt={self.name_pt!r}, code_anbima={self.code_anbima!r})"


class Industry(Base):
    __tablename__ = "industries"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name_pt: Mapped[str] = mapped_column(sa.String(100), nullable=False)
    name_en: Mapped[str | None] = mapped_column(sa.String(100))
    sector_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("sectors.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), default=utcnow)

    sector = sa.orm.relationship("Sector", back_populates="industries")
    issuers = sa.orm.relationship("Issuer", back_populates="industry")

    def __repr__(self) -> str:
        return f"Industry(name_pt={self.name_pt!r})"


class Issuer(Base):
    __tablename__ = "issuers"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name_pt: Mapped[str] = mapped_column(sa.String(200), nullable=False)
    cnpj: Mapped[str | None] = mapped_column(sa.String(14), unique=True, index=True)
    cvm_code: Mapped[int | None] = mapped_column(sa.Integer, unique=True, index=True)
    industry_id: Mapped[UUID | None] = mapped_column(
        sa.ForeignKey("industries.id", ondelete="SET NULL"),
    )
    website_ri_url: Mapped[str | None] = mapped_column(sa.Text)
    is_active: Mapped[bool | None] = mapped_column(sa.Boolean, default=True)

    created_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
    )

    tickers = sa.orm.relationship("Ticker", back_populates="issuer")
    industry = sa.orm.relationship("Industry", back_populates="issuers")

    def __repr__(self) -> str:
        return f"Issuer(name_pt={self.name_pt!r}, cnpj={self.cnpj!r})"


class Ticker(Base):
    __tablename__ = "tickers"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    symbol: Mapped[str] = mapped_column(sa.String(10), nullable=False)
    issuer_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("issuers.id", ondelete="CASCADE"),
        nullable=False,
    )
    market_segment: Mapped[str | None] = mapped_column(sa.String(20))  # "BOVESPA", "SADR" (Novo Mercado), etc.
    listing_date: Mapped[date | None] = mapped_column(sa.Date)
    delisting_date: Mapped[date | None] = mapped_column(sa.Date, index=True)

    created_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), default=utcnow)

    issuer = sa.orm.relationship("Issuer", back_populates="tickers")

    __table_args__ = (sa.UniqueConstraint("symbol", "issuer_id"),)

    def __repr__(self) -> str:
        return f"Ticker(symbol={self.symbol!r}, market_segment={self.market_segment!r})"


class MarketPrice(Base):
    """Cotações diárias históricas."""

    __tablename__ = "market_prices"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    ticker_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("tickers.id", ondelete="CASCADE"),
        nullable=False,
    )
    trade_date: Mapped[date] = mapped_column(sa.Date, nullable=False)
    open_price: Mapped[Decimal | None] = mapped_column(sa.Numeric(14, 6))
    high_price: Mapped[Decimal | None] = mapped_column(sa.Numeric(14, 6))
    low_price: Mapped[Decimal | None] = mapped_column(sa.Numeric(14, 6))
    close_price: Mapped[Decimal | None] = mapped_column(sa.Numeric(14, 6), index=True)
    volume: Mapped[int | None] = mapped_column(sa.BigInteger)
    num_trades: Mapped[int | None] = mapped_column(sa.Integer)

    source: Mapped[str | None] = mapped_column(sa.String(50))  # "B3", "Yahoo Finance"
    created_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), default=utcnow)

    __table_args__ = (
        sa.Index("ix_market_prices_ticker_id", "ticker_id"),
        sa.UniqueConstraint("ticker_id", "trade_date"),
    )

    def __repr__(self) -> str:
        return f"MarketPrice(trade_date={self.trade_date!r}, close_price={self.close_price})"


class Embedding(Base):
    """Embeddings vetoriais para busca semântica com pgvector."""

    __tablename__ = "embeddings"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    content_type: Mapped[str | None] = mapped_column(sa.String(50))  # "document", "news", "thesis"
    entity_id: Mapped[UUID] = mapped_column(nullable=False)
    text_snippet: Mapped[str | None] = mapped_column(sa.Text)
    vector: Mapped[list[float] | None] = mapped_column(Vector(1536))
    __table_args__ = (sa.Index("ix_embeddings_entity_id", "entity_id"),)

    created_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), default=utcnow)

    def __repr__(self) -> str:
        return f"Embedding(content_type={self.content_type!r}, entity_id={self.entity_id!r})"
