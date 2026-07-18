from datetime import UTC, datetime

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import UUID

from .base import Base


class Sector(Base):
    __tablename__ = "sectors"

    id = sa.Column(UUID(as_uuid=True), primary_key=True, default=sa.func.gen_random_uuid())
    name_pt = sa.Column(sa.String(100), nullable=False)
    name_en = sa.Column(sa.String(100))
    code_anbima = sa.Column(sa.String(20))
    created_at = sa.Column(sa.DateTime(timezone=True), default=lambda: datetime.now(UTC))

    industries = sa.orm.relationship("Industry", back_populates="sector")

    def __repr__(self) -> str:
        return f"Sector(name_pt={self.name_pt!r}, code_anbima={self.code_anbima!r})"


class Industry(Base):
    __tablename__ = "industries"

    id = sa.Column(UUID(as_uuid=True), primary_key=True, default=sa.func.gen_random_uuid())
    name_pt = sa.Column(sa.String(100), nullable=False)
    name_en = sa.Column(sa.String(100))
    sector_id = sa.Column(
        UUID(as_uuid=True), sa.ForeignKey("sectors.id", ondelete="CASCADE"), nullable=False,
    )
    created_at = sa.Column(sa.DateTime(timezone=True), default=lambda: datetime.now(UTC))

    sector = sa.orm.relationship("Sector", back_populates="industries")

    def __repr__(self) -> str:
        return f"Industry(name_pt={self.name_pt!r})"


class Issuer(Base):
    __tablename__ = "issuers"

    id = sa.Column(UUID(as_uuid=True), primary_key=True, default=sa.func.gen_random_uuid())
    name_pt = sa.Column(sa.String(200), nullable=False)
    cnpj = sa.Column(sa.String(14), unique=True, index=True)
    cvm_code = sa.Column(sa.Integer, unique=True, index=True)
    industry_id = sa.Column(
        UUID(as_uuid=True), sa.ForeignKey("industries.id", ondelete="SET NULL"),
    )
    website_ri_url = sa.Column(sa.Text)
    is_active = sa.Column(sa.Boolean, default=True)

    created_at = sa.Column(sa.DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at = sa.Column(
        sa.DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    tickers = sa.orm.relationship("Ticker", back_populates="issuer")

    def __repr__(self) -> str:
        return f"Issuer(name_pt={self.name_pt!r}, cnpj={self.cnpj!r})"


class Ticker(Base):
    __tablename__ = "tickers"

    id = sa.Column(UUID(as_uuid=True), primary_key=True, default=sa.func.gen_random_uuid())
    symbol = sa.Column(sa.String(10), nullable=False)
    issuer_id = sa.Column(
        UUID(as_uuid=True), sa.ForeignKey("issuers.id", ondelete="CASCADE"), nullable=False,
    )
    market_segment = sa.Column(sa.String(20))  # "BOVESPA", "SADR" (Novo Mercado), etc.
    listing_date = sa.Column(sa.Date)
    delisting_date = sa.Column(sa.Date, index=True)

    created_at = sa.Column(sa.DateTime(timezone=True), default=lambda: datetime.now(UTC))

    issuer = sa.orm.relationship("Issuer", back_populates="tickers")

    __table_args__ = (
        sa.UniqueConstraint("symbol", "issuer_id"),
    )

    def __repr__(self) -> str:
        return f"Ticker(symbol={self.symbol!r}, market_segment={self.market_segment!r})"


class MarketPrice(Base):
    """Cotações diárias históricas."""

    __tablename__ = "market_prices"

    id = sa.Column(UUID(as_uuid=True), primary_key=True, default=sa.func.gen_random_uuid())
    ticker_id = sa.Column(
        UUID(as_uuid=True), sa.ForeignKey("tickers.id", ondelete="CASCADE"), nullable=False,
    )
    trade_date = sa.Column(sa.Date, nullable=False)
    open_price = sa.Column(sa.Numeric(14, 6))
    high_price = sa.Column(sa.Numeric(14, 6))
    low_price = sa.Column(sa.Numeric(14, 6))
    close_price = sa.Column(sa.Numeric(14, 6), index=True)
    volume = sa.Column(sa.BigInteger)
    num_trades = sa.Column(sa.Integer)

    source = sa.Column(sa.String(50))  # "B3", "Yahoo Finance"
    created_at = sa.Column(sa.DateTime(timezone=True), default=lambda: datetime.now(UTC))

    __table_args__ = (
        sa.Index("ix_market_prices_ticker_id", "ticker_id"),
        sa.UniqueConstraint("ticker_id", "trade_date"),
    )

    def __repr__(self) -> str:
        return f"MarketPrice(trade_date={self.trade_date!r}, close_price={self.close_price})"


class Embedding(Base):
    """Embeddings vetoriais para busca semântica com pgvector."""

    __tablename__ = "embeddings"

    id = sa.Column(UUID(as_uuid=True), primary_key=True, default=sa.func.gen_random_uuid())
    content_type = sa.Column(sa.String(50))  # "document", "news", "thesis"
    entity_id = sa.Column(UUID(as_uuid=True), nullable=False)
    text_snippet = sa.Column(sa.Text)
    vector = sa.Column(Vector(dimensions=1536))
    __table_args__ = (
        sa.Index("ix_embeddings_entity_id", "entity_id"),
    )

    created_at = sa.Column(sa.DateTime(timezone=True), default=lambda: datetime.now(UTC))

    def __repr__(self) -> str:
        return f"Embedding(content_type={self.content_type!r}, entity_id={self.entity_id!r})"
