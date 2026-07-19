"""immutable versioned research theses

Revision ID: a2f100000010
Revises: a2f100000009
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a2f100000010"
down_revision: str | Sequence[str] | None = "a2f100000009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "research_theses",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("issuer_id", sa.UUID(), nullable=False),
        sa.Column("instrument_id", sa.UUID(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("lock_version", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("lock_version > 0", name=op.f("ck_research_theses_positive_lock_version")),
        sa.CheckConstraint(
            "status IN ('draft', 'active', 'stale', 'closed')", name=op.f("ck_research_theses_status_values")
        ),
        sa.ForeignKeyConstraint(
            ["instrument_id"],
            ["instruments.id"],
            name=op.f("fk_research_theses_instrument_id_instruments"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["issuer_id"], ["issuers.id"], name=op.f("fk_research_theses_issuer_id_issuers"), ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_research_theses")),
    )
    op.create_index(op.f("ix_research_theses_issuer_id"), "research_theses", ["issuer_id"])
    op.create_table(
        "research_thesis_versions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("thesis_id", sa.UUID(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("parent_version_id", sa.UUID(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("assumptions", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("catalysts", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("risks", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("invalidation_criteria", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("recommendation", sa.String(20), nullable=False),
        sa.Column("recommendation_confidence", sa.Numeric(5, 4), nullable=False),
        sa.Column("data_as_of", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("valid_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("content_sha256", sa.String(64), nullable=False),
        sa.Column("change_set", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_by", sa.String(255), nullable=False),
        sa.Column("approved_by", sa.String(255), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_decision_id", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("content_sha256 ~ '^[0-9a-f]{64}$'", name=op.f("ck_research_thesis_versions_sha256_format")),
        sa.CheckConstraint("expires_at > data_as_of", name=op.f("ck_research_thesis_versions_valid_expiry")),
        sa.CheckConstraint(
            "recommendation IN ('buy', 'hold', 'sell', 'watch')",
            name=op.f("ck_research_thesis_versions_recommendation_values"),
        ),
        sa.CheckConstraint(
            "recommendation_confidence BETWEEN 0 AND 1", name=op.f("ck_research_thesis_versions_confidence_range")
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'active', 'rejected', 'superseded')",
            name=op.f("ck_research_thesis_versions_status_values"),
        ),
        sa.CheckConstraint(
            "valid_to IS NULL OR (valid_from IS NOT NULL AND valid_to > valid_from)",
            name=op.f("ck_research_thesis_versions_valid_window"),
        ),
        sa.CheckConstraint("version_number > 0", name=op.f("ck_research_thesis_versions_positive_version")),
        sa.ForeignKeyConstraint(
            ["parent_version_id"],
            ["research_thesis_versions.id"],
            name=op.f("fk_research_thesis_versions_parent_version_id_research_thesis_versions"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["review_decision_id"],
            ["review_decisions.id"],
            name=op.f("fk_research_thesis_versions_review_decision_id_review_decisions"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["thesis_id"],
            ["research_theses.id"],
            name=op.f("fk_research_thesis_versions_thesis_id_research_theses"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_research_thesis_versions")),
        sa.UniqueConstraint("thesis_id", "version_number", name="uq_research_thesis_versions_number"),
    )
    op.create_index(op.f("ix_research_thesis_versions_data_as_of"), "research_thesis_versions", ["data_as_of"])
    op.create_index(op.f("ix_research_thesis_versions_expires_at"), "research_thesis_versions", ["expires_at"])
    op.create_index(op.f("ix_research_thesis_versions_thesis_id"), "research_thesis_versions", ["thesis_id"])
    op.create_index(
        "uq_research_thesis_versions_one_active",
        "research_thesis_versions",
        ["thesis_id"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )
    op.create_table(
        "thesis_version_claims",
        sa.Column("thesis_version_id", sa.UUID(), nullable=False),
        sa.Column("claim_id", sa.UUID(), nullable=False),
        sa.Column("role", sa.String(50), nullable=False),
        sa.ForeignKeyConstraint(
            ["claim_id"],
            ["research_claims.id"],
            name=op.f("fk_thesis_version_claims_claim_id_research_claims"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["thesis_version_id"],
            ["research_thesis_versions.id"],
            name=op.f("fk_thesis_version_claims_thesis_version_id_research_thesis_versions"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("thesis_version_id", "claim_id", name=op.f("pk_thesis_version_claims")),
    )
    op.create_table(
        "thesis_version_evidence",
        sa.Column("thesis_version_id", sa.UUID(), nullable=False),
        sa.Column("evidence_id", sa.UUID(), nullable=False),
        sa.Column("role", sa.String(50), nullable=False),
        sa.ForeignKeyConstraint(
            ["evidence_id"],
            ["research_evidence.id"],
            name=op.f("fk_thesis_version_evidence_evidence_id_research_evidence"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["thesis_version_id"],
            ["research_thesis_versions.id"],
            name=op.f("fk_thesis_version_evidence_thesis_version_id_research_thesis_versions"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("thesis_version_id", "evidence_id", name=op.f("pk_thesis_version_evidence")),
    )


def downgrade() -> None:
    op.drop_table("thesis_version_evidence")
    op.drop_table("thesis_version_claims")
    op.drop_index("uq_research_thesis_versions_one_active", table_name="research_thesis_versions")
    op.drop_index(op.f("ix_research_thesis_versions_thesis_id"), table_name="research_thesis_versions")
    op.drop_index(op.f("ix_research_thesis_versions_expires_at"), table_name="research_thesis_versions")
    op.drop_index(op.f("ix_research_thesis_versions_data_as_of"), table_name="research_thesis_versions")
    op.drop_table("research_thesis_versions")
    op.drop_index(op.f("ix_research_theses_issuer_id"), table_name="research_theses")
    op.drop_table("research_theses")
