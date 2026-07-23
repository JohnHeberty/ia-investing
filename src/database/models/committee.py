import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from ._utils import utcnow
from .base import Base


class CommitteeSession(Base):
    __tablename__ = "committee_sessions"

    id = sa.Column(UUID(as_uuid=True), primary_key=True, default=sa.func.gen_random_uuid())
    thesis_ids = sa.Column(JSONB, nullable=False, default=list)
    members = sa.Column(JSONB, nullable=False, default=list)
    scheduled_at = sa.Column(sa.DateTime(timezone=True), nullable=False)
    convened_at = sa.Column(sa.DateTime(timezone=True))
    state = sa.Column(sa.String(20), nullable=False, default="scheduled")
    agenda = sa.Column(JSONB, nullable=False, default=dict)
    total_members = sa.Column(sa.Integer, nullable=False, default=0)
    present_members = sa.Column(sa.Integer, nullable=False, default=0)
    votes_in_favor = sa.Column(sa.Integer, nullable=False, default=0)
    votes_against = sa.Column(sa.Integer, nullable=False, default=0)
    members_notified = sa.Column(sa.Boolean, nullable=False, default=False)
    decision = sa.Column(sa.Text)
    rationale = sa.Column(sa.Text)
    published_at = sa.Column(sa.DateTime(timezone=True))
    archived_at = sa.Column(sa.DateTime(timezone=True))
    created_at = sa.Column(sa.DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = sa.Column(
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

    id = sa.Column(UUID(as_uuid=True), primary_key=True, default=sa.func.gen_random_uuid())
    session_id = sa.Column(
        UUID(as_uuid=True),
        sa.ForeignKey("committee_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    member_id = sa.Column(sa.String(100), nullable=False)
    proposal_id = sa.Column(sa.String(100), nullable=False)
    vote = sa.Column(sa.String(20), nullable=False)
    justification = sa.Column(sa.Text)
    created_at = sa.Column(sa.DateTime(timezone=True), nullable=False, default=utcnow)

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

    id = sa.Column(UUID(as_uuid=True), primary_key=True, default=sa.func.gen_random_uuid())
    session_id = sa.Column(
        UUID(as_uuid=True),
        sa.ForeignKey("committee_sessions.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    decision = sa.Column(sa.Text, nullable=False)
    rationale = sa.Column(sa.Text)
    votes_summary = sa.Column(JSONB, nullable=False, default=dict)
    published_at = sa.Column(sa.DateTime(timezone=True), nullable=False, default=utcnow)
    created_at = sa.Column(sa.DateTime(timezone=True), nullable=False, default=utcnow)
