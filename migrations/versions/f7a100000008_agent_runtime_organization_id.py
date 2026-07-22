"""Add organization_id to agent_runtime_runs for tenant-scoped execution.

Revision ID: f7a100000008
Revises: 20260722_01
Create Date: 2026-07-22
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f7a100000008"
down_revision: str | Sequence[str] | None = "20260722_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("agent_runtime_runs", sa.Column("organization_id", sa.Uuid(), nullable=False))
    op.create_index("ix_agent_runtime_runs_organization_id", "agent_runtime_runs", ["organization_id"])
    op.create_foreign_key(
        "fk_agent_runtime_runs_organization_id",
        "agent_runtime_runs",
        "organizations",
        ["organization_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.drop_constraint("uq_agent_runtime_runs_capability_idempotency", "agent_runtime_runs", type_="unique")
    op.create_unique_constraint(
        "uq_agent_runtime_runs_org_capability_idempotency",
        "agent_runtime_runs",
        ["organization_id", "capability_id", "idempotency_key"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_agent_runtime_runs_org_capability_idempotency", "agent_runtime_runs", type_="unique")
    op.create_unique_constraint(
        "uq_agent_runtime_runs_capability_idempotency", "agent_runtime_runs", ["capability_id", "idempotency_key"]
    )
    op.drop_constraint("fk_agent_runtime_runs_organization_id", "agent_runtime_runs", type_="foreignkey")
    op.drop_index("ix_agent_runtime_runs_organization_id", "agent_runtime_runs")
    op.drop_column("agent_runtime_runs", "organization_id")
