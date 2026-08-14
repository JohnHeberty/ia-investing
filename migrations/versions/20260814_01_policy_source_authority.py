"""Add authority and fetch tracking to policy_sources.

Revision ID: 20260814_01
Revises: 20260813_06
Create Date: 2026-08-14
"""
from alembic import op
import sqlalchemy as sa

revision = "20260814_01"
down_revision = "20260813_06"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("policy_sources", sa.Column("authority", sa.String(100), nullable=False, server_default="camara"))
    op.add_column("policy_sources", sa.Column("fetch_config", sa.JSON(), nullable=False, server_default=sa.text("'{}'::jsonb")))
    op.add_column("policy_sources", sa.Column("last_fetch_error", sa.Text(), nullable=True))
    op.add_column("policy_sources", sa.Column("last_fetch_error_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("uq_active_policy_source_authority", "policy_sources", ["authority"], unique=True, postgresql_where=sa.text("is_active = true"))


def downgrade() -> None:
    op.drop_index("uq_active_policy_source_authority", table_name="policy_sources")
    op.drop_column("policy_sources", "last_fetch_error_at")
    op.drop_column("policy_sources", "last_fetch_error")
    op.drop_column("policy_sources", "fetch_config")
    op.drop_column("policy_sources", "authority")
