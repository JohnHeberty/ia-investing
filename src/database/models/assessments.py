from datetime import datetime
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ._utils import utcnow
from .base import Base


class AgentAssessment(Base):
    __tablename__ = "agent_assessments"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    agent_run_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("agent_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    issuer_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("issuers.id", ondelete="SET NULL"),
    )

    assessment_type: Mapped[str] = mapped_column(sa.String(50))
    verdict: Mapped[str] = mapped_column(sa.String(20))
    confidence: Mapped[float] = mapped_column(sa.Float)

    thesis_effect: Mapped[str] = mapped_column(sa.String(20))
    materiality_score: Mapped[float] = mapped_column(sa.Float)
    time_horizon: Mapped[str] = mapped_column(sa.String(30))

    claims: Mapped[dict[str, object]] = mapped_column(JSONB)
    risks: Mapped[dict[str, object]] = mapped_column(JSONB)
    assumptions: Mapped[dict[str, object]] = mapped_column(JSONB)
    data_gaps: Mapped[dict[str, object]] = mapped_column(JSONB)
    invalidation_triggers: Mapped[dict[str, object]] = mapped_column(JSONB)

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=utcnow)

    def __repr__(self) -> str:
        return (
            f"AgentAssessment(assessment_type={self.assessment_type!r}, "
            f"verdict={self.verdict!r}, confidence={self.confidence})"
        )


class EvidenceItem(Base):
    __tablename__ = "evidence_items"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    assessment_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("agent_assessments.id", ondelete="CASCADE"),
        nullable=False,
    )

    claim_text: Mapped[str] = mapped_column(sa.Text)
    status: Mapped[str] = mapped_column(sa.String(20))

    source_document_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("raw_documents.id", ondelete="SET NULL"),
    )
    source_location: Mapped[str] = mapped_column(sa.Text)
    metric_ids: Mapped[dict[str, object]] = mapped_column(JSONB)

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=utcnow)

    def __repr__(self) -> str:
        return f"EvidenceItem(status={self.status!r}, source_location={self.source_location!r})"
