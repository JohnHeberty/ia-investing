"""add tenant scope to remaining models

Revision ID: b4c000000007
Revises: b4c000000006, 20260722_01

Adds organization_id to: committee_sessions, committee_votes,
committee_decisions, audit_logs, investment_theses, thesis_versions,
recommendations, research_theses, research_thesis_versions,
agent_definitions, agent_runs, agent_tool_calls,
data_quality_checks, data_refresh_log, research_assessments,
review_requests, review_decisions, document_chunks,
research_questions, research_assignments, research_evidence, research_claims.

Existing unscoped rows remain NULL and are intentionally invisible to
tenant-scoped APIs until an operator assigns them to an organization.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b4c000000007"
down_revision: str | Sequence[str] | None = ("b4c000000006", "20260722_01")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLES = [
    # committee
    "committee_sessions",
    "committee_votes",
    "committee_decisions",
    # audit
    "audit_logs",
    # thesis
    "investment_theses",
    "thesis_versions",
    "recommendations",
    # thesis_domain
    "research_theses",
    "research_thesis_versions",
    # definitions (legacy agent)
    "agent_definitions",
    "agent_runs",
    "agent_tool_calls",
    # quality
    "data_quality_checks",
    "data_refresh_log",
    # review
    "research_assessments",
    "review_requests",
    "review_decisions",
    # evidence
    "document_chunks",
    # research (children of research_cases which already has org_id)
    "research_questions",
    "research_assignments",
    "research_evidence",
    "research_claims",
]


def upgrade() -> None:
    for table in _TABLES:
        op.add_column(table, sa.Column("organization_id", sa.Uuid(), nullable=True))
        op.create_foreign_key(
            f"fk_{table}_organization_id_organizations",
            table,
            "organizations",
            ["organization_id"],
            ["id"],
            ondelete="CASCADE",
        )
        op.create_index(f"ix_{table}_organization_id", table, ["organization_id"])


def downgrade() -> None:
    for table in reversed(_TABLES):
        op.drop_index(f"ix_{table}_organization_id", table_name=table)
        op.drop_constraint(f"fk_{table}_organization_id_organizations", table, type_="foreignkey")
        op.drop_column(table, "organization_id")
