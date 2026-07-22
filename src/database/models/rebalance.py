from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ._utils import utcnow
from .base import Base


class RebalanceProposal(Base):
    __tablename__ = "portfolio_rebalance_proposals"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    portfolio_id: Mapped[UUID] = mapped_column(sa.ForeignKey("model_portfolios.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(sa.String(30), default="draft")
    target_allocations: Mapped[dict[str, object]] = mapped_column(JSONB)
    current_allocations: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    drift_analysis: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    rationale: Mapped[str] = mapped_column(sa.Text)
    created_by: Mapped[str] = mapped_column(sa.String(200))
    approved_by: Mapped[str | None] = mapped_column(sa.String(200))
    approval_notes: Mapped[str | None] = mapped_column(sa.Text)
    cancelled_reason: Mapped[str | None] = mapped_column(sa.Text)
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))

    __table_args__ = (
        sa.CheckConstraint(
            "status IN ('draft', 'approved', 'in_progress', 'completed', 'cancelled')",
            name="ck_rebalance_proposal_status",
        ),
        sa.Index("ix_rebalance_proposals_portfolio_status", "portfolio_id", "status"),
    )


class RebalanceTrade(Base):
    __tablename__ = "portfolio_rebalance_trades"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    proposal_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("portfolio_rebalance_proposals.id", ondelete="CASCADE"), index=True
    )
    ticker: Mapped[str] = mapped_column(sa.String(20))
    side: Mapped[str] = mapped_column(sa.String(4))
    current_weight: Mapped[Decimal] = mapped_column(sa.Numeric(12, 6))
    target_weight: Mapped[Decimal] = mapped_column(sa.Numeric(12, 6))
    delta: Mapped[Decimal] = mapped_column(sa.Numeric(12, 6))
    estimated_value: Mapped[Decimal] = mapped_column(sa.Numeric(28, 10))
    estimated_fees: Mapped[Decimal | None] = mapped_column(sa.Numeric(28, 10))
    estimated_taxes: Mapped[Decimal | None] = mapped_column(sa.Numeric(28, 10))
    status: Mapped[str] = mapped_column(sa.String(20), default="pending")
    execution_order: Mapped[int] = mapped_column(default=0)
    executed_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    fill_price: Mapped[Decimal | None] = mapped_column(sa.Numeric(28, 10))
    fill_quantity: Mapped[Decimal | None] = mapped_column(sa.Numeric(28, 10))
    execution_notes: Mapped[str | None] = mapped_column(sa.Text)
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=utcnow)

    __table_args__ = (
        sa.CheckConstraint("side IN ('buy', 'sell')", name="ck_rebalance_trade_side"),
        sa.CheckConstraint(
            "status IN ('pending', 'executed', 'skipped', 'failed')",
            name="ck_rebalance_trade_status",
        ),
        sa.CheckConstraint("current_weight >= 0 AND target_weight >= 0", name="ck_rebalance_trade_nonnegative_weights"),
        sa.Index("ix_rebalance_trades_proposal_status", "proposal_id", "status"),
    )


class DriftSnapshot(Base):
    __tablename__ = "drift_snapshots"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    portfolio_id: Mapped[UUID] = mapped_column(sa.ForeignKey("model_portfolios.id", ondelete="CASCADE"), index=True)
    snapshot_date: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True))
    allocations: Mapped[dict[str, object]] = mapped_column(JSONB)
    max_drift: Mapped[Decimal] = mapped_column(sa.Numeric(12, 6))
    total_drift: Mapped[Decimal] = mapped_column(sa.Numeric(12, 6))
    risk_contribution: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=utcnow)

    __table_args__ = (
        sa.Index("ix_drift_snapshots_portfolio_date", "portfolio_id", "snapshot_date"),
        sa.CheckConstraint("max_drift >= 0 AND total_drift >= 0", name="ck_drift_snapshot_nonnegative"),
    )
