from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class ResearchCase(Base):
    __tablename__ = "research_cases"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    case_type: Mapped[str] = mapped_column(sa.String(50))
    title: Mapped[str] = mapped_column(sa.String(300))
    priority: Mapped[str] = mapped_column(sa.String(20))
    state: Mapped[str] = mapped_column(sa.String(30), default="draft")
    issuer_id: Mapped[UUID] = mapped_column(sa.ForeignKey("issuers.id", ondelete="RESTRICT"), index=True)
    instrument_id: Mapped[UUID | None] = mapped_column(sa.ForeignKey("instruments.id", ondelete="RESTRICT"))
    data_as_of: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), index=True)
    due_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    created_by: Mapped[str] = mapped_column(sa.String(255))
    idempotency_key: Mapped[str] = mapped_column(sa.String(255), unique=True)
    request_hash: Mapped[str] = mapped_column(sa.String(64))
    lock_version: Mapped[int] = mapped_column(default=1)
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    __table_args__ = (
        sa.CheckConstraint("priority IN ('low', 'normal', 'high', 'critical')", name="priority_values"),
        sa.CheckConstraint(
            "state IN ('draft', 'triage', 'in_research', 'review', 'approved', 'rejected', 'closed')",
            name="state_values",
        ),
        sa.CheckConstraint("lock_version > 0", name="positive_lock_version"),
        sa.CheckConstraint("request_hash ~ '^[0-9a-f]{64}$'", name="request_hash_format"),
    )


class ResearchQuestion(Base):
    __tablename__ = "research_questions"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    research_case_id: Mapped[UUID] = mapped_column(sa.ForeignKey("research_cases.id", ondelete="CASCADE"), index=True)
    question: Mapped[str] = mapped_column(sa.Text)
    is_required: Mapped[bool] = mapped_column(default=True)
    status: Mapped[str] = mapped_column(sa.String(20), default="open")
    answer_summary: Mapped[str | None] = mapped_column(sa.Text)
    ordinal: Mapped[int]

    __table_args__ = (
        sa.UniqueConstraint("research_case_id", "ordinal", name="uq_research_questions_case_ordinal"),
        sa.CheckConstraint("status IN ('open', 'answered', 'waived')", name="status_values"),
        sa.CheckConstraint("ordinal >= 0", name="nonnegative_ordinal"),
    )


class ResearchAssignment(Base):
    __tablename__ = "research_assignments"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    research_case_id: Mapped[UUID] = mapped_column(sa.ForeignKey("research_cases.id", ondelete="CASCADE"), index=True)
    assignee_type: Mapped[str] = mapped_column(sa.String(20))
    assignee_id: Mapped[str] = mapped_column(sa.String(255))
    role: Mapped[str] = mapped_column(sa.String(50))
    assigned_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=utcnow)
    released_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))

    __table_args__ = (
        sa.UniqueConstraint(
            "research_case_id", "assignee_type", "assignee_id", "role", "assigned_at", name="uq_research_assignments"
        ),
        sa.CheckConstraint("assignee_type IN ('human', 'agent')", name="assignee_type_values"),
    )


class DomainOutboxEvent(Base):
    __tablename__ = "domain_outbox_events"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    aggregate_type: Mapped[str] = mapped_column(sa.String(50), index=True)
    aggregate_id: Mapped[UUID] = mapped_column(index=True)
    aggregate_version: Mapped[int]
    event_type: Mapped[str] = mapped_column(sa.String(100))
    payload: Mapped[dict[str, object]] = mapped_column(JSONB)
    correlation_id: Mapped[UUID] = mapped_column(index=True)
    idempotency_key: Mapped[str] = mapped_column(sa.String(255), unique=True)
    occurred_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=utcnow)
    published_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))


