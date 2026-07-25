"""add tenant scope to quality_incidents

Revision ID: b4c000000008
Revises: b4c000000007

Adds organization_id to quality_incidents so data governance incidents
are scoped to the same tenant as the rest of the platform.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b4c000000008"
down_revision: str | Sequence[str] | None = "b4c000000007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("quality_incidents", sa.Column("organization_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_quality_incidents_organization_id_organizations",
        "quality_incidents",
        "organizations",
        ["organization_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_quality_incidents_organization_id", "quality_incidents", ["organization_id"])


def downgrade() -> None:
    op.drop_index("ix_quality_incidents_organization_id", table_name="quality_incidents")
    op.drop_constraint(
        "fk_quality_incidents_organization_id_organizations",
        "quality_incidents",
        type_="foreignkey",
    )
    op.drop_column("quality_incidents", "organization_id")
