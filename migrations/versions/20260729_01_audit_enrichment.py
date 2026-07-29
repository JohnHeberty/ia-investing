"""Add HTTP context columns to audit_log_entries.

Revision ID: 20260729_01
Revises: 20260728_07
Create Date: 2026-07-29
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

revision = "20260729_01"
down_revision = "20260728_07"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("audit_log_entries", sa.Column("request_id", PG_UUID(as_uuid=True), nullable=True))
    op.add_column("audit_log_entries", sa.Column("http_method", sa.String(7), nullable=True))
    op.add_column("audit_log_entries", sa.Column("http_path", sa.String(500), nullable=True))
    op.add_column("audit_log_entries", sa.Column("duration_ms", sa.Float, nullable=True))
    op.add_column("audit_log_entries", sa.Column("status_code", sa.Integer, nullable=True))
    op.create_index("ix_audit_log_request_id", "audit_log_entries", ["request_id"])


def downgrade() -> None:
    op.drop_index("ix_audit_log_request_id", table_name="audit_log_entries")
    op.drop_column("audit_log_entries", "status_code")
    op.drop_column("audit_log_entries", "duration_ms")
    op.drop_column("audit_log_entries", "http_path")
    op.drop_column("audit_log_entries", "http_method")
    op.drop_column("audit_log_entries", "request_id")
