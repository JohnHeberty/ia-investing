"""Drop 13 dead tables whose ORM models were removed.

Revision ID: 20260728_04
Revises: 20260728_03
Create Date: 2026-07-28
"""

import sqlalchemy as sa
from alembic import op

revision: str = "20260728_04"
down_revision: str | None = "20260728_merge"
branch_labels: str | None = None
depends_on: str | None = None

# Tables that are confirmed dead (zero app code usage, no dependents).
DEAD_TABLES = [
    # portfolio_models.py — replaced by rebalance.py
    "proposed_trades",
    "rebalance_proposals",
    # definitions.py — replaced by agent_runtime.py
    "agent_tool_calls",
    "agent_runs",
    "agent_definitions",
    # assessments.py — zero usage
    "evidence_items",
    "agent_assessments",
    # audit_models.py — zero usage (AuditLog kept)
    "evaluation_results",
    "execution_reconciliations",
    "approvals",
    # thesis.py — replaced by thesis_domain.py
    "recommendations",
    "thesis_versions",
    "investment_theses",
]


def upgrade() -> None:
    for table in DEAD_TABLES:
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")


def downgrade() -> None:
    # Recreate empty tables for rollback (structure only, no data).
    for table in DEAD_TABLES:
        op.create_table(
            table,
            sa.Column("id", sa.Uuid(), primary_key=True),
        )
