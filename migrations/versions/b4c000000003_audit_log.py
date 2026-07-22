"""add append-only audit log with hash-chain integrity

Revision ID: b4c000000003
Revises: b4c000000002

Creates the audit_log_entries table with:
- Blockchain-style hash chain (hash_prev → hash)
- Indexes for query by tenant, actor, resource
- Action check constraint
- Unique constraint on hash for integrity verification
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "b4c000000003"
down_revision: str | Sequence[str] | None = "b4c000000002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "audit_log_entries",
        sa.Column("id", UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("actor_id", UUID(as_uuid=True), nullable=True),
        sa.Column("action", sa.String(30), nullable=False),
        sa.Column("resource_type", sa.String(50), nullable=False),
        sa.Column("resource_id", UUID(as_uuid=True), nullable=True),
        sa.Column("changes", JSONB, nullable=True),
        sa.Column("metadata", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("hash_prev", sa.String(64), nullable=True),
        sa.Column("hash", sa.String(64), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["organizations.id"],
            ondelete="RESTRICT",
            name="fk_audit_log_entries_tenant_id_organizations",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_audit_log_entries"),
        sa.UniqueConstraint("hash", name="uq_audit_log_entries_hash"),
        sa.CheckConstraint(
            "action IN ('create','update','delete','read','execute','approve',"
            "'reject','login','logout','export','config_change')",
            name="ck_audit_log_action",
        ),
    )
    op.create_index(
        "ix_audit_log_tenant_timestamp",
        "audit_log_entries",
        ["tenant_id", "timestamp"],
    )
    op.create_index(
        "ix_audit_log_actor",
        "audit_log_entries",
        ["actor_id"],
    )
    op.create_index(
        "ix_audit_log_resource",
        "audit_log_entries",
        ["resource_type", "resource_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_audit_log_resource", table_name="audit_log_entries")
    op.drop_index("ix_audit_log_actor", table_name="audit_log_entries")
    op.drop_index("ix_audit_log_tenant_timestamp", table_name="audit_log_entries")
    op.drop_table("audit_log_entries")
