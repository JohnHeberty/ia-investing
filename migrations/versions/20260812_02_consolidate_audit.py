"""Consolidate audit: add actor_type, correlation_id to audit_log_entries; migrate data from audit_logs.

Revision ID: 20260812_02
Revises: 20260812_01
Create Date: 2026-08-12
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

revision: str = "20260812_02"
down_revision: str | Sequence[str] | None = "20260812_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Add actor_type column with default
    op.add_column(
        "audit_log_entries",
        sa.Column("actor_type", sa.String(50), nullable=False, server_default="human"),
    )

    # 2. Add correlation_id column (nullable)
    op.add_column(
        "audit_log_entries",
        sa.Column("correlation_id", PG_UUID(as_uuid=True), nullable=True),
    )

    # 3. Create index on correlation_id
    op.create_index("ix_audit_log_correlation", "audit_log_entries", ["correlation_id"])

    # 4. Add check constraint for actor_type
    op.create_check_constraint(
        "ck_audit_log_actor_type",
        "audit_log_entries",
        "actor_type IN ('human', 'system')",
    )

    # 5. Expand action check constraint to allow dot notation (e.g. agent_run.submit)
    op.execute("ALTER TABLE audit_log_entries DROP CONSTRAINT IF EXISTS ck_audit_log_action")
    op.create_check_constraint(
        "ck_audit_log_action",
        "audit_log_entries",
        "action ~ '^[a-z][a-z0-9_.:-]{0,99}$'",
    )

    # 6. Migrate data from audit_logs if it exists
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'audit_logs') THEN
                INSERT INTO audit_log_entries (
                    tenant_id, actor_type, actor_id, action, resource_type, resource_id,
                    correlation_id, changes, hash_prev, hash, timestamp, created_at
                )
                SELECT
                    COALESCE(al.organization_id, '00000000-0000-0000-0000-000000000000'::uuid),
                    COALESCE(al.actor_type, 'human'),
                    NULL,
                    al.action,
                    al.entity_type,
                    al.entity_id,
                    al.correlation_id,
                    al.details,
                    NULL,
                    md5(al.id::text || al.created_at::text),
                    al.created_at,
                    al.created_at
                FROM audit_logs al
                ON CONFLICT (hash) DO NOTHING;

                DROP TABLE IF EXISTS audit_logs;
            END IF;
        END $$;
        """
    )

    # 7. Remove server default after migration
    op.alter_column(
        "audit_log_entries",
        "actor_type",
        server_default=None,
    )


def downgrade() -> None:
    op.execute("ALTER TABLE audit_log_entries DROP CONSTRAINT IF EXISTS ck_audit_log_actor_type")
    op.drop_index("ix_audit_log_correlation", table_name="audit_log_entries")
    op.drop_column("audit_log_entries", "correlation_id")
    op.drop_column("audit_log_entries", "actor_type")

    # Restore original action check constraint
    op.execute("ALTER TABLE audit_log_entries DROP CONSTRAINT IF EXISTS ck_audit_log_action")
    op.execute(
        "ALTER TABLE audit_log_entries ADD CONSTRAINT ck_audit_log_action "
        "CHECK (action IN ('create','update','delete','read','execute','approve',"
        "'reject','login','logout','export','config_change'))"
    )