class ResearchEvidence(Base):
    __tablename__ = "research_evidence"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    research_case_id: Mapped[UUID] = mapped_column(sa.ForeignKey("research_cases.id", ondelete="CASCADE"), index=True)
    document_chunk_id: Mapped[UUID] = mapped_column(sa.ForeignKey("document_chunks.id", ondelete="RESTRICT"))
    source_object_version_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("source_object_versions.id", ondelete="RESTRICT")
    )
    license_id: Mapped[UUID] = mapped_column(sa.ForeignKey("source_licenses.id", ondelete="RESTRICT"))
    excerpt: Mapped[str] = mapped_column(sa.Text)
    excerpt_sha256: Mapped[str] = mapped_column(sa.String(64))
    page_start: Mapped[int]
    page_end: Mapped[int]
    section_path: Mapped[list[str]] = mapped_column(JSONB, default=list)
    quality_score: Mapped[Decimal] = mapped_column(sa.Numeric(5, 4))
    knowledge_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True))
    valid_until: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))

    __table_args__ = (
        sa.UniqueConstraint(
            "research_case_id", "document_chunk_id", "excerpt_sha256", name="uq_research_evidence_case_chunk"
        ),
        sa.CheckConstraint("excerpt_sha256 ~ '^[0-9a-f]{64}$'", name="sha256_format"),
        sa.CheckConstraint("page_start > 0 AND page_end >= page_start", name="valid_pages"),
        sa.CheckConstraint("quality_score BETWEEN 0 AND 1", name="quality_range"),
        sa.CheckConstraint("valid_until IS NULL OR valid_until > knowledge_at", name="valid_window"),
    )


class ResearchClaim(Base):
    __tablename__ = "research_claims"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    research_case_id: Mapped[UUID] = mapped_column(sa.ForeignKey("research_cases.id", ondelete="CASCADE"), index=True)
    claim_type: Mapped[str] = mapped_column(sa.String(20))
    text: Mapped[str] = mapped_column(sa.Text)
    text_sha256: Mapped[str] = mapped_column(sa.String(64))
    is_material: Mapped[bool]
    status: Mapped[str] = mapped_column(sa.String(20), default="draft")
    confidence: Mapped[Decimal] = mapped_column(sa.Numeric(5, 4))
    valid_from: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True))
    valid_until: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    created_by_type: Mapped[str] = mapped_column(sa.String(20))
    created_by_id: Mapped[str] = mapped_column(sa.String(255))

    __table_args__ = (
        sa.UniqueConstraint("research_case_id", "text_sha256", name="uq_research_claims_case_hash"),
        sa.CheckConstraint("claim_type IN ('fact', 'inference', 'recommendation')", name="claim_type_values"),
        sa.CheckConstraint("status IN ('draft', 'submitted', 'verified', 'rejected', 'revoked')", name="status_values"),
        sa.CheckConstraint("confidence BETWEEN 0 AND 1", name="confidence_range"),
        sa.CheckConstraint("valid_until IS NULL OR valid_until > valid_from", name="valid_window"),
        sa.CheckConstraint("created_by_type IN ('human', 'agent')", name="creator_type_values"),
    )


class ClaimEvidenceLink(Base):
    __tablename__ = "claim_evidence_links"

    claim_id: Mapped[UUID] = mapped_column(sa.ForeignKey("research_claims.id", ondelete="CASCADE"), primary_key=True)
    evidence_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("research_evidence.id", ondelete="RESTRICT"), primary_key=True
    )
    stance: Mapped[str] = mapped_column(sa.String(20))

    __table_args__ = (sa.CheckConstraint("stance IN ('supporting', 'opposing')", name="stance_values"),)


class ClaimContradiction(Base):
    __tablename__ = "claim_contradictions"

    claim_id: Mapped[UUID] = mapped_column(sa.ForeignKey("research_claims.id", ondelete="CASCADE"), primary_key=True)
    contradicts_claim_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("research_claims.id", ondelete="CASCADE"), primary_key=True
    )
    rationale: Mapped[str] = mapped_column(sa.Text)
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=utcnow)

    __table_args__ = (sa.CheckConstraint("claim_id <> contradicts_claim_id", name="different_claims"),)
