"""Link approved portfolio versions to optimizer and risk evidence.

Revision ID: f7a100000006
Revises: f7a100000005
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f7a100000006"
down_revision: str | None = "f7a100000005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
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


def downgrade() -> None:
    op.drop_constraint("fk_portfolio_versions_risk_snapshot", "institutional_portfolio_versions", type_="foreignkey")
    op.drop_constraint("fk_portfolio_versions_optimization_run", "institutional_portfolio_versions", type_="foreignkey")
    op.drop_column("institutional_portfolio_versions", "risk_snapshot_id")
    op.drop_column("institutional_portfolio_versions", "optimization_run_id")
