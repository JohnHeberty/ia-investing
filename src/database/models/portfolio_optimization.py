from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class OptimizationRun(Base):
    __tablename__ = "optimization_runs"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    portfolio_id: Mapped[UUID] = mapped_column(sa.ForeignKey("model_portfolios.id", ondelete="CASCADE"), index=True)
    as_of: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True))
    input_sha256: Mapped[str] = mapped_column(sa.String(64))
    solver: Mapped[str] = mapped_column(sa.String(50))
    solver_version: Mapped[str] = mapped_column(sa.String(50))
    tolerances: Mapped[dict[str, object]] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(sa.String(30))
    weights: Mapped[dict[str, object]] = mapped_column(JSONB)
    trades: Mapped[list[dict[str, object]]] = mapped_column(JSONB)
    slacks: Mapped[dict[str, object]] = mapped_column(JSONB)
    diagnostics: Mapped[dict[str, object]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=utcnow)

    __table_args__ = (
        sa.UniqueConstraint("portfolio_id", "as_of", "input_sha256", name="uq_optimization_runs_portfolio_asof_input"),
        sa.CheckConstraint("input_sha256 ~ '^[0-9a-f]{64}$'", name="sha256_format"),
    )


class PortfolioApprovalEvidence(Base):
    __tablename__ = "portfolio_approval_evidence"

    portfolio_version_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("institutional_portfolio_versions.id", ondelete="RESTRICT"), primary_key=True
    )
    optimization_run_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("optimization_runs.id", ondelete="RESTRICT"), unique=True
    )
    risk_snapshot_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("institutional_risk_snapshots.id", ondelete="RESTRICT"), unique=True
    )
    evidence_sha256: Mapped[str] = mapped_column(sa.String(64))
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=utcnow)

    __table_args__ = (sa.CheckConstraint("evidence_sha256 ~ '^[0-9a-f]{64}$'", name="sha256_format"),)


class BacktestConfig(Base):
    __tablename__ = "backtest_configs"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(sa.ForeignKey("organizations.id", ondelete="RESTRICT"), index=True)
    strategy_name: Mapped[str] = mapped_column(sa.String(200))
    universe_definition: Mapped[dict[str, object]] = mapped_column(JSONB)
    benchmark_index_id: Mapped[UUID] = mapped_column(sa.ForeignKey("market_indices.id", ondelete="RESTRICT"))
    start_date: Mapped[date]
    end_date: Mapped[date]
    signal_delay_sessions: Mapped[int] = mapped_column()
    costs: Mapped[dict[str, object]] = mapped_column(JSONB)
    taxes: Mapped[dict[str, object]] = mapped_column(JSONB)
    seed: Mapped[int] = mapped_column()
    config_sha256: Mapped[str] = mapped_column(sa.String(64), unique=True)

    __table_args__ = (
        sa.CheckConstraint("end_date >= start_date", name="valid_dates"),
        sa.CheckConstraint("signal_delay_sessions >= 1", name="positive_signal_delay"),
        sa.CheckConstraint("config_sha256 ~ '^[0-9a-f]{64}$'", name="sha256_format"),
    )


class InstitutionalBacktestRun(Base):
    __tablename__ = "institutional_backtest_runs"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    config_id: Mapped[UUID] = mapped_column(sa.ForeignKey("backtest_configs.id", ondelete="RESTRICT"), index=True)
    code_version: Mapped[str] = mapped_column(sa.String(100))
    data_snapshot_sha256: Mapped[str] = mapped_column(sa.String(64))
    status: Mapped[str] = mapped_column(sa.String(20))
    result_sha256: Mapped[str | None] = mapped_column(sa.String(64))
    results: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=utcnow)

    __table_args__ = (
        sa.UniqueConstraint(
            "config_id", "code_version", "data_snapshot_sha256", name="uq_backtest_runs_reproducible_input"
        ),
        sa.CheckConstraint("data_snapshot_sha256 ~ '^[0-9a-f]{64}$'", name="data_hash_format"),
        sa.CheckConstraint("result_sha256 IS NULL OR result_sha256 ~ '^[0-9a-f]{64}$'", name="result_hash_format"),
        sa.CheckConstraint("status IN ('queued', 'running', 'succeeded', 'failed', 'cancelled')", name="status_values"),
    )
