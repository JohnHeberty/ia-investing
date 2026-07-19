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


class ResearchThesis(Base):
    __tablename__ = "research_theses"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    issuer_id: Mapped[UUID] = mapped_column(sa.ForeignKey("issuers.id", ondelete="RESTRICT"), index=True)
    instrument_id: Mapped[UUID | None] = mapped_column(sa.ForeignKey("instruments.id", ondelete="RESTRICT"))
    status: Mapped[str] = mapped_column(sa.String(20), default="draft")
    lock_version: Mapped[int] = mapped_column(default=1)
    created_by: Mapped[str] = mapped_column(sa.String(255))
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=utcnow)

    __table_args__ = (
        sa.CheckConstraint("status IN ('draft', 'active', 'stale', 'closed')", name="status_values"),
        sa.CheckConstraint("lock_version > 0", name="positive_lock_version"),
    )


class ResearchThesisVersion(Base):
    __tablename__ = "research_thesis_versions"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    thesis_id: Mapped[UUID] = mapped_column(sa.ForeignKey("research_theses.id", ondelete="CASCADE"), index=True)
    version_number: Mapped[int]
    parent_version_id: Mapped[UUID | None] = mapped_column(
        sa.ForeignKey("research_thesis_versions.id", ondelete="RESTRICT")
    )
    status: Mapped[str] = mapped_column(sa.String(20), default="draft")
    summary: Mapped[str] = mapped_column(sa.Text)
    assumptions: Mapped[list[dict[str, object]]] = mapped_column(JSONB)
    catalysts: Mapped[list[dict[str, object]]] = mapped_column(JSONB)
    risks: Mapped[list[dict[str, object]]] = mapped_column(JSONB)
    invalidation_criteria: Mapped[list[dict[str, object]]] = mapped_column(JSONB)
    recommendation: Mapped[str] = mapped_column(sa.String(20))
    recommendation_confidence: Mapped[Decimal] = mapped_column(sa.Numeric(5, 4))
    data_as_of: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), index=True)
    expires_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), index=True)
    valid_from: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    valid_to: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    content_sha256: Mapped[str] = mapped_column(sa.String(64))
    change_set: Mapped[dict[str, object]] = mapped_column(JSONB)
    created_by: Mapped[str] = mapped_column(sa.String(255))
    approved_by: Mapped[str | None] = mapped_column(sa.String(255))
    approved_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    review_decision_id: Mapped[UUID | None] = mapped_column(sa.ForeignKey("review_decisions.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=utcnow)

    __table_args__ = (
        sa.UniqueConstraint("thesis_id", "version_number", name="uq_research_thesis_versions_number"),
        sa.CheckConstraint("version_number > 0", name="positive_version"),
        sa.CheckConstraint("status IN ('draft', 'active', 'rejected', 'superseded')", name="status_values"),
        sa.CheckConstraint("recommendation IN ('buy', 'hold', 'sell', 'watch')", name="recommendation_values"),
        sa.CheckConstraint("recommendation_confidence BETWEEN 0 AND 1", name="confidence_range"),
        sa.CheckConstraint("expires_at > data_as_of", name="valid_expiry"),
        sa.CheckConstraint(
            "valid_to IS NULL OR (valid_from IS NOT NULL AND valid_to > valid_from)", name="valid_window"
        ),
        sa.CheckConstraint("content_sha256 ~ '^[0-9a-f]{64}$'", name="sha256_format"),
        sa.Index(
            "uq_research_thesis_versions_one_active",
            "thesis_id",
            unique=True,
            postgresql_where=sa.text("status = 'active'"),
        ),
    )


class ThesisVersionEvidence(Base):
    __tablename__ = "thesis_version_evidence"

    thesis_version_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("research_thesis_versions.id", ondelete="CASCADE"), primary_key=True
    )
    evidence_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("research_evidence.id", ondelete="RESTRICT"), primary_key=True
    )
    role: Mapped[str] = mapped_column(sa.String(50))


class ThesisVersionClaim(Base):
    __tablename__ = "thesis_version_claims"

    thesis_version_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("research_thesis_versions.id", ondelete="CASCADE"), primary_key=True
    )
    claim_id: Mapped[UUID] = mapped_column(sa.ForeignKey("research_claims.id", ondelete="RESTRICT"), primary_key=True)
    role: Mapped[str] = mapped_column(sa.String(50))
