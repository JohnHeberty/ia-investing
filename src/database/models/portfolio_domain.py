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


class InstitutionalRiskPolicy(Base):
    __tablename__ = "institutional_risk_policies"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    mandate_id: Mapped[UUID] = mapped_column(sa.ForeignKey("strategy_mandates.id", ondelete="CASCADE"), index=True)
    version: Mapped[int] = mapped_column()
    methodology_version: Mapped[str] = mapped_column(sa.String(100))
    limits: Mapped[dict[str, object]] = mapped_column(JSONB)
    content_sha256: Mapped[str] = mapped_column(sa.String(64))
    status: Mapped[str] = mapped_column(sa.String(20), default="active")

    __table_args__ = (
        sa.UniqueConstraint("mandate_id", "version", name="uq_institutional_risk_policies_mandate_version"),
        sa.CheckConstraint("content_sha256 ~ '^[0-9a-f]{64}$'", name="sha256_format"),
    )


class InstitutionalRiskSnapshot(Base):
    __tablename__ = "institutional_risk_snapshots"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    portfolio_version_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("institutional_portfolio_versions.id", ondelete="CASCADE"), index=True
    )
    risk_policy_id: Mapped[UUID] = mapped_column(sa.ForeignKey("institutional_risk_policies.id", ondelete="RESTRICT"))
    as_of: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True))
    input_sha256: Mapped[str] = mapped_column(sa.String(64))
    exposures: Mapped[dict[str, object]] = mapped_column(JSONB)
    concentration: Mapped[dict[str, object]] = mapped_column(JSONB)
    liquidity: Mapped[dict[str, object]] = mapped_column(JSONB)
    volatility: Mapped[Decimal | None] = mapped_column(sa.Numeric(10, 8))
    drawdown: Mapped[Decimal | None] = mapped_column(sa.Numeric(10, 8))
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=utcnow)

    __table_args__ = (
        sa.UniqueConstraint(
            "portfolio_version_id", "risk_policy_id", "as_of", name="uq_risk_snapshots_version_policy_asof"
        ),
    )


class RiskBreach(Base):
    __tablename__ = "risk_breaches"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    risk_snapshot_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("institutional_risk_snapshots.id", ondelete="CASCADE"), index=True
    )
    limit_name: Mapped[str] = mapped_column(sa.String(150))
    limit_type: Mapped[str] = mapped_column(sa.String(10))
    observed_value: Mapped[Decimal] = mapped_column(sa.Numeric(20, 8))
    limit_value: Mapped[Decimal] = mapped_column(sa.Numeric(20, 8))
    status: Mapped[str] = mapped_column(sa.String(20), default="open")
    opened_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=utcnow)

    __table_args__ = (
        sa.UniqueConstraint("risk_snapshot_id", "limit_name", name="uq_risk_breaches_snapshot_limit"),
        sa.CheckConstraint("limit_type IN ('hard', 'soft')", name="limit_type_values"),
        sa.CheckConstraint("status IN ('open', 'waived', 'resolved')", name="status_values"),
    )


class RiskWaiver(Base):
    __tablename__ = "risk_waivers"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    breach_id: Mapped[UUID] = mapped_column(sa.ForeignKey("risk_breaches.id", ondelete="CASCADE"), index=True)
    granted_by: Mapped[str] = mapped_column(sa.String(255))
    reason: Mapped[str] = mapped_column(sa.Text)
    granted_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True))

    __table_args__ = (sa.CheckConstraint("expires_at > granted_at", name="valid_expiry"),)


class StressScenario(Base):
    __tablename__ = "stress_scenarios"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    logical_id: Mapped[str] = mapped_column(sa.String(100))
    version: Mapped[int] = mapped_column()
    shocks: Mapped[dict[str, object]] = mapped_column(JSONB)
    content_sha256: Mapped[str] = mapped_column(sa.String(64))

    __table_args__ = (
        sa.UniqueConstraint("logical_id", "version", name="uq_stress_scenarios_logical_version"),
        sa.CheckConstraint("content_sha256 ~ '^[0-9a-f]{64}$'", name="sha256_format"),
    )


class StressResult(Base):
    __tablename__ = "stress_results"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    risk_snapshot_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("institutional_risk_snapshots.id", ondelete="CASCADE"), index=True
    )
    scenario_id: Mapped[UUID] = mapped_column(sa.ForeignKey("stress_scenarios.id", ondelete="RESTRICT"))
    pnl_impact: Mapped[Decimal] = mapped_column(sa.Numeric(28, 8))
    nav_impact_ratio: Mapped[Decimal] = mapped_column(sa.Numeric(10, 8))
    result_payload: Mapped[dict[str, object]] = mapped_column(JSONB)

    __table_args__ = (
        sa.UniqueConstraint("risk_snapshot_id", "scenario_id", name="uq_stress_results_snapshot_scenario"),
    )


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
