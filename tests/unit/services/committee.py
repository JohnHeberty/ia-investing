"""Unit tests for CommitteeService — create, convene, vote, finalize, publish."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from ia_investing.application.committee_service import (
    CommitteeService,
    ConflictOfInterestError,
    DuplicateVoteError,
    MajorityNotReachedError,
    QuorumNotMetError,
)
from ia_investing.domain.base_machine import InvalidTransitionError

_SENTINEL = object()


@pytest.fixture()
def mock_session() -> AsyncMock:
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.execute = AsyncMock()
    session.get = AsyncMock()
    session.scalar = AsyncMock()
    return session


@pytest.fixture()
def mock_audit() -> AsyncMock:
    audit = AsyncMock()
    audit.log = AsyncMock()
    return audit


@pytest.fixture()
def service(mock_session: AsyncMock, mock_audit: AsyncMock) -> CommitteeService:
    return CommitteeService(mock_session, mock_audit)


def _make_session_model(**overrides: object) -> MagicMock:
    s = MagicMock()
    s.id = overrides.get("id", uuid.uuid4())
    s.organization_id = overrides.get("organization_id", uuid.uuid4())
    s.thesis_ids = overrides.get("thesis_ids", ["t1"])
    s.members = overrides.get("members", [{"member_id": "m1", "subject": "s1"}, {"member_id": "m2", "subject": "s2"}])
    s.scheduled_at = overrides.get("scheduled_at", datetime(2026, 1, 15, 10, tzinfo=UTC))
    s.convened_at = overrides.get("convened_at", None)
    s.state = overrides.get("state", "scheduled")
    s.agenda = overrides.get("agenda", {})
    s.total_members = overrides.get("total_members", 2)
    s.present_members = overrides.get("present_members", 0)
    s.votes_in_favor = overrides.get("votes_in_favor", 0)
    s.votes_against = overrides.get("votes_against", 0)
    s.members_notified = overrides.get("members_notified", False)
    s.decision = overrides.get("decision", None)
    s.rationale = overrides.get("rationale", None)
    s.published_at = overrides.get("published_at", None)
    s.created_at = overrides.get("created_at", datetime.now(UTC))
    s.updated_at = overrides.get("updated_at", datetime.now(UTC))
    return s


def _make_vote(**overrides: object) -> MagicMock:
    v = MagicMock()
    v.id = overrides.get("id", uuid.uuid4())
    v.session_id = overrides.get("session_id", uuid.uuid4())
    v.member_id = overrides.get("member_id", "m1")
    v.proposal_id = overrides.get("proposal_id", "p1")
    v.vote = overrides.get("vote", "in_favor")
    v.justification = overrides.get("justification", None)
    v.created_at = overrides.get("created_at", datetime.now(UTC))
    return v


def _make_execute_result(scalar_one=_SENTINEL, scalars_all=_SENTINEL):
    """Build a mock for session.execute() that works for both scalar_one_or_none and scalars().all()."""
    result = MagicMock()
    result.scalar_one_or_none.return_value = None if scalar_one is _SENTINEL else scalar_one
    if scalars_all is not _SENTINEL:
        result.scalars.return_value.all.return_value = scalars_all
    return result


@pytest.mark.asyncio
@pytest.mark.unit
class TestCreateSession:
    async def test_create_session(self, service: CommitteeService, mock_session: AsyncMock) -> None:
        result = await service.create_session(
            thesis_ids=["t1", "t2"],
            members=[{"member_id": "m1", "subject": "s1"}],
            scheduled_at=datetime(2026, 6, 1, tzinfo=UTC),
            actor_id=uuid.uuid4(),
        )
        assert result.state == "scheduled"
        assert result.total_members == 1
        mock_session.add.assert_called_once()
        mock_session.flush.assert_awaited()

    async def test_create_session_with_agenda(
        self, service: CommitteeService, mock_session: AsyncMock
    ) -> None:
        agenda = {"topic": "rebalance Q2"}
        result = await service.create_session(
            thesis_ids=["t1"],
            members=[],
            scheduled_at=datetime(2026, 6, 1, tzinfo=UTC),
            agenda=agenda,
        )
        assert result.agenda == {"topic": "rebalance Q2"}


@pytest.mark.asyncio
@pytest.mark.unit
class TestConveneSession:
    async def test_convene_session_success(
        self, service: CommitteeService, mock_session: AsyncMock
    ) -> None:
        db_session = _make_session_model(state="scheduled")
        mock_session.get.return_value = db_session
        mock_session.execute.return_value = _make_execute_result(scalar_one=db_session)

        result = await service.convene_session(db_session.id)
        assert result.state == "in_session"
        assert result.convened_at is not None

    async def test_convene_not_found(self, service: CommitteeService, mock_session: AsyncMock) -> None:
        mock_session.get.return_value = None
        with pytest.raises(LookupError, match="not found"):
            await service.convene_session(uuid.uuid4())

    async def test_convene_with_present_members(
        self, service: CommitteeService, mock_session: AsyncMock
    ) -> None:
        members = [{"member_id": "m1", "subject": "s1"}, {"member_id": "m2", "subject": "s2"}]
        db_session = _make_session_model(state="scheduled", members=members)
        mock_session.get.return_value = db_session
        mock_session.execute.return_value = _make_execute_result(scalar_one=db_session)

        result = await service.convene_session(db_session.id, present_member_ids=["m1", "m2"])
        assert result.present_members == 2

    async def test_convene_unknown_member_raises(
        self, service: CommitteeService, mock_session: AsyncMock
    ) -> None:
        members = [{"member_id": "m1", "subject": "s1"}]
        db_session = _make_session_model(state="scheduled", members=members)
        mock_session.get.return_value = db_session

        with pytest.raises(ValueError, match="Unknown members"):
            await service.convene_session(db_session.id, present_member_ids=["m1", "m99"])


@pytest.mark.asyncio
@pytest.mark.unit
class TestStartVoting:
    async def test_start_voting_success(
        self, service: CommitteeService, mock_session: AsyncMock
    ) -> None:
        db_session = _make_session_model(state="in_session", total_members=2, present_members=2)
        mock_session.get.return_value = db_session
        mock_session.execute.return_value = _make_execute_result(scalar_one=db_session)

        result = await service.start_voting(
            db_session.id, proposals=[{"proposal_id": "p1", "title": "test"}]
        )
        assert result.state == "voting"

    async def test_start_voting_not_found(
        self, service: CommitteeService, mock_session: AsyncMock
    ) -> None:
        mock_session.get.return_value = None
        with pytest.raises(LookupError, match="not found"):
            await service.start_voting(uuid.uuid4(), proposals=[])


@pytest.mark.asyncio
@pytest.mark.unit
class TestCastVote:
    async def test_cast_vote_in_favor(
        self, service: CommitteeService, mock_session: AsyncMock
    ) -> None:
        db_session = _make_session_model(state="voting")
        mock_session.get.return_value = db_session
        mock_session.execute.return_value = _make_execute_result(scalar_one=None)

        vote = await service.cast_vote(
            db_session.id, member_id="m1", proposal_id="p1", vote="in_favor"
        )
        assert vote.vote == "in_favor"
        assert db_session.votes_in_favor == 1

    async def test_cast_vote_against(
        self, service: CommitteeService, mock_session: AsyncMock
    ) -> None:
        db_session = _make_session_model(state="voting")
        mock_session.get.return_value = db_session
        mock_session.execute.return_value = _make_execute_result(scalar_one=None)

        await service.cast_vote(
            db_session.id, member_id="m1", proposal_id="p1", vote="against"
        )
        assert db_session.votes_against == 1

    async def test_cast_vote_duplicate_raises(
        self, service: CommitteeService, mock_session: AsyncMock
    ) -> None:
        db_session = _make_session_model(state="voting")
        mock_session.get.return_value = db_session
        mock_session.execute.return_value = _make_execute_result(scalar_one=MagicMock())

        with pytest.raises(DuplicateVoteError, match="already voted"):
            await service.cast_vote(
                db_session.id, member_id="m1", proposal_id="p1", vote="in_favor"
            )

    async def test_cast_vote_not_voting_state_raises(
        self, service: CommitteeService, mock_session: AsyncMock
    ) -> None:
        db_session = _make_session_model(state="scheduled")
        mock_session.get.return_value = db_session

        with pytest.raises(InvalidTransitionError, match="Voting is not open"):
            await service.cast_vote(
                db_session.id, member_id="m1", proposal_id="p1", vote="in_favor"
            )

    async def test_cast_vote_unknown_member_raises(
        self, service: CommitteeService, mock_session: AsyncMock
    ) -> None:
        members = [{"member_id": "m1", "subject": "s1"}]
        db_session = _make_session_model(state="voting", members=members)
        mock_session.get.return_value = db_session

        with pytest.raises(LookupError, match="not registered"):
            await service.cast_vote(
                db_session.id, member_id="m_unknown", proposal_id="p1", vote="in_favor"
            )

    async def test_cast_vote_conflict_of_interest(
        self, service: CommitteeService, mock_session: AsyncMock
    ) -> None:
        members = [{"member_id": "m1", "subject": "real_subject"}]
        db_session = _make_session_model(state="voting", members=members)
        mock_session.get.return_value = db_session

        with pytest.raises(ConflictOfInterestError, match="cannot vote"):
            await service.cast_vote(
                db_session.id,
                member_id="m1",
                proposal_id="p1",
                vote="in_favor",
                actor_subject="different_subject",
            )

    async def test_session_not_found(self, service: CommitteeService, mock_session: AsyncMock) -> None:
        mock_session.get.return_value = None
        with pytest.raises(LookupError, match="not found"):
            await service.cast_vote(
                uuid.uuid4(), member_id="m1", proposal_id="p1", vote="in_favor"
            )


@pytest.mark.asyncio
@pytest.mark.unit
class TestFinalizeVoting:
    async def test_finalize_reaches_decided(
        self, service: CommitteeService, mock_session: AsyncMock
    ) -> None:
        db_session = _make_session_model(
            state="voting", votes_in_favor=3, votes_against=1, total_members=4, present_members=4
        )
        mock_session.get.return_value = db_session
        # _transition is called twice: "deliberate" then "make_decision"
        mock_session.execute.return_value = _make_execute_result(scalar_one=db_session)

        result = await service.finalize_voting(db_session.id)
        assert result.state == "decided"

    async def test_finalize_no_votes_raises(
        self, service: CommitteeService, mock_session: AsyncMock
    ) -> None:
        db_session = _make_session_model(state="voting", votes_in_favor=0, votes_against=0)
        mock_session.get.return_value = db_session

        with pytest.raises(MajorityNotReachedError, match="No votes"):
            await service.finalize_voting(db_session.id)

    async def test_finalize_majority_not_reached(
        self, service: CommitteeService, mock_session: AsyncMock
    ) -> None:
        db_session = _make_session_model(state="voting", votes_in_favor=2, votes_against=3)
        mock_session.get.return_value = db_session

        with pytest.raises(MajorityNotReachedError, match="Majority not reached"):
            await service.finalize_voting(db_session.id)

    async def test_finalize_wrong_state_raises(
        self, service: CommitteeService, mock_session: AsyncMock
    ) -> None:
        db_session = _make_session_model(state="scheduled", votes_in_favor=1, votes_against=0)
        mock_session.get.return_value = db_session

        with pytest.raises(InvalidTransitionError, match="not in voting"):
            await service.finalize_voting(db_session.id)

    async def test_finalize_session_not_found(
        self, service: CommitteeService, mock_session: AsyncMock
    ) -> None:
        mock_session.get.return_value = None
        with pytest.raises(LookupError, match="not found"):
            await service.finalize_voting(uuid.uuid4())


@pytest.mark.asyncio
@pytest.mark.unit
class TestPublishDecision:
    async def test_publish_decision(
        self, service: CommitteeService, mock_session: AsyncMock
    ) -> None:
        db_session = _make_session_model(state="decided")
        mock_session.get.return_value = db_session
        # Calls: 1) execute for votes, 2) execute for _transition
        mock_session.execute.side_effect = [
            _make_execute_result(scalars_all=[]),
            _make_execute_result(scalar_one=db_session),
        ]

        result = await service.publish_decision(
            db_session.id, decision="approve", rationale="Strong thesis"
        )
        assert result.state == "published"
        assert result.decision == "approve"
        assert result.rationale == "Strong thesis"

    async def test_publish_with_votes_summary(
        self, service: CommitteeService, mock_session: AsyncMock
    ) -> None:
        db_session = _make_session_model(state="decided")
        mock_session.get.return_value = db_session
        votes = [
            _make_vote(vote="in_favor"),
            _make_vote(vote="in_favor"),
            _make_vote(vote="against"),
        ]
        mock_session.execute.side_effect = [
            _make_execute_result(scalars_all=votes),
            _make_execute_result(scalar_one=db_session),
        ]

        result = await service.publish_decision(db_session.id, decision="approve")
        assert result.state == "published"

    async def test_publish_session_not_found(
        self, service: CommitteeService, mock_session: AsyncMock
    ) -> None:
        mock_session.get.return_value = None
        with pytest.raises(LookupError, match="not found"):
            await service.publish_decision(uuid.uuid4(), decision="approve")


@pytest.mark.asyncio
@pytest.mark.unit
class TestGetSession:
    async def test_get_session_success(
        self, service: CommitteeService, mock_session: AsyncMock
    ) -> None:
        db_session = _make_session_model(state="published", decision="approve")
        mock_session.execute.side_effect = [
            _make_execute_result(scalar_one=db_session),
            _make_execute_result(scalars_all=[_make_vote()]),
            _make_execute_result(scalar_one=MagicMock(
                decision="approve", rationale="ok", votes_summary={}, published_at=None
            )),
        ]

        result = await service.get_session(db_session.id)
        assert result["state"] == "published"
        assert result["decision"] == "approve"
        assert len(result["votes"]) == 1

    async def test_get_session_not_found(
        self, service: CommitteeService, mock_session: AsyncMock
    ) -> None:
        mock_session.execute.return_value = _make_execute_result(scalar_one=None)

        with pytest.raises(LookupError, match="not found"):
            await service.get_session(uuid.uuid4())


@pytest.mark.asyncio
@pytest.mark.unit
class TestListSessions:
    async def test_list_empty(self, service: CommitteeService, mock_session: AsyncMock) -> None:
        mock_session.scalar.return_value = 0
        mock_session.execute.return_value = _make_execute_result(scalars_all=[])

        sessions, total = await service.list_sessions()
        assert total == 0
        assert sessions == []

    async def test_list_with_state_filter(
        self, service: CommitteeService, mock_session: AsyncMock
    ) -> None:
        mock_session.scalar.return_value = 1
        mock_session.execute.return_value = _make_execute_result(
            scalars_all=[_make_session_model(state="voting")]
        )

        sessions, total = await service.list_sessions(state="voting")
        assert total == 1


@pytest.mark.asyncio
@pytest.mark.unit
class TestGetPendingSessions:
    async def test_get_pending_sessions(
        self, service: CommitteeService, mock_session: AsyncMock
    ) -> None:
        mock_session.execute.return_value = _make_execute_result(
            scalars_all=[_make_session_model(state="scheduled")]
        )

        result = await service.get_pending_sessions()
        assert len(result) == 1
        assert result[0]["state"] == "scheduled"
