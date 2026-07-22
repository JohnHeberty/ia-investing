"""add tenant scope to research cases, agent runs and operations

Revision ID: b4c000000002
Revises: b4c000000001

Existing unscoped rows remain NULL and are intentionally invisible to tenant-scoped
APIs until an operator assigns them to an organization. New application writes
must always provide organization_id.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b4c000000002"
down_revision: str | Sequence[str] | None = "b4c000000001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("research_cases", sa.Column("organization_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_research_cases_organization_id_organizations",
        "research_cases",
        "organizations",
        ["organization_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index("ix_research_cases_organization_id", "research_cases", ["organization_id"])
    op.drop_constraint("uq_research_cases_idempotency_key", "research_cases", type_="unique")
    op.create_unique_constraint(
        "uq_research_cases_organization_idempotency_key",
        "research_cases",
        ["organization_id", "idempotency_key"],
    )

    op.add_column("agent_runtime_runs", sa.Column("organization_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_agent_runtime_runs_organization_id_organizations",
        "agent_runtime_runs",
        "organizations",
        ["organization_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index("ix_agent_runtime_runs_organization_id", "agent_runtime_runs", ["organization_id"])
    op.drop_constraint(
        "uq_agent_runtime_runs_capability_idempotency",
        "agent_runtime_runs",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_agent_runtime_runs_org_capability_idempotency",
        "agent_runtime_runs",
        ["organization_id", "capability_id", "idempotency_key"],
    )

    op.add_column("operations", sa.Column("organization_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_operations_organization_id_organizations",
        "operations",
        "organizations",
        ["organization_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index("ix_operations_organization_id", "operations", ["organization_id"])
    op.drop_constraint("uq_operations_type_idempotency_key", "operations", type_="unique")
    op.create_unique_constraint(
        "uq_operations_org_type_idempotency_key",
        "operations",
        ["organization_id", "operation_type", "idempotency_key"],
    )

    op.create_table(
        "operation_dispatch_outbox",
        sa.Column("id", sa.Uuid(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("operation_id", sa.Uuid(), nullable=False),
        sa.Column("topic", sa.String(length=100), nullable=False),
        sa.Column("state", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("dispatched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.String(length=200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint(
            "state IN ('pending', 'dispatched', 'failed')",
            name="operation_dispatch_outbox_state",
        ),
        sa.CheckConstraint(
            "attempts >= 0",
            name="operation_dispatch_outbox_attempts_nonnegative",
        ),
        sa.ForeignKeyConstraint(
            ["operation_id"],
            ["operations.id"],
            ondelete="CASCADE",
            name="fk_operation_dispatch_outbox_operation_id_operations",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            ondelete="RESTRICT",
            name="fk_operation_dispatch_outbox_organization_id_organizations",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_operation_dispatch_outbox"),
        sa.UniqueConstraint("operation_id", name="uq_operation_dispatch_outbox_operation_id"),
    )
    op.create_index(
        "ix_operation_dispatch_outbox_organization_id",
        "operation_dispatch_outbox",
        ["organization_id"],
    )
    op.create_index(
        "ix_operation_dispatch_outbox_pending",
        "operation_dispatch_outbox",
        ["state", "next_attempt_at"],
        postgresql_where=sa.text("state = 'pending'"),
    )


def downgrade() -> None:
    op.drop_index("ix_operation_dispatch_outbox_pending", table_name="operation_dispatch_outbox")
    op.drop_index("ix_operation_dispatch_outbox_organization_id", table_name="operation_dispatch_outbox")
    op.drop_table("operation_dispatch_outbox")

    op.drop_constraint("uq_operations_org_type_idempotency_key", "operations", type_="unique")
    op.create_unique_constraint(
        "uq_operations_type_idempotency_key",
        "operations",
        ["operation_type", "idempotency_key"],
    )
    op.drop_index("ix_operations_organization_id", table_name="operations")
    op.drop_constraint(
        "fk_operations_organization_id_organizations",
        "operations",
        type_="foreignkey",
    )
    op.drop_column("operations", "organization_id")

    op.drop_constraint(
        "uq_agent_runtime_runs_org_capability_idempotency",
        "agent_runtime_runs",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_agent_runtime_runs_capability_idempotency",
        "agent_runtime_runs",
        ["capability_id", "idempotency_key"],
    )
    op.drop_index("ix_agent_runtime_runs_organization_id", table_name="agent_runtime_runs")
    op.drop_constraint(
        "fk_agent_runtime_runs_organization_id_organizations",
        "agent_runtime_runs",
        type_="foreignkey",
    )
    op.drop_column("agent_runtime_runs", "organization_id")

    op.drop_constraint(
        "uq_research_cases_organization_idempotency_key",
        "research_cases",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_research_cases_idempotency_key",
        "research_cases",
        ["idempotency_key"],
    )
    op.drop_index("ix_research_cases_organization_id", table_name="research_cases")
    op.drop_constraint(
        "fk_research_cases_organization_id_organizations",
        "research_cases",
        type_="foreignkey",
    )
    op.drop_column("research_cases", "organization_id")
