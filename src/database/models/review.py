from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class ResearchAssessment(Base):
    __tablename__ = "research_assessments"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    research_case_id: Mapped[UUID] = mapped_column(sa.ForeignKey("research_cases.id", ondelete="CASCADE"), index=True)
    assessment_type: Mapped[str] = mapped_column(sa.String(50))
    author_type: Mapped[str] = mapped_column(sa.String(20))
    author_id: Mapped[str] = mapped_column(sa.String(255))
    schema_name: Mapped[str] = mapped_column(sa.String(100))
    schema_version: Mapped[str] = mapped_column(sa.String(50))
    result: Mapped[dict[str, object]] = mapped_column(JSONB)
    result_sha256: Mapped[str] = mapped_column(sa.String(64))
    data_as_of: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=utcnow)

    __table_args__ = (
        sa.CheckConstraint("author_type IN ('human', 'agent')", name="author_type_values"),
        sa.CheckConstraint("result_sha256 ~ '^[0-9a-f]{64}$'", name="sha256_format"),
        sa.CheckConstraint("expires_at > data_as_of", name="valid_expiry"),
    )


class ReviewRequest(Base):
    __tablename__ = "review_requests"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    assessment_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("research_assessments.id", ondelete="CASCADE"), unique=True
    )
    required_reviewer_role: Mapped[str] = mapped_column(sa.String(100))
    status: Mapped[str] = mapped_column(sa.String(30), default="pending")
    requested_by: Mapped[str] = mapped_column(sa.String(255))
    requested_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=utcnow)
    due_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))

    __table_args__ = (
        sa.CheckConstraint(
            "status IN ('pending', 'approved', 'rejected', 'changes_requested', 'expired')", name="status_values"
        ),
    )


class ReviewDecision(Base):
    __tablename__ = "review_decisions"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    review_request_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("review_requests.id", ondelete="CASCADE"), unique=True
    )
    reviewer_id: Mapped[str] = mapped_column(sa.String(255))
    decision: Mapped[str] = mapped_column(sa.String(30))
    comment: Mapped[str] = mapped_column(sa.Text)
    reason: Mapped[str] = mapped_column(sa.Text)
    before_hash: Mapped[str] = mapped_column(sa.String(64))
    after_hash: Mapped[str] = mapped_column(sa.String(64))
    correlation_id: Mapped[UUID] = mapped_column(index=True)
    decided_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=utcnow)

    __table_args__ = (
        sa.CheckConstraint("decision IN ('approved', 'rejected', 'changes_requested')", name="decision_values"),
        sa.CheckConstraint("before_hash ~ '^[0-9a-f]{64}$'", name="before_hash_format"),
        sa.CheckConstraint("after_hash ~ '^[0-9a-f]{64}$'", name="after_hash_format"),
    )
