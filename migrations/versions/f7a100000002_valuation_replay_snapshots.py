"""persist complete valuation replay snapshots

Revision ID: f7a100000002
Revises: f7a100000001
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f7a100000002"
down_revision: str | Sequence[str] | None = "f7a100000001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "valuation_runs",
        sa.Column("input_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column("valuation_runs", sa.Column("result_sha256", sa.String(64), nullable=True))
    op.execute("UPDATE valuation_runs SET input_payload = '{}'::jsonb WHERE input_payload IS NULL")
    op.execute("UPDATE valuation_runs SET result_sha256 = repeat('0', 64) WHERE result_sha256 IS NULL")
    op.alter_column("valuation_runs", "input_payload", nullable=False)
    op.alter_column("valuation_runs", "result_sha256", nullable=False)
    op.create_check_constraint(
        op.f("ck_valuation_runs_result_sha256_format"),
        "valuation_runs",
        "result_sha256 ~ '^[0-9a-f]{64}$'",
    )


def downgrade() -> None:
    op.drop_constraint(op.f("ck_valuation_runs_result_sha256_format"), "valuation_runs", type_="check")
    op.drop_column("valuation_runs", "result_sha256")
    op.drop_column("valuation_runs", "input_payload")
