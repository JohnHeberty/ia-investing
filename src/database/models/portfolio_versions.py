from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class InstitutionalPortfolioVersion(Base):
    __tablename__ = "institutional_portfolio_versions"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    portfolio_id: Mapped[UUID] = mapped_column(sa.ForeignKey("model_portfolios.id", ondelete="CASCADE"), index=True)
    mandate_id: Mapped[UUID] = mapped_column(sa.ForeignKey("strategy_mandates.id", ondelete="RESTRICT"))
    version: Mapped[int] = mapped_column()
    as_of: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True))
    input_snapshot_sha256: Mapped[str] = mapped_column(sa.String(64))
    weights_sha256: Mapped[str] = mapped_column(sa.String(64))
    approved_weights: Mapped[dict[str, object]] = mapped_column(JSONB)
    proposal: Mapped[dict[str, object]] = mapped_column(JSONB)
    decision: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(sa.String(20), default="draft")
    created_by: Mapped[str] = mapped_column(sa.String(255))
    approved_by: Mapped[str | None] = mapped_column(sa.String(255))
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=utcnow)

    __table_args__ = (
        sa.UniqueConstraint("portfolio_id", "version", name="uq_institutional_portfolio_versions_portfolio_version"),
        sa.CheckConstraint("version > 0", name="positive_version"),
        sa.CheckConstraint(
            "input_snapshot_sha256 ~ '^[0-9a-f]{64}$' AND weights_sha256 ~ '^[0-9a-f]{64}$'", name="hash_format"
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'proposed', 'approved', 'rejected', 'superseded')", name="status_values"
        ),
    )


class PortfolioVersionThesis(Base):
    __tablename__ = "portfolio_version_theses"

    portfolio_version_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("institutional_portfolio_versions.id", ondelete="CASCADE"), primary_key=True
    )
    thesis_version_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("research_thesis_versions.id", ondelete="RESTRICT"), primary_key=True
    )


class PortfolioVersionValuation(Base):
    __tablename__ = "portfolio_version_valuations"

    portfolio_version_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("institutional_portfolio_versions.id", ondelete="CASCADE"), primary_key=True
    )
    valuation_run_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("valuation_runs.id", ondelete="RESTRICT"), primary_key=True
    )


class PositionSnapshot(Base):
    __tablename__ = "position_snapshots"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    portfolio_version_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("institutional_portfolio_versions.id", ondelete="CASCADE"), index=True
    )
    instrument_id: Mapped[UUID] = mapped_column(sa.ForeignKey("instruments.id", ondelete="RESTRICT"))
    quantity: Mapped[Decimal] = mapped_column(sa.Numeric(28, 10))
    cost_basis: Mapped[Decimal] = mapped_column(sa.Numeric(28, 8))
    as_of: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True))

    __table_args__ = (
        sa.UniqueConstraint("portfolio_version_id", "instrument_id", name="uq_position_snapshots_version_instrument"),
        sa.CheckConstraint("quantity >= 0 AND cost_basis >= 0", name="nonnegative_values"),
    )


class CashSnapshot(Base):
    __tablename__ = "cash_snapshots"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    portfolio_version_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("institutional_portfolio_versions.id", ondelete="CASCADE"), index=True
    )
    currency: Mapped[str] = mapped_column(sa.String(3))
    amount: Mapped[Decimal] = mapped_column(sa.Numeric(28, 8))
    as_of: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True))

    __table_args__ = (
        sa.UniqueConstraint("portfolio_version_id", "currency", name="uq_cash_snapshots_version_currency"),
    )


class PortfolioLedgerEntry(Base):
    __tablename__ = "portfolio_ledger_entries"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    portfolio_id: Mapped[UUID] = mapped_column(sa.ForeignKey("model_portfolios.id", ondelete="CASCADE"), index=True)
    instrument_id: Mapped[UUID | None] = mapped_column(sa.ForeignKey("instruments.id", ondelete="RESTRICT"))
    entry_type: Mapped[str] = mapped_column(sa.String(30))
    currency: Mapped[str] = mapped_column(sa.String(3))
    amount: Mapped[Decimal] = mapped_column(sa.Numeric(28, 8))
    quantity: Mapped[Decimal | None] = mapped_column(sa.Numeric(28, 10))
    occurred_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), index=True)
    source_reference: Mapped[str] = mapped_column(sa.String(255))
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=utcnow)

    __table_args__ = (
        sa.UniqueConstraint("portfolio_id", "source_reference", name="uq_portfolio_ledger_entries_source"),
        sa.CheckConstraint(
            "entry_type IN ('cash', 'trade', 'dividend', 'jcp', 'fee', 'tax', 'fx')", name="entry_type_values"
        ),
    )


class NavPublication(Base):
    __tablename__ = "nav_publications"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    portfolio_id: Mapped[UUID] = mapped_column(sa.ForeignKey("model_portfolios.id", ondelete="CASCADE"), index=True)
    portfolio_version_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("institutional_portfolio_versions.id", ondelete="RESTRICT")
    )
    as_of: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True))
    revision: Mapped[int] = mapped_column(default=1)
    methodology_version: Mapped[str] = mapped_column(sa.String(100))
    input_sha256: Mapped[str] = mapped_column(sa.String(64))
    input_details: Mapped[dict[str, object]] = mapped_column(JSONB)
    cash_value: Mapped[Decimal] = mapped_column(sa.Numeric(28, 8))
    positions_value: Mapped[Decimal] = mapped_column(sa.Numeric(28, 8))
    gross_pnl: Mapped[Decimal] = mapped_column(sa.Numeric(28, 8))
    net_pnl: Mapped[Decimal] = mapped_column(sa.Numeric(28, 8))
    fees_value: Mapped[Decimal] = mapped_column(sa.Numeric(28, 8))
    taxes_value: Mapped[Decimal] = mapped_column(sa.Numeric(28, 8))
    nav: Mapped[Decimal] = mapped_column(sa.Numeric(28, 8))
    benchmark_value: Mapped[Decimal | None] = mapped_column(sa.Numeric(28, 8))
    benchmark_return: Mapped[Decimal | None] = mapped_column(sa.Numeric(18, 10))
    reconciled: Mapped[bool] = mapped_column(default=False)
    published_by: Mapped[str] = mapped_column(sa.String(255))
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=utcnow)

    __table_args__ = (
        sa.UniqueConstraint("portfolio_id", "as_of", "revision", name="uq_nav_publications_portfolio_asof_revision"),
        sa.CheckConstraint("revision > 0", name="positive_revision"),
        sa.CheckConstraint("input_sha256 ~ '^[0-9a-f]{64}$'", name="sha256_format"),
        sa.CheckConstraint("nav = cash_value + positions_value - fees_value - taxes_value", name="accounting_identity"),
    )
