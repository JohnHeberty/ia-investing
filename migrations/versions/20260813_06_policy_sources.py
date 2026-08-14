"""Add policy_sources table.

Revision ID: 20260813_06
Revises: 20260813_05
Create Date: 2026-08-13
"""
from alembic import op
import sqlalchemy as sa

revision = "20260813_06"
down_revision = "20260813_05"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "policy_sources",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("source_type", sa.String(100), nullable=True),
        sa.Column("url_pattern", sa.Text, nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("last_fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_policy_sources_name", "policy_sources", ["name"])


def downgrade() -> None:
    op.drop_index("ix_policy_sources_name", table_name="policy_sources")
    op.drop_table("policy_sources")
