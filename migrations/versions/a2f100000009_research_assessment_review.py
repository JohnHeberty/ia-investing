"""research assessments and human review

Revision ID: a2f100000009
Revises: a2f100000008
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a2f100000009"
down_revision: str | Sequence[str] | None = "a2f100000008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "research_assessments",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("research_case_id", sa.UUID(), nullable=False),
        sa.Column("assessment_type", sa.String(50), nullable=False),
        sa.Column("author_type", sa.String(20), nullable=False),
        sa.Column("author_id", sa.String(255), nullable=False),
        sa.Column("schema_name", sa.String(100), nullable=False),
        sa.Column("schema_version", sa.String(50), nullable=False),
        sa.Column("result", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("result_sha256", sa.String(64), nullable=False),
        sa.Column("data_as_of", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "author_type IN ('human', 'agent')", name=op.f("ck_research_assessments_author_type_values")
        ),
        sa.CheckConstraint("expires_at > data_as_of", name=op.f("ck_research_assessments_valid_expiry")),
        sa.CheckConstraint("result_sha256 ~ '^[0-9a-f]{64}$'", name=op.f("ck_research_assessments_sha256_format")),
        sa.ForeignKeyConstraint(
            ["research_case_id"],
            ["research_cases.id"],
            name=op.f("fk_research_assessments_research_case_id_research_cases"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_research_assessments")),
    )
    op.create_index(op.f("ix_research_assessments_expires_at"), "research_assessments", ["expires_at"])
    op.create_index(op.f("ix_research_assessments_research_case_id"), "research_assessments", ["research_case_id"])
    op.create_table(
        "review_requests",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("assessment_id", sa.UUID(), nullable=False),
        sa.Column("required_reviewer_role", sa.String(100), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("requested_by", sa.String(255), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('pending', 'approved', 'rejected', 'changes_requested', 'expired')",
            name=op.f("ck_review_requests_status_values"),
        ),
        sa.ForeignKeyConstraint(
            ["assessment_id"],
            ["research_assessments.id"],
            name=op.f("fk_review_requests_assessment_id_research_assessments"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_review_requests")),
        sa.UniqueConstraint("assessment_id", name=op.f("uq_review_requests_assessment_id")),
    )
    op.create_table(
        "review_decisions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("review_request_id", sa.UUID(), nullable=False),
        sa.Column("reviewer_id", sa.String(255), nullable=False),
        sa.Column("decision", sa.String(30), nullable=False),
        sa.Column("comment", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("before_hash", sa.String(64), nullable=False),
        sa.Column("after_hash", sa.String(64), nullable=False),
        sa.Column("correlation_id", sa.UUID(), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("after_hash ~ '^[0-9a-f]{64}$'", name=op.f("ck_review_decisions_after_hash_format")),
        sa.CheckConstraint("before_hash ~ '^[0-9a-f]{64}$'", name=op.f("ck_review_decisions_before_hash_format")),
        sa.CheckConstraint(
            "decision IN ('approved', 'rejected', 'changes_requested')",
            name=op.f("ck_review_decisions_decision_values"),
        ),
        sa.ForeignKeyConstraint(
            ["review_request_id"],
            ["review_requests.id"],
            name=op.f("fk_review_decisions_review_request_id_review_requests"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_review_decisions")),
        sa.UniqueConstraint("review_request_id", name=op.f("uq_review_decisions_review_request_id")),
    )
    op.create_index(op.f("ix_review_decisions_correlation_id"), "review_decisions", ["correlation_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_review_decisions_correlation_id"), table_name="review_decisions")
    op.drop_table("review_decisions")
    op.drop_table("review_requests")
    op.drop_index(op.f("ix_research_assessments_research_case_id"), table_name="research_assessments")
    op.drop_index(op.f("ix_research_assessments_expires_at"), table_name="research_assessments")
    op.drop_table("research_assessments")
