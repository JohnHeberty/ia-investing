"""add auditable portfolio ranking snapshots

Revision ID: b4c000000001
Revises: f7a100000007

The public migration graph already resolves to a single head at f7a100000007.
This revision extends that linear history with deterministic ranking inputs.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b4c000000001"
down_revision: str | Sequence[str] | None = "f7a100000007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_COMPONENTS = (
    "excess_return",
    "sortino",
    "drawdown_control",
    "regime_stability",
    "walk_forward_robustness",
    "risk_compliance",
    "thesis_health",
    "cost_capacity",
    "data_model_confidence",
)


def upgrade() -> None:
    columns: list[sa.Column] = [
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "portfolio_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("model_portfolios.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "portfolio_version_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("institutional_portfolio_versions.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("as_of", sa.DateTime(timezone=True), nullable=False),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("benchmark", sa.String(50), nullable=False),
        sa.Column("risk_class", sa.String(30), nullable=False),
        sa.Column("inception_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("nav_reconciled", sa.Boolean(), nullable=False),
        sa.Column("backtest_point_in_time_verified", sa.Boolean(), nullable=False),
        sa.Column("approved_version", sa.Boolean(), nullable=False),
        sa.Column("open_hard_breaches", sa.Integer(), nullable=False),
        sa.Column("open_soft_breaches", sa.Integer(), nullable=False),
        sa.Column("expired_theses", sa.Integer(), nullable=False),
        sa.Column("thesis_coverage", sa.Numeric(6, 5), nullable=False),
        sa.Column("data_confidence", sa.Numeric(6, 5), nullable=False),
        sa.Column("low_liquidity", sa.Boolean(), nullable=False),
        sa.Column("high_turnover", sa.Boolean(), nullable=False),
        sa.Column("methodology_version", sa.String(100), nullable=False),
        sa.Column("input_sha256", sa.String(64), nullable=False),
        sa.Column("input_payload", postgresql.JSONB(), nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
    ]
    columns.extend(sa.Column(name, sa.Numeric(6, 5), nullable=False) for name in _COMPONENTS)

    constraints: list[sa.SchemaItem] = [
        sa.UniqueConstraint(
            "portfolio_id",
            "as_of",
            "methodology_version",
            name="uq_portfolio_ranking_snapshot_identity",
        ),
        sa.CheckConstraint(
            "input_sha256 ~ '^[0-9a-f]{64}$'",
            name="ck_portfolio_ranking_snapshot_sha256",
        ),
        sa.CheckConstraint(
            "open_hard_breaches >= 0 AND open_soft_breaches >= 0 AND expired_theses >= 0",
            name="ck_portfolio_ranking_snapshot_nonnegative_counts",
        ),
        sa.CheckConstraint(
            "thesis_coverage BETWEEN 0 AND 1 AND data_confidence BETWEEN 0 AND 1",
            name="ck_portfolio_ranking_snapshot_confidence_ranges",
        ),
    ]
    for component in _COMPONENTS:
        constraints.append(
            sa.CheckConstraint(
                f"{component} BETWEEN 0 AND 1",
                name=f"ck_portfolio_ranking_snapshot_{component}_range",
            )
        )

    op.create_table("portfolio_ranking_snapshots", *columns, *constraints)
    op.create_index(
        "ix_portfolio_ranking_snapshots_portfolio_asof",
        "portfolio_ranking_snapshots",
        ["portfolio_id", "as_of"],
    )
    op.create_index(
        "ix_portfolio_ranking_snapshots_cohort",
        "portfolio_ranking_snapshots",
        ["category", "benchmark", "risk_class", "as_of"],
    )


def downgrade() -> None:
    op.drop_index("ix_portfolio_ranking_snapshots_cohort", table_name="portfolio_ranking_snapshots")
    op.drop_index("ix_portfolio_ranking_snapshots_portfolio_asof", table_name="portfolio_ranking_snapshots")
    op.drop_table("portfolio_ranking_snapshots")
