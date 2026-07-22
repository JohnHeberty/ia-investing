"""add portfolio rebalance proposal, trade, and drift snapshot tables

Revision ID: b4c000000005
Revises: b4c000000004

Creates:
- portfolio_rebalance_proposals — rebalance workflow container
- portfolio_rebalance_trades — individual trade instructions
- drift_snapshots — periodic allocation drift records
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "b4c000000005"
down_revision: str | Sequence[str] | None = "b4c000000004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "portfolio_rebalance_proposals",
        sa.Column("id", UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("portfolio_id", UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="draft"),
        sa.Column("target_allocations", JSONB, nullable=False),
        sa.Column("current_allocations", JSONB, nullable=True),
        sa.Column("drift_analysis", JSONB, nullable=True),
        sa.Column("rationale", sa.Text, nullable=False),
        sa.Column("created_by", sa.String(200), nullable=False),
        sa.Column("approved_by", sa.String(200), nullable=True),
        sa.Column("approval_notes", sa.Text, nullable=True),
        sa.Column("cancelled_reason", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["portfolio_id"],
            ["model_portfolios.id"],
            ondelete="CASCADE",
            name="fk_portfolio_rebalance_proposals_portfolio_id",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_portfolio_rebalance_proposals"),
        sa.CheckConstraint(
            "status IN ('draft', 'approved', 'in_progress', 'completed', 'cancelled')",
            name="ck_portfolio_rebalance_proposal_status",
        ),
    )
    op.create_index(
        "ix_portfolio_rebalance_proposals_portfolio_status",
        "portfolio_rebalance_proposals",
        ["portfolio_id", "status"],
    )

    op.create_table(
        "portfolio_rebalance_trades",
        sa.Column("id", UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("proposal_id", UUID(as_uuid=True), nullable=False),
        sa.Column("ticker", sa.String(20), nullable=False),
        sa.Column("side", sa.String(4), nullable=False),
        sa.Column("current_weight", sa.Numeric(12, 6), nullable=False),
        sa.Column("target_weight", sa.Numeric(12, 6), nullable=False),
        sa.Column("delta", sa.Numeric(12, 6), nullable=False),
        sa.Column("estimated_value", sa.Numeric(28, 10), nullable=False),
        sa.Column("estimated_fees", sa.Numeric(28, 10), nullable=True),
        sa.Column("estimated_taxes", sa.Numeric(28, 10), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("execution_order", sa.Integer, nullable=False, server_default="0"),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fill_price", sa.Numeric(28, 10), nullable=True),
        sa.Column("fill_quantity", sa.Numeric(28, 10), nullable=True),
        sa.Column("execution_notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(
            ["proposal_id"],
            ["portfolio_rebalance_proposals.id"],
            ondelete="CASCADE",
            name="fk_portfolio_rebalance_trades_proposal_id",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_portfolio_rebalance_trades"),
        sa.CheckConstraint("side IN ('buy', 'sell')", name="ck_portfolio_rebalance_trade_side"),
        sa.CheckConstraint(
            "status IN ('pending', 'executed', 'skipped', 'failed')",
            name="ck_portfolio_rebalance_trade_status",
        ),
        sa.CheckConstraint(
            "current_weight >= 0 AND target_weight >= 0",
            name="ck_portfolio_rebalance_trade_nonnegative_weights",
        ),
    )
    op.create_index(
        "ix_portfolio_rebalance_trades_proposal_status",
        "portfolio_rebalance_trades",
        ["proposal_id", "status"],
    )

    op.create_table(
        "drift_snapshots",
        sa.Column("id", UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("portfolio_id", UUID(as_uuid=True), nullable=False),
        sa.Column("snapshot_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("allocations", JSONB, nullable=False),
        sa.Column("max_drift", sa.Numeric(12, 6), nullable=False),
        sa.Column("total_drift", sa.Numeric(12, 6), nullable=False),
        sa.Column("risk_contribution", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(
            ["portfolio_id"],
            ["model_portfolios.id"],
            ondelete="CASCADE",
            name="fk_drift_snapshots_portfolio_id",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_drift_snapshots"),
        sa.CheckConstraint(
            "max_drift >= 0 AND total_drift >= 0",
            name="ck_drift_snapshot_nonnegative",
        ),
    )
    op.create_index(
        "ix_drift_snapshots_portfolio_date",
        "drift_snapshots",
        ["portfolio_id", "snapshot_date"],
    )


def downgrade() -> None:
    op.drop_index("ix_drift_snapshots_portfolio_date", table_name="drift_snapshots")
    op.drop_table("drift_snapshots")
    op.drop_index("ix_portfolio_rebalance_trades_proposal_status", table_name="portfolio_rebalance_trades")
    op.drop_table("portfolio_rebalance_trades")
    op.drop_index("ix_portfolio_rebalance_proposals_portfolio_status", table_name="portfolio_rebalance_proposals")
    op.drop_table("portfolio_rebalance_proposals")
