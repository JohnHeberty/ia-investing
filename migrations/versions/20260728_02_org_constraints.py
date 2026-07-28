"""R5-10 operations.organization_id NOT NULL + R5-11 Organization.status CHECK.

Revision ID: 20260728_02
Revises: 20260728_01
Create Date: 2026-07-28
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260728_02"
down_revision: str | None = "20260728_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # R5-10: operations.organization_id → NOT NULL
    # Delete orphan rows first (should be none in practice)
    op.execute("DELETE FROM operations WHERE organization_id IS NULL")
    op.alter_column(
        "operations",
        "organization_id",
        nullable=False,
    )

    # R5-11: Organization.status CHECK constraint
    op.execute(
        "ALTER TABLE organizations "
        "ADD CONSTRAINT ck_organizations_status "
        "CHECK (status IN ('active', 'suspended', 'deleted'))"
    )


def downgrade() -> None:
    op.drop_constraint("ck_organizations_status", "organizations", type_="check")
    op.alter_column(
        "operations",
        "organization_id",
        nullable=True,
    )
