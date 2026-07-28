"""Add missing FKs, convert Float→Numeric, add DLQ table.

Revision ID: 20260727_01
Revises: 20260726_02
Create Date: 2026-07-27

- R5-7: FK on agent_capabilities.active_version_id → agent_versions.id
- R5-9: FK on thesis_versions.agent_run_id → agent_runtime_runs.id
- R5-13/14: Float→Numeric in scorecards, backtest_results, risk_snapshots
- R6-H1: Add operation_dispatch_dead_letter table + expand outbox state constraint
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "20260727_01"
down_revision: str | None = "20260726_02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- R5-7: FK on agent_capabilities.active_version_id ---
    op.execute(
        "DELETE FROM agent_capabilities "
        "WHERE active_version_id IS NOT NULL "
        "AND active_version_id NOT IN (SELECT id FROM agent_versions)"
    )
    op.create_foreign_key(
        "fk_agent_capabilities_active_version",
        "agent_capabilities",
        "agent_versions",
        ["active_version_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # --- R5-9: FK on thesis_versions.agent_run_id ---
    op.execute(
        "DELETE FROM thesis_versions "
        "WHERE agent_run_id IS NOT NULL "
        "AND agent_run_id NOT IN (SELECT id FROM agent_runtime_runs)"
    )
    op.create_foreign_key(
        "fk_thesis_versions_agent_run",
        "thesis_versions",
        "agent_runtime_runs",
        ["agent_run_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # --- R5-14: Float→Numeric on scorecards ---
    op.execute("ALTER TABLE scorecards ALTER COLUMN quality_score TYPE NUMERIC(6,4) USING quality_score::numeric(6,4)")
    op.execute("ALTER TABLE scorecards ALTER COLUMN growth_score TYPE NUMERIC(6,4) USING growth_score::numeric(6,4)")
    op.execute("ALTER TABLE scorecards ALTER COLUMN leverage_score TYPE NUMERIC(6,4) USING leverage_score::numeric(6,4)")
    op.execute("ALTER TABLE scorecards ALTER COLUMN valuation_score TYPE NUMERIC(6,4) USING valuation_score::numeric(6,4)")
    op.execute("ALTER TABLE scorecards ALTER COLUMN overall_score TYPE NUMERIC(6,4) USING overall_score::numeric(6,4)")

    # --- R5-14: Float→Numeric on backtest_results ---
    op.execute("ALTER TABLE backtest_results ALTER COLUMN cagr_pct TYPE NUMERIC(8,4) USING cagr_pct::numeric(8,4)")
    op.execute("ALTER TABLE backtest_results ALTER COLUMN sharpe_ratio TYPE NUMERIC(8,4) USING sharpe_ratio::numeric(8,4)")
    op.execute("ALTER TABLE backtest_results ALTER COLUMN sortino_ratio TYPE NUMERIC(8,4) USING sortino_ratio::numeric(8,4)")
    op.execute("ALTER TABLE backtest_results ALTER COLUMN calmar_ratio TYPE NUMERIC(8,4) USING calmar_ratio::numeric(8,4)")
    op.execute("ALTER TABLE backtest_results ALTER COLUMN max_drawdown_pct TYPE NUMERIC(8,4) USING max_drawdown_pct::numeric(8,4)")
    op.execute("ALTER TABLE backtest_results ALTER COLUMN win_rate_pct TYPE NUMERIC(8,4) USING win_rate_pct::numeric(8,4)")
    op.execute("ALTER TABLE backtest_results ALTER COLUMN benchmark_cagr_pct TYPE NUMERIC(8,4) USING benchmark_cagr_pct::numeric(8,4)")

    # --- R5-13: Float→Numeric on risk_snapshots ---
    op.execute("ALTER TABLE risk_snapshots ALTER COLUMN sharpe_ratio TYPE NUMERIC(10,6) USING sharpe_ratio::numeric(10,6)")
    op.execute("ALTER TABLE risk_snapshots ALTER COLUMN max_drawdown_pct TYPE NUMERIC(10,6) USING max_drawdown_pct::numeric(10,6)")
    op.execute("ALTER TABLE risk_snapshots ALTER COLUMN volatility_annualized TYPE NUMERIC(10,6) USING volatility_annualized::numeric(10,6)")

    # --- R6-H1: Expand outbox state constraint ---
    op.execute("ALTER TABLE operation_dispatch_outbox DROP CONSTRAINT operation_dispatch_outbox_state")
    op.create_check_constraint(
        "operation_dispatch_outbox_state",
        "operation_dispatch_outbox",
        sa.text("state IN ('pending', 'dispatched', 'failed', 'dead_letter')"),
    )

    # --- R6-H1: Create dead letter table ---
    op.create_table(
        "operation_dispatch_dead_letter",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("outbox_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("operation_id", sa.Uuid(), nullable=False),
        sa.Column("topic", sa.String(100), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("last_error", sa.String(200), nullable=True),
        sa.Column("payload_snapshot", JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["outbox_id"], ["operation_dispatch_outbox.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["operation_id"], ["operations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("outbox_id"),
    )
    op.create_index("ix_dlq_organization", "operation_dispatch_dead_letter", ["organization_id"])


def downgrade() -> None:
    # --- Drop dead letter table ---
    op.drop_index("ix_dlq_organization", table_name="operation_dispatch_dead_letter")
    op.drop_table("operation_dispatch_dead_letter")

    # --- Restore outbox state constraint ---
    op.execute("ALTER TABLE operation_dispatch_outbox DROP CONSTRAINT operation_dispatch_outbox_state")
    op.create_check_constraint(
        "operation_dispatch_outbox_state",
        "operation_dispatch_outbox",
        sa.text("state IN ('pending', 'dispatched', 'failed')"),
    )

    # --- Revert risk_snapshots Float→Numeric ---
    op.execute("ALTER TABLE risk_snapshots ALTER COLUMN sharpe_ratio TYPE DOUBLE PRECISION USING sharpe_ratio::double precision")
    op.execute("ALTER TABLE risk_snapshots ALTER COLUMN max_drawdown_pct TYPE DOUBLE PRECISION USING max_drawdown_pct::double precision")
    op.execute("ALTER TABLE risk_snapshots ALTER COLUMN volatility_annualized TYPE DOUBLE PRECISION USING volatility_annualized::double precision")

    # --- Revert backtest_results Float→Numeric ---
    op.execute("ALTER TABLE backtest_results ALTER COLUMN benchmark_cagr_pct TYPE DOUBLE PRECISION USING benchmark_cagr_pct::double precision")
    op.execute("ALTER TABLE backtest_results ALTER COLUMN win_rate_pct TYPE DOUBLE PRECISION USING win_rate_pct::double precision")
    op.execute("ALTER TABLE backtest_results ALTER COLUMN max_drawdown_pct TYPE DOUBLE PRECISION USING max_drawdown_pct::double precision")
    op.execute("ALTER TABLE backtest_results ALTER COLUMN calmar_ratio TYPE DOUBLE PRECISION USING calmar_ratio::double precision")
    op.execute("ALTER TABLE backtest_results ALTER COLUMN sortino_ratio TYPE DOUBLE PRECISION USING sortino_ratio::double precision")
    op.execute("ALTER TABLE backtest_results ALTER COLUMN sharpe_ratio TYPE DOUBLE PRECISION USING sharpe_ratio::double precision")
    op.execute("ALTER TABLE backtest_results ALTER COLUMN cagr_pct TYPE DOUBLE PRECISION USING cagr_pct::double precision")

    # --- Revert scorecards Float→Numeric ---
    op.execute("ALTER TABLE scorecards ALTER COLUMN overall_score TYPE DOUBLE PRECISION USING overall_score::double precision")
    op.execute("ALTER TABLE scorecards ALTER COLUMN valuation_score TYPE DOUBLE PRECISION USING valuation_score::double precision")
    op.execute("ALTER TABLE scorecards ALTER COLUMN leverage_score TYPE DOUBLE PRECISION USING leverage_score::double precision")
    op.execute("ALTER TABLE scorecards ALTER COLUMN growth_score TYPE DOUBLE PRECISION USING growth_score::double precision")
    op.execute("ALTER TABLE scorecards ALTER COLUMN quality_score TYPE DOUBLE PRECISION USING quality_score::double precision")

    # --- Drop FKs ---
    op.drop_constraint("fk_thesis_versions_agent_run", "thesis_versions", type_="foreignkey")
    op.drop_constraint("fk_agent_capabilities_active_version", "agent_capabilities", type_="foreignkey")
