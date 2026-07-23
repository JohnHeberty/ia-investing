from datetime import datetime
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ._utils import utcnow
from .base import Base


class CommitteeSession(Base):
    __tablename__ = "committee_sessions"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    thesis_ids: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=list)
    members: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=list)
    scheduled_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    convened_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    state: Mapped[str] = mapped_column(sa.String(20), nullable=False, default="scheduled")
    agenda: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    total_members: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=0)
    present_members: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=0)
    votes_in_favor: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=0)
    votes_against: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=0)
    members_notified: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, default=False)
    decision: Mapped[str | None] = mapped_column(sa.Text)
    rationale: Mapped[str | None] = mapped_column(sa.Text)
    published_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    archived_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
    )

    __table_args__ = (
        sa.CheckConstraint(
            "state IN ('scheduled','in_session','voting','deliberating','decided','published','archived')",
            name="ck_committee_session_state",
        ),
        sa.CheckConstraint("total_members >= 0", name="ck_committee_session_total_members"),
        sa.CheckConstraint("present_members >= 0", name="ck_committee_session_present_members"),
        sa.CheckConstraint("votes_in_favor >= 0", name="ck_committee_session_votes_in_favor"),
        sa.CheckConstraint("votes_against >= 0", name="ck_committee_session_votes_against"),
    )


class CommitteeVote(Base):
    __tablename__ = "committee_votes"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    session_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("committee_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    member_id: Mapped[str] = mapped_column(sa.String(100), nullable=False)
    proposal_id: Mapped[str] = mapped_column(sa.String(100), nullable=False)
    vote: Mapped[str] = mapped_column(sa.String(20), nullable=False)
    justification: Mapped[str | None] = mapped_column(sa.Text)
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False, default=utcnow)

    __table_args__ = (
        sa.CheckConstraint(
            "vote IN ('in_favor','against','abstain')",
            name="ck_committee_vote_value",
        ),
        sa.UniqueConstraint(
            "session_id",
            "member_id",
            "proposal_id",
            name="uq_committee_vote_session_member_proposal",
        ),
    )


class CommitteeDecision(Base):
    __tablename__ = "committee_decisions"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    session_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("committee_sessions.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    decision: Mapped[str] = mapped_column(sa.Text, nullable=False)
    rationale: Mapped[str | None] = mapped_column(sa.Text)
    votes_summary: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    published_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False, default=utcnow)
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False, default=utcnow)
