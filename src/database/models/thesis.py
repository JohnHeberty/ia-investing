from datetime import datetime
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ._utils import utcnow
from .base import Base


class InvestmentThesis(Base):
    __tablename__ = "investment_theses"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    issuer_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("issuers.id", ondelete="CASCADE"),
        nullable=False,
    )

    status: Mapped[str | None] = mapped_column(
        sa.String(20), default="observation"
    )  # "observation", "researching", "active"
    summary_pt: Mapped[str | None] = mapped_column(sa.Text)
    key_drivers: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    risks: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    invalidation_criteria: Mapped[dict[str, object] | None] = mapped_column(JSONB)

    review_deadline: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    created_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), default=utcnow)

    def __repr__(self) -> str:
        return f"InvestmentThesis(status={self.status!r}, summary_pt={self.summary_pt!r})"


class ThesisVersion(Base):
    __tablename__ = "thesis_versions"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    thesis_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("investment_theses.id", ondelete="CASCADE"),
        nullable=False,
    )

    version_number: Mapped[int | None] = mapped_column(sa.Integer)
    change_summary: Mapped[str | None] = mapped_column(sa.Text)

    summary_pt: Mapped[str | None] = mapped_column(sa.Text)
    key_drivers: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    risks: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    invalidation_criteria: Mapped[dict[str, object] | None] = mapped_column(JSONB)

    agent_run_id: Mapped[UUID | None] = mapped_column()
    created_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), default=utcnow)

    def __repr__(self) -> str:
        return f"ThesisVersion(version_number={self.version_number}, change_summary={self.change_summary!r})"


class Recommendation(Base):
    __tablename__ = "recommendations"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    thesis_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("investment_theses.id", ondelete="CASCADE"),
        nullable=False,
    )
    issuer_id: Mapped[UUID | None] = mapped_column(
        sa.ForeignKey("issuers.id", ondelete="SET NULL"),
    )

    action: Mapped[str | None] = mapped_column(sa.String(20))  # "buy", "sell", "hold"
    confidence: Mapped[float | None] = mapped_column(sa.Float)
    reasoning_pt: Mapped[str | None] = mapped_column(sa.Text)

    supporting_assessments: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    opposing_arguments: Mapped[dict[str, object] | None] = mapped_column(JSONB)

    review_deadline: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    invalidation_triggers: Mapped[dict[str, object] | None] = mapped_column(JSONB)

    created_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), default=utcnow)

    def __repr__(self) -> str:
        return f"Recommendation(action={self.action!r}, confidence={self.confidence})"
