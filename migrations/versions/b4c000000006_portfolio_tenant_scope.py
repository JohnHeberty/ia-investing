"""add organization_id to portfolios for tenant isolation

Revision ID: b4c000000006
Revises: b4c000000005

Adds:
- portfolios.organization_id FK → organizations.id (nullable, SET NULL on delete)
- unique constraint uq_portfolios_org_name on (organization_id, name)
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b4c000000006"
down_revision: str | Sequence[str] | None = "b4c000000005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "portfolios",
        sa.Column(
            "organization_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_portfolios_organization_id", "portfolios", ["organization_id"])
    op.create_unique_constraint(
        "uq_portfolios_org_name",
        "portfolios",
        ["organization_id", "name"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_portfolios_org_name", "portfolios", type_="unique")
    op.drop_index("ix_portfolios_organization_id", "portfolios")
    op.drop_column("portfolios", "organization_id")
