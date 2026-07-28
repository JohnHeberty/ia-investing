"""Add restricted_instruments table with exclusion constraint.

Revision ID: 20260726_01
Revises: b4c000000008
Create Date: 2026-07-26

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260726_01"
down_revision: str | None = "b4c000000008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "restricted_instruments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("instrument_id", sa.Uuid(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("active_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("active_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_restricted_instruments_organization_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["instrument_id"],
            ["instruments.id"],
            name="fk_restricted_instruments_instrument_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_restricted_instruments"),
        sa.CheckConstraint(
            "active_until IS NULL OR active_until > active_from",
            name="restricted_instrument_valid_window",
        ),
    )
    op.create_index("ix_restricted_instruments_organization_id", "restricted_instruments", ["organization_id"])
    op.create_index("ix_restricted_instruments_instrument_id", "restricted_instruments", ["instrument_id"])
    op.create_index("ix_restricted_instruments_active_from", "restricted_instruments", ["active_from"])
    op.create_index("ix_restricted_instruments_active_until", "restricted_instruments", ["active_until"])
    op.create_index(
        "ix_restricted_instrument_org_window",
        "restricted_instruments",
        ["organization_id", "active_from", "active_until"],
    )
    op.execute(
        "ALTER TABLE restricted_instruments "
        "ADD CONSTRAINT ex_restricted_instruments_active_window "
        "EXCLUDE USING gist "
        "(organization_id WITH =, instrument_id WITH =, "
        "tstzrange(active_from, active_until, '[)') WITH &&) "
        "WHERE (active_until IS NULL OR active_until > active_from)"
    )


def downgrade() -> None:
    op.drop_table("restricted_instruments")
