"""Use an approval evidence association without cyclic foreign keys.

Revision ID: f7a100000007
Revises: f7a100000006
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f7a100000007"
down_revision: str | None = "f7a100000006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "portfolio_approval_evidence",
        sa.Column("portfolio_version_id", sa.Uuid(), nullable=False),
        sa.Column("optimization_run_id", sa.Uuid(), nullable=False),
        sa.Column("risk_snapshot_id", sa.Uuid(), nullable=False),
        sa.Column("evidence_sha256", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("evidence_sha256 ~ '^[0-9a-f]{64}$'", name="ck_portfolio_approval_evidence_sha256_format"),
        sa.ForeignKeyConstraint(["optimization_run_id"], ["optimization_runs.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["portfolio_version_id"], ["institutional_portfolio_versions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["risk_snapshot_id"], ["institutional_risk_snapshots.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("portfolio_version_id"),
        sa.UniqueConstraint("optimization_run_id"),
        sa.UniqueConstraint("risk_snapshot_id"),
    )
    op.drop_constraint("fk_portfolio_versions_risk_snapshot", "institutional_portfolio_versions", type_="foreignkey")
    op.drop_constraint("fk_portfolio_versions_optimization_run", "institutional_portfolio_versions", type_="foreignkey")
    op.drop_column("institutional_portfolio_versions", "risk_snapshot_id")
    op.drop_column("institutional_portfolio_versions", "optimization_run_id")


def downgrade() -> None:
    op.add_column("institutional_portfolio_versions", sa.Column("optimization_run_id", sa.Uuid(), nullable=True))
    op.add_column("institutional_portfolio_versions", sa.Column("risk_snapshot_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_portfolio_versions_optimization_run",
        "institutional_portfolio_versions",
        "optimization_runs",
        ["optimization_run_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_portfolio_versions_risk_snapshot",
        "institutional_portfolio_versions",
        "institutional_risk_snapshots",
        ["risk_snapshot_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.drop_table("portfolio_approval_evidence")
