from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.committee import CommitteeDecision, CommitteeSession, CommitteeVote
from ia_investing.application.audit_service import AuditService
from ia_investing.domain.base_machine import InvalidTransitionError
from ia_investing.domain.committee_machine import CommitteeMachineModel, create_committee_machine


class QuorumNotMetError(ValueError):
    pass


class MajorityNotReachedError(ValueError):
    pass


class DuplicateVoteError(ValueError):
    pass


class CommitteeService:
    def __init__(self, session: AsyncSession, audit: AuditService) -> None:
        self._session = session
        self._audit = audit

    async def create_session(
        self,
        thesis_ids: list[str],
        members: list[dict],
        scheduled_at: datetime,
        agenda: dict | None = None,
        actor_id: UUID | None = None,
    ) -> CommitteeSession:
        session = CommitteeSession(
            thesis_ids=thesis_ids,
            members=members,
            scheduled_at=scheduled_at,
            agenda=agenda or {},
            state="scheduled",
            total_members=len(members),
        )
        self._session.add(session)
        await self._session.flush()
        await self._audit.log(
            actor_id=actor_id,
            action="create",
            resource_type="committee_session",
            resource_id=session.id,
            changes={"thesis_ids": thesis_ids, "total_members": len(members)},
        )
        return session

    async def _transition(
        self,
        session_id: UUID,
        trigger: str,
        reason: str | None = None,
        actor_id: UUID | None = None,
        **kwargs,
    ) -> CommitteeSession:
        db_session = await self._session.get(CommitteeSession, session_id)
        if db_session is None:
            raise LookupError(f"Committee session {session_id} not found")

        model = CommitteeMachineModel(
            id=db_session.id,
            state=db_session.state,
            total_members=db_session.total_members,
            present_members=db_session.present_members,
            votes_in_favor=db_session.votes_in_favor,
            votes_against=db_session.votes_against,
            members_notified=db_session.members_notified,
        )
        machine = create_committee_machine(model)

        try:
            new_state = machine.apply(trigger, reason=reason, **kwargs)
        except InvalidTransitionError as exc:
            raise InvalidTransitionError(str(exc)) from exc

        db_session.state = new_state
        db_session.present_members = model.present_members
        db_session.votes_in_favor = model.votes_in_favor
        db_session.votes_against = model.votes_against
        db_session.members_notified = model.members_notified

        await self._audit.log(
            actor_id=actor_id,
            action=f"committee:{trigger}",
            resource_type="committee_session",
            resource_id=session_id,
            changes={
                "from_state": model.state_history[-2].from_state if len(model.state_history) >= 2 else None,
                "to_state": new_state,
            },
        )
        return db_session

    async def convene_session(
        self,
        session_id: UUID,
        present_members: int | None = None,
        actor_id: UUID | None = None,
    ) -> CommitteeSession:
        db_session = await self._session.get(CommitteeSession, session_id)
        if db_session is None:
            raise LookupError(f"Committee session {session_id} not found")

        if present_members is not None:
            db_session.present_members = present_members

        result = await self._transition(session_id, "convene", actor_id=actor_id)
        result.convened_at = datetime.now(UTC)
        return result

    async def start_voting(
        self,
        session_id: UUID,
        proposals: list[dict],
        actor_id: UUID | None = None,
    ) -> CommitteeSession:
        db_session = await self._session.get(CommitteeSession, session_id)
        if db_session is None:
            raise LookupError(f"Committee session {session_id} not found")

        if db_session.present_members < db_session.total_members // 2 + 1:
            raise QuorumNotMetError(
                f"Quorum not met: {db_session.present_members} present, "
                f"need at least {db_session.total_members // 2 + 1}"
            )

        db_session.agenda = {**db_session.agenda, "proposals": proposals}
        result = await self._transition(session_id, "start_voting", actor_id=actor_id)
        return result

    async def cast_vote(
        self,
        session_id: UUID,
        member_id: str,
        proposal_id: str,
        vote: str,
        justification: str | None = None,
        actor_id: UUID | None = None,
    ) -> CommitteeVote:
        db_session = await self._session.get(CommitteeSession, session_id)
        if db_session is None:
            raise LookupError(f"Committee session {session_id} not found")

        if db_session.state not in ("voting", "in_session"):
            raise InvalidTransitionError("Voting is not open for this session")

        existing = await self._session.execute(
            sa.select(CommitteeVote).where(
                CommitteeVote.session_id == session_id,
                CommitteeVote.member_id == member_id,
                CommitteeVote.proposal_id == proposal_id,
            )
        )
        if existing.scalar_one_or_none() is not None:
            raise DuplicateVoteError(f"Member {member_id} already voted on proposal {proposal_id}")

        vote_record = CommitteeVote(
            session_id=session_id,
            member_id=member_id,
            proposal_id=proposal_id,
            vote=vote,
            justification=justification,
        )
        self._session.add(vote_record)

        if vote == "in_favor":
            db_session.votes_in_favor += 1
        elif vote == "against":
            db_session.votes_against += 1

        await self._audit.log(
            actor_id=actor_id,
            action="committee:cast_vote",
            resource_type="committee_vote",
            resource_id=vote_record.id,
            changes={"session_id": str(session_id), "member_id": member_id, "proposal_id": proposal_id, "vote": vote},
        )
        return vote_record

    async def finalize_voting(
        self,
        session_id: UUID,
        actor_id: UUID | None = None,
    ) -> CommitteeSession:
        db_session = await self._session.get(CommitteeSession, session_id)
        if db_session is None:
            raise LookupError(f"Committee session {session_id} not found")

        if db_session.state != "voting":
            raise InvalidTransitionError("Session is not in voting state")

        total_votes = db_session.votes_in_favor + db_session.votes_against
        if total_votes == 0:
            raise MajorityNotReachedError("No votes cast")
        if db_session.votes_in_favor <= total_votes / 2:
            raise MajorityNotReachedError(
                f"Majority not reached: {db_session.votes_in_favor} in favor, {db_session.votes_against} against"
            )

        result = await self._transition(session_id, "deliberate", reason="Voting finalized", actor_id=actor_id)
        result = await self._transition(session_id, "make_decision", actor_id=actor_id)
        return result

    async def publish_decision(
        self,
        session_id: UUID,
        decision: str,
        rationale: str | None = None,
        actor_id: UUID | None = None,
    ) -> CommitteeSession:
        db_session = await self._session.get(CommitteeSession, session_id)
        if db_session is None:
            raise LookupError(f"Committee session {session_id} not found")

        # collect vote summary
        vote_stmt = sa.select(CommitteeVote).where(CommitteeVote.session_id == session_id)
        vote_result = await self._session.execute(vote_stmt)
        votes = vote_result.scalars().all()

        votes_summary = {
            "in_favor": sum(1 for v in votes if v.vote == "in_favor"),
            "against": sum(1 for v in votes if v.vote == "against"),
            "abstain": sum(1 for v in votes if v.vote == "abstain"),
            "total": len(votes),
        }

        result = await self._transition(session_id, "publish", reason="Decision published", actor_id=actor_id)

        db_session.decision = decision
        db_session.rationale = rationale
        db_session.published_at = datetime.now(UTC)

        decision_record = CommitteeDecision(
            session_id=session_id,
            decision=decision,
            rationale=rationale,
            votes_summary=votes_summary,
        )
        self._session.add(decision_record)

        await self._audit.log(
            actor_id=actor_id,
            action="committee:publish",
            resource_type="committee_decision",
            resource_id=decision_record.id,
            changes={"session_id": str(session_id), "decision": decision, "votes_summary": votes_summary},
        )
        return result

    async def get_session(self, session_id: UUID) -> dict:
        db_session = await self._session.get(CommitteeSession, session_id)
        if db_session is None:
            raise LookupError(f"Committee session {session_id} not found")

        model = CommitteeMachineModel(
            state=db_session.state,
            total_members=db_session.total_members,
            present_members=db_session.present_members,
            votes_in_favor=db_session.votes_in_favor,
            votes_against=db_session.votes_against,
        )
        machine = create_committee_machine(model)

        vote_stmt = sa.select(CommitteeVote).where(CommitteeVote.session_id == session_id)
        vote_result = await self._session.execute(vote_stmt)
        votes = vote_result.scalars().all()

        decision_stmt = sa.select(CommitteeDecision).where(CommitteeDecision.session_id == session_id)
        decision_result = await self._session.execute(decision_stmt)
        decision = decision_result.scalar_one_or_none()

        return {
            "id": str(db_session.id),
            "thesis_ids": db_session.thesis_ids,
            "members": db_session.members,
            "scheduled_at": db_session.scheduled_at.isoformat() if db_session.scheduled_at else None,
            "convened_at": db_session.convened_at.isoformat() if db_session.convened_at else None,
            "state": db_session.state,
            "agenda": db_session.agenda,
            "total_members": db_session.total_members,
            "present_members": db_session.present_members,
            "votes_in_favor": db_session.votes_in_favor,
            "votes_against": db_session.votes_against,
            "members_notified": db_session.members_notified,
            "decision": db_session.decision,
            "rationale": db_session.rationale,
            "published_at": db_session.published_at.isoformat() if db_session.published_at else None,
            "created_at": db_session.created_at.isoformat() if db_session.created_at else None,
            "updated_at": db_session.updated_at.isoformat() if db_session.updated_at else None,
            "allowed_transitions": machine.get_allowed_transitions(),
            "state_history": machine.get_state_history(),
            "votes": [
                {
                    "id": str(v.id),
                    "member_id": v.member_id,
                    "proposal_id": v.proposal_id,
                    "vote": v.vote,
                    "justification": v.justification,
                    "created_at": v.created_at.isoformat() if v.created_at else None,
                }
                for v in votes
            ],
            "decision_record": {
                "decision": decision.decision,
                "rationale": decision.rationale,
                "votes_summary": decision.votes_summary,
                "published_at": decision.published_at.isoformat() if decision.published_at else None,
            }
            if decision
            else None,
        }

    async def get_pending_sessions(self) -> list[dict]:
        stmt = (
            sa.select(CommitteeSession)
            .where(CommitteeSession.state.in_(["scheduled", "in_session", "voting", "deliberating", "decided"]))
            .order_by(CommitteeSession.scheduled_at.asc())
        )
        result = await self._session.execute(stmt)
        sessions = result.scalars().all()
        return [
            {
                "id": str(s.id),
                "state": s.state,
                "scheduled_at": s.scheduled_at.isoformat() if s.scheduled_at else None,
                "total_members": s.total_members,
                "present_members": s.present_members,
                "created_at": s.created_at.isoformat() if s.created_at else None,
            }
            for s in sessions
        ]

    async def list_sessions(
        self,
        state: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[CommitteeSession], int]:
        stmt = sa.select(CommitteeSession)
        count_stmt = sa.select(sa.func.count()).select_from(CommitteeSession)

        if state:
            stmt = stmt.where(CommitteeSession.state == state)
            count_stmt = count_stmt.where(CommitteeSession.state == state)

        total = await self._session.scalar(count_stmt) or 0
        stmt = stmt.order_by(CommitteeSession.created_at.desc()).offset(offset).limit(limit)
        result = await self._session.execute(stmt)
        rows = list(result.scalars().all())
        return rows, total
