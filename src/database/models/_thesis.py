import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from ._utils import utcnow
from .base import Base


class InvestmentThesis(Base):
    __tablename__ = "investment_theses"

    id = sa.Column(UUID(as_uuid=True), primary_key=True, default=sa.func.gen_random_uuid())
    issuer_id = sa.Column(
        UUID(as_uuid=True),
        sa.ForeignKey("issuers.id", ondelete="CASCADE"),
        nullable=False,
    )

    status = sa.Column(sa.String(20), default="observation")  # "observation", "researching", "active"
    summary_pt = sa.Column(sa.Text)
    key_drivers = sa.Column(JSONB)
    risks = sa.Column(JSONB)
    invalidation_criteria = sa.Column(JSONB)

    review_deadline = sa.Column(sa.DateTime(timezone=True))
    created_at = sa.Column(sa.DateTime(timezone=True), default=utcnow)

    def __repr__(self) -> str:
        return f"InvestmentThesis(status={self.status!r}, summary_pt={self.summary_pt!r})"


class ThesisVersion(Base):
    __tablename__ = "thesis_versions"

    id = sa.Column(UUID(as_uuid=True), primary_key=True, default=sa.func.gen_random_uuid())
    thesis_id = sa.Column(
        UUID(as_uuid=True),
        sa.ForeignKey("investment_theses.id", ondelete="CASCADE"),
        nullable=False,
    )

    version_number = sa.Column(sa.Integer)
    change_summary = sa.Column(sa.Text)

    summary_pt = sa.Column(sa.Text)
    key_drivers = sa.Column(JSONB)
    risks = sa.Column(JSONB)
    invalidation_criteria = sa.Column(JSONB)

    agent_run_id = sa.Column(UUID(as_uuid=True), nullable=True)
    created_at = sa.Column(sa.DateTime(timezone=True), default=utcnow)

    def __repr__(self) -> str:
        return f"ThesisVersion(version_number={self.version_number}, change_summary={self.change_summary!r})"


class Recommendation(Base):
    __tablename__ = "recommendations"

    id = sa.Column(UUID(as_uuid=True), primary_key=True, default=sa.func.gen_random_uuid())
    thesis_id = sa.Column(
        UUID(as_uuid=True),
        sa.ForeignKey("investment_theses.id", ondelete="CASCADE"),
        nullable=False,
    )
    issuer_id = sa.Column(
        UUID(as_uuid=True),
        sa.ForeignKey("issuers.id", ondelete="SET NULL"),
    )

    action = sa.Column(sa.String(20))  # "buy", "sell", "hold"
    confidence = sa.Column(sa.Float)
    reasoning_pt = sa.Column(sa.Text)

    supporting_assessments = sa.Column(JSONB)
    opposing_arguments = sa.Column(JSONB)

    review_deadline = sa.Column(sa.DateTime(timezone=True))
    invalidation_triggers = sa.Column(JSONB)

    created_at = sa.Column(sa.DateTime(timezone=True), default=utcnow)

    def __repr__(self) -> str:
        return f"Recommendation(action={self.action!r}, confidence={self.confidence})"
