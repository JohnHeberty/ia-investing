"""persist point-in-time NAV pricing and FX provenance

Revision ID: f7a100000004
Revises: f7a100000003
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f7a100000004"
down_revision: str | Sequence[str] | None = "f7a100000003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "nav_publications",
        sa.Column("input_details", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.execute("UPDATE nav_publications SET input_details = '{}'::jsonb WHERE input_details IS NULL")
    op.alter_column("nav_publications", "input_details", nullable=False)


def downgrade() -> None:
    op.drop_column("nav_publications", "input_details")
