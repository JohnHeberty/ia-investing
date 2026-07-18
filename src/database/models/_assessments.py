from datetime import UTC, datetime

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from .base import Base


class AgentAssessment(Base):
    __tablename__ = "agent_assessments"

    id = sa.Column(UUID(as_uuid=True), primary_key=True, default=sa.func.gen_random_uuid())
    agent_run_id = sa.Column(
        UUID(as_uuid=True), sa.ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=False,
    )
    issuer_id = sa.Column(
        UUID(as_uuid=True), sa.ForeignKey("issuers.id", ondelete="SET NULL"),
    )

    assessment_type = sa.Column(sa.String(50))  # "filing_review", "news_analysis"
    verdict = sa.Column(sa.String(20))  # "positive", "negative", "neutral"
    confidence = sa.Column(sa.Float)

    thesis_effect = sa.Column(sa.String(20))  # "strengthen", "weaken", "no_change"
    materiality_score = sa.Column(sa.Float)
    time_horizon = sa.Column(sa.String(30))

    claims = JSONB()
    risks = JSONB()
    assumptions = JSONB()
    data_gaps = JSONB()
    invalidation_triggers = sa.Column(JSONB)

    created_at = sa.Column(sa.DateTime(timezone=True), default=lambda: datetime.now(UTC))

    def __repr__(self) -> str:
        return (
            f"AgentAssessment(assessment_type={self.assessment_type!r}, "
            f"verdict={self.verdict!r}, confidence={self.confidence})"
        )


class EvidenceItem(Base):
    __tablename__ = "evidence_items"

    id = sa.Column(UUID(as_uuid=True), primary_key=True, default=sa.func.gen_random_uuid())
    assessment_id = sa.Column(
        UUID(as_uuid=True), sa.ForeignKey("agent_assessments.id", ondelete="CASCADE"),
        nullable=False,
    )

    claim_text = sa.Column(sa.Text)
    status = sa.Column(sa.String(20))  # "verified", "unverified"

    source_document_id = sa.Column(
        UUID(as_uuid=True), sa.ForeignKey("raw_documents.id", ondelete="SET NULL"),
    )
    source_location = sa.Column(sa.Text)  # "DFP, nota 24, pagina 71"
    metric_ids = JSONB()

    created_at = sa.Column(sa.DateTime(timezone=True), default=lambda: datetime.now(UTC))

    def __repr__(self) -> str:
        return f"EvidenceItem(status={self.status!r}, source_location={self.source_location!r})"
