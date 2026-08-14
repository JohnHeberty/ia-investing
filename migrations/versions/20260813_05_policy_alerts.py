"""Add policy_alerts table and performance indexes.

Revision ID: 20260813_05
Revises: 20260813_04
Create Date: 2026-08-13
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "20260813_05"
down_revision: str | Sequence[str] | None = "20260813_04"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "policy_alerts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("policy_object_id", sa.Uuid(), sa.ForeignKey("policy_objects.id"), nullable=False),
        sa.Column("alert_type", sa.String(50), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("details", JSONB()),
        sa.Column("fired_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True)),
        sa.Column("acknowledged_by", sa.String(200)),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.Column("resolved_by", sa.String(200)),
        sa.Column("resolution_notes", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )
    op.create_index("ix_policy_alerts_policy_object_id", "policy_alerts", ["policy_object_id"])
    op.create_index("ix_policy_alerts_fired_at", "policy_alerts", ["fired_at"])

    op.create_index(
        "ix_policy_stage_events_object_stage",
        "policy_stage_events",
        ["policy_object_id", "stage"],
    )
    op.create_index(
        "ix_regulatory_actions_authority",
        "regulatory_actions",
        ["authority"],
    )
    op.create_index(
        "ix_regulatory_actions_action_type",
        "regulatory_actions",
        ["action_type"],
    )


def downgrade() -> None:
    op.drop_index("ix_regulatory_actions_action_type", table_name="regulatory_actions")
    op.drop_index("ix_regulatory_actions_authority", table_name="regulatory_actions")
    op.drop_index("ix_policy_stage_events_object_stage", table_name="policy_stage_events")
    op.drop_index("ix_policy_alerts_fired_at", table_name="policy_alerts")
    op.drop_index("ix_policy_alerts_policy_object_id", table_name="policy_alerts")
    op.drop_table("policy_alerts")
