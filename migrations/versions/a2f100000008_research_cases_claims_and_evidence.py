"""research cases, claims, evidence, and outbox

Revision ID: a2f100000008
Revises: a2f100000007
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a2f100000008"
down_revision: str | Sequence[str] | None = "a2f100000007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "domain_outbox_events",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("aggregate_type", sa.String(50), nullable=False),
        sa.Column("aggregate_id", sa.UUID(), nullable=False),
        sa.Column("aggregate_version", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("correlation_id", sa.UUID(), nullable=False),
        sa.Column("idempotency_key", sa.String(255), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_domain_outbox_events")),
        sa.UniqueConstraint("idempotency_key", name=op.f("uq_domain_outbox_events_idempotency_key")),
    )
    for column in ("aggregate_type", "aggregate_id", "correlation_id"):
        op.create_index(op.f(f"ix_domain_outbox_events_{column}"), "domain_outbox_events", [column])
    op.create_table(
        "research_cases",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("case_type", sa.String(50), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("priority", sa.String(20), nullable=False),
        sa.Column("state", sa.String(30), nullable=False),
        sa.Column("issuer_id", sa.UUID(), nullable=False),
        sa.Column("instrument_id", sa.UUID(), nullable=True),
        sa.Column("data_as_of", sa.DateTime(timezone=True), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.String(255), nullable=False),
        sa.Column("idempotency_key", sa.String(255), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("lock_version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("lock_version > 0", name=op.f("ck_research_cases_positive_lock_version")),
        sa.CheckConstraint(
            "request_hash ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_research_cases_request_hash_format"),
        ),
        sa.CheckConstraint(
            "priority IN ('low', 'normal', 'high', 'critical')", name=op.f("ck_research_cases_priority_values")
        ),
        sa.CheckConstraint(
            "state IN ('draft', 'triage', 'in_research', 'review', 'approved', 'rejected', 'closed')",
            name=op.f("ck_research_cases_state_values"),
        ),
        sa.ForeignKeyConstraint(
            ["instrument_id"],
            ["instruments.id"],
            name=op.f("fk_research_cases_instrument_id_instruments"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["issuer_id"], ["issuers.id"], name=op.f("fk_research_cases_issuer_id_issuers"), ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_research_cases")),
        sa.UniqueConstraint("idempotency_key", name=op.f("uq_research_cases_idempotency_key")),
    )
    op.create_index(op.f("ix_research_cases_data_as_of"), "research_cases", ["data_as_of"])
    op.create_index(op.f("ix_research_cases_issuer_id"), "research_cases", ["issuer_id"])
    op.create_table(
        "research_assignments",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("research_case_id", sa.UUID(), nullable=False),
        sa.Column("assignee_type", sa.String(20), nullable=False),
        sa.Column("assignee_id", sa.String(255), nullable=False),
        sa.Column("role", sa.String(50), nullable=False),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "assignee_type IN ('human', 'agent')", name=op.f("ck_research_assignments_assignee_type_values")
        ),
        sa.ForeignKeyConstraint(
            ["research_case_id"],
            ["research_cases.id"],
            name=op.f("fk_research_assignments_research_case_id_research_cases"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_research_assignments")),
        sa.UniqueConstraint(
            "research_case_id", "assignee_type", "assignee_id", "role", "assigned_at", name="uq_research_assignments"
        ),
    )
    op.create_index(op.f("ix_research_assignments_research_case_id"), "research_assignments", ["research_case_id"])
    op.create_table(
        "research_questions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("research_case_id", sa.UUID(), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("is_required", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("answer_summary", sa.Text(), nullable=True),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.CheckConstraint("ordinal >= 0", name=op.f("ck_research_questions_nonnegative_ordinal")),
        sa.CheckConstraint(
            "status IN ('open', 'answered', 'waived')", name=op.f("ck_research_questions_status_values")
        ),
        sa.ForeignKeyConstraint(
            ["research_case_id"],
            ["research_cases.id"],
            name=op.f("fk_research_questions_research_case_id_research_cases"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_research_questions")),
        sa.UniqueConstraint("research_case_id", "ordinal", name="uq_research_questions_case_ordinal"),
    )
    op.create_index(op.f("ix_research_questions_research_case_id"), "research_questions", ["research_case_id"])
    op.create_table(
        "research_evidence",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("research_case_id", sa.UUID(), nullable=False),
        sa.Column("document_chunk_id", sa.UUID(), nullable=False),
        sa.Column("source_object_version_id", sa.UUID(), nullable=False),
        sa.Column("license_id", sa.UUID(), nullable=False),
        sa.Column("excerpt", sa.Text(), nullable=False),
        sa.Column("excerpt_sha256", sa.String(64), nullable=False),
        sa.Column("page_start", sa.Integer(), nullable=False),
        sa.Column("page_end", sa.Integer(), nullable=False),
        sa.Column("section_path", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("quality_score", sa.Numeric(5, 4), nullable=False),
        sa.Column("knowledge_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("excerpt_sha256 ~ '^[0-9a-f]{64}$'", name=op.f("ck_research_evidence_sha256_format")),
        sa.CheckConstraint("page_start > 0 AND page_end >= page_start", name=op.f("ck_research_evidence_valid_pages")),
        sa.CheckConstraint("quality_score BETWEEN 0 AND 1", name=op.f("ck_research_evidence_quality_range")),
        sa.CheckConstraint(
            "valid_until IS NULL OR valid_until > knowledge_at", name=op.f("ck_research_evidence_valid_window")
        ),
        sa.ForeignKeyConstraint(
            ["document_chunk_id"],
            ["document_chunks.id"],
            name=op.f("fk_research_evidence_document_chunk_id_document_chunks"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["license_id"],
            ["source_licenses.id"],
            name=op.f("fk_research_evidence_license_id_source_licenses"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["research_case_id"],
            ["research_cases.id"],
            name=op.f("fk_research_evidence_research_case_id_research_cases"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_object_version_id"],
            ["source_object_versions.id"],
            name=op.f("fk_research_evidence_source_object_version_id_source_object_versions"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_research_evidence")),
        sa.UniqueConstraint(
            "research_case_id", "document_chunk_id", "excerpt_sha256", name="uq_research_evidence_case_chunk"
        ),
    )
    op.create_index(op.f("ix_research_evidence_research_case_id"), "research_evidence", ["research_case_id"])
    op.create_table(
        "research_claims",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("research_case_id", sa.UUID(), nullable=False),
        sa.Column("claim_type", sa.String(20), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("text_sha256", sa.String(64), nullable=False),
        sa.Column("is_material", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_type", sa.String(20), nullable=False),
        sa.Column("created_by_id", sa.String(255), nullable=False),
        sa.CheckConstraint(
            "claim_type IN ('fact', 'inference', 'recommendation')", name=op.f("ck_research_claims_claim_type_values")
        ),
        sa.CheckConstraint("confidence BETWEEN 0 AND 1", name=op.f("ck_research_claims_confidence_range")),
        sa.CheckConstraint(
            "created_by_type IN ('human', 'agent')", name=op.f("ck_research_claims_creator_type_values")
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'submitted', 'verified', 'rejected', 'revoked')",
            name=op.f("ck_research_claims_status_values"),
        ),
        sa.CheckConstraint(
            "valid_until IS NULL OR valid_until > valid_from", name=op.f("ck_research_claims_valid_window")
        ),
        sa.ForeignKeyConstraint(
            ["research_case_id"],
            ["research_cases.id"],
            name=op.f("fk_research_claims_research_case_id_research_cases"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_research_claims")),
        sa.UniqueConstraint("research_case_id", "text_sha256", name="uq_research_claims_case_hash"),
    )
    op.create_index(op.f("ix_research_claims_research_case_id"), "research_claims", ["research_case_id"])
    op.create_table(
        "claim_contradictions",
        sa.Column("claim_id", sa.UUID(), nullable=False),
        sa.Column("contradicts_claim_id", sa.UUID(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("claim_id <> contradicts_claim_id", name=op.f("ck_claim_contradictions_different_claims")),
        sa.ForeignKeyConstraint(
            ["claim_id"],
            ["research_claims.id"],
            name=op.f("fk_claim_contradictions_claim_id_research_claims"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["contradicts_claim_id"],
            ["research_claims.id"],
            name=op.f("fk_claim_contradictions_contradicts_claim_id_research_claims"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("claim_id", "contradicts_claim_id", name=op.f("pk_claim_contradictions")),
    )
    op.create_table(
        "claim_evidence_links",
        sa.Column("claim_id", sa.UUID(), nullable=False),
        sa.Column("evidence_id", sa.UUID(), nullable=False),
        sa.Column("stance", sa.String(20), nullable=False),
        sa.CheckConstraint("stance IN ('supporting', 'opposing')", name=op.f("ck_claim_evidence_links_stance_values")),
        sa.ForeignKeyConstraint(
            ["claim_id"],
            ["research_claims.id"],
            name=op.f("fk_claim_evidence_links_claim_id_research_claims"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["evidence_id"],
            ["research_evidence.id"],
            name=op.f("fk_claim_evidence_links_evidence_id_research_evidence"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("claim_id", "evidence_id", name=op.f("pk_claim_evidence_links")),
    )


def downgrade() -> None:
    op.drop_table("claim_evidence_links")
    op.drop_table("claim_contradictions")
    op.drop_index(op.f("ix_research_claims_research_case_id"), table_name="research_claims")
    op.drop_table("research_claims")
    op.drop_index(op.f("ix_research_evidence_research_case_id"), table_name="research_evidence")
    op.drop_table("research_evidence")
    op.drop_index(op.f("ix_research_questions_research_case_id"), table_name="research_questions")
    op.drop_table("research_questions")
    op.drop_index(op.f("ix_research_assignments_research_case_id"), table_name="research_assignments")
    op.drop_table("research_assignments")
    op.drop_index(op.f("ix_research_cases_issuer_id"), table_name="research_cases")
    op.drop_index(op.f("ix_research_cases_data_as_of"), table_name="research_cases")
    op.drop_table("research_cases")
    for column in ("correlation_id", "aggregate_id", "aggregate_type"):
        op.drop_index(op.f(f"ix_domain_outbox_events_{column}"), table_name="domain_outbox_events")
    op.drop_table("domain_outbox_events")
