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


class StrategyMandate(Base):
    __tablename__ = "strategy_mandates"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(sa.ForeignKey("organizations.id", ondelete="RESTRICT"), index=True)
    logical_id: Mapped[str] = mapped_column(sa.String(100))
    version: Mapped[int] = mapped_column()
    objective: Mapped[str] = mapped_column(sa.Text)
    strategy_type: Mapped[str] = mapped_column(sa.String(50))
    universe_definition: Mapped[dict[str, object]] = mapped_column(JSONB)
    benchmark_index_id: Mapped[UUID] = mapped_column(sa.ForeignKey("market_indices.id", ondelete="RESTRICT"))
    base_currency: Mapped[str] = mapped_column(sa.String(3), default="BRL")
    investment_horizon_days: Mapped[int] = mapped_column()
    rebalance_policy: Mapped[dict[str, object]] = mapped_column(JSONB)
    risk_budget: Mapped[dict[str, object]] = mapped_column(JSONB)
    target_volatility: Mapped[Decimal | None] = mapped_column(sa.Numeric(8, 6))
    max_drawdown: Mapped[Decimal] = mapped_column(sa.Numeric(8, 6))
    concentration_limits: Mapped[dict[str, object]] = mapped_column(JSONB)
    factor_limits: Mapped[dict[str, object]] = mapped_column(JSONB)
    liquidity_policy: Mapped[dict[str, object]] = mapped_column(JSONB)
    min_cash_weight: Mapped[Decimal] = mapped_column(sa.Numeric(8, 6))
    max_cash_weight: Mapped[Decimal] = mapped_column(sa.Numeric(8, 6))
    max_turnover: Mapped[Decimal] = mapped_column(sa.Numeric(8, 6))
    exclusions: Mapped[dict[str, object]] = mapped_column(JSONB)
    cost_policy: Mapped[dict[str, object]] = mapped_column(JSONB)
    tax_policy: Mapped[dict[str, object]] = mapped_column(JSONB)
    approval_policy: Mapped[dict[str, object]] = mapped_column(JSONB)
    content_sha256: Mapped[str] = mapped_column(sa.String(64))
    status: Mapped[str] = mapped_column(sa.String(20), default="draft")
    created_by: Mapped[str] = mapped_column(sa.String(255))
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=utcnow)

    __table_args__ = (
        sa.UniqueConstraint(
            "organization_id", "logical_id", "version", name="uq_strategy_mandates_org_logical_version"
        ),
        sa.CheckConstraint("version > 0", name="positive_version"),
        sa.CheckConstraint("content_sha256 ~ '^[0-9a-f]{64}$'", name="sha256_format"),
        sa.CheckConstraint("base_currency ~ '^[A-Z]{3}$'", name="currency_format"),
        sa.CheckConstraint("investment_horizon_days > 0", name="positive_horizon"),
        sa.CheckConstraint(
            "min_cash_weight BETWEEN 0 AND 1 AND max_cash_weight BETWEEN min_cash_weight AND 1", name="cash_range"
        ),
        sa.CheckConstraint("max_turnover BETWEEN 0 AND 2", name="turnover_range"),
        sa.CheckConstraint("max_drawdown BETWEEN 0 AND 1", name="drawdown_range"),
        sa.CheckConstraint("status IN ('draft', 'active', 'retired')", name="status_values"),
    )


class ModelPortfolio(Base):
    __tablename__ = "model_portfolios"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(sa.ForeignKey("organizations.id", ondelete="RESTRICT"), index=True)
    owner_team_id: Mapped[UUID] = mapped_column(sa.ForeignKey("teams.id", ondelete="RESTRICT"))
    mandate_id: Mapped[UUID] = mapped_column(sa.ForeignKey("strategy_mandates.id", ondelete="RESTRICT"))
    name: Mapped[str] = mapped_column(sa.String(200))
    base_currency: Mapped[str] = mapped_column(sa.String(3))
    state: Mapped[str] = mapped_column(sa.String(30), default="draft")
    environment: Mapped[str] = mapped_column(sa.String(10), default="paper")
    lock_version: Mapped[int] = mapped_column(default=1)
    created_by: Mapped[str] = mapped_column(sa.String(255))
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    __table_args__ = (
        sa.UniqueConstraint("organization_id", "name", name="uq_model_portfolios_organization_name"),
        sa.CheckConstraint(
            "state IN ('draft', 'researching', 'simulated', 'committee_review', 'approved', 'paper_live', "
            "'eligible_for_live', 'live', 'suspended', 'archived')",
            name="state_values",
        ),
        sa.CheckConstraint("environment IN ('paper', 'live')", name="environment_values"),
    )
