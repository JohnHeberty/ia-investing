"""Unit tests for committee routes."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.api.dependencies import get_committee_service
from apps.api.routes.committee import (
    CastVoteRequest,
    CommitteeMemberInput,
    CommitteeSessionCreatedResponse,
    CreateSessionRequest,
    ProposalInput,
    PublishDecisionRequest,
    router,
)
from apps.api.security import AuthContext, get_auth_context


def _mock_auth() -> AuthContext:
    return AuthContext(
        subject="user@test.com",
        roles=frozenset({"admin"}),
        permissions=frozenset(
            {"committee:create", "committee:read", "committee:chair", "committee:vote", "committee:publish"}
        ),
        authentication_method="test",
        organization_id=uuid4(),
    )


def _mock_service() -> MagicMock:
    service = MagicMock()
    service._session = AsyncMock()
    service.create_session = AsyncMock()
    service.list_sessions = AsyncMock(return_value=([], 0))
    service.get_pending_sessions = AsyncMock(return_value=[])
    service.get_session = AsyncMock()
    service.convene_session = AsyncMock()
    service.start_voting = AsyncMock()
    service.cast_vote = AsyncMock()
    service.finalize_voting = AsyncMock()
    service.publish_decision = AsyncMock()
    return service


@pytest.fixture()
def app_instance():
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_auth_context] = _mock_auth
    app.dependency_overrides[get_committee_service] = _mock_service
    yield app
    app.dependency_overrides.clear()


@pytest.fixture()
def client(app_instance):
    return TestClient(app_instance, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Schema tests
# ---------------------------------------------------------------------------
class TestSchemas:
    def test_create_session_request_validation(self) -> None:
        req = CreateSessionRequest(
            thesis_ids=["t1"],
            members=[CommitteeMemberInput(member_id="m1", subject="s1", role="chair")],
            scheduled_at=datetime.now(UTC),
        )
        assert len(req.members) == 1

    def test_create_session_request_duplicate_members_rejected(self) -> None:
        with pytest.raises(ValueError, match="unique"):
            CreateSessionRequest(
                thesis_ids=["t1"],
                members=[
                    CommitteeMemberInput(member_id="m1", subject="s1", role="chair"),
                    CommitteeMemberInput(member_id="m1", subject="s1", role="chair"),
                ],
                scheduled_at=datetime.now(UTC),
            )

    def test_proposal_input(self) -> None:
        p = ProposalInput(proposal_id="p1", title="Test", action="add")
        assert p.action == "add"

    def test_cast_vote_request(self) -> None:
        v = CastVoteRequest(proposal_id="p1", vote="in_favor")
        assert v.vote == "in_favor"

    def test_publish_decision_requires_rationale(self) -> None:
        with pytest.raises(ValueError, match="rationale"):
            PublishDecisionRequest(decision="reject")

    def test_publish_decision_approve_without_rationale(self) -> None:
        req = PublishDecisionRequest(decision="approve")
        assert req.decision == "approve"

    def test_committee_session_created_response(self) -> None:
        resp = CommitteeSessionCreatedResponse(id="s1", state="created", scheduled_at="2026-01-01T00:00:00")
        assert resp.state == "created"


# ---------------------------------------------------------------------------
# Create session endpoint
# ---------------------------------------------------------------------------
class TestCreateSession:
    @patch("apps.api.routes.committee.AuditMixin._audit", new_callable=AsyncMock)
    def test_create_session_success(self, mock_audit: MagicMock, client: TestClient) -> None:
        mock_session_obj = MagicMock()
        mock_session_obj.id = uuid4()
        mock_session_obj.state = "created"
        mock_session_obj.scheduled_at = datetime.now(UTC)

        service = _mock_service()
        service.create_session = AsyncMock(return_value=mock_session_obj)
        client.app.dependency_overrides[get_committee_service] = lambda: service

        resp = client.post(
            "/api/v1/committee/sessions",
            json={
                "thesis_ids": ["t1"],
                "members": [{"member_id": "m1", "subject": "s1", "role": "chair"}],
                "scheduled_at": datetime.now(UTC).isoformat(),
            },
        )
        assert resp.status_code == 201


# ---------------------------------------------------------------------------
# List sessions endpoint
# ---------------------------------------------------------------------------
class TestListSessions:
    def test_list_sessions_empty(self, client: TestClient) -> None:
        resp = client.get("/api/v1/committee/sessions")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0

    def test_list_sessions_with_state_filter(self, client: TestClient) -> None:
        resp = client.get("/api/v1/committee/sessions", params={"state": "voting"})
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Pending sessions
# ---------------------------------------------------------------------------
class TestPendingSessions:
    def test_pending_sessions(self, client: TestClient) -> None:
        resp = client.get("/api/v1/committee/sessions/pending")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Get session detail
# ---------------------------------------------------------------------------
class TestGetSession:
    def test_get_session_success(self, client: TestClient) -> None:
        service = _mock_service()
        service.get_session = AsyncMock(return_value={"id": "s1", "state": "created"})
        client.app.dependency_overrides[get_committee_service] = lambda: service

        resp = client.get(f"/api/v1/committee/sessions/{uuid4()}")
        assert resp.status_code == 200

    def test_get_session_not_found(self, client: TestClient) -> None:
        service = _mock_service()
        service.get_session = AsyncMock(side_effect=LookupError("not found"))
        client.app.dependency_overrides[get_committee_service] = lambda: service

        resp = client.get(f"/api/v1/committee/sessions/{uuid4()}")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Convene session
# ---------------------------------------------------------------------------
class TestConveneSession:
    @patch("apps.api.routes.committee.AuditMixin._audit", new_callable=AsyncMock)
    def test_convene_success(self, mock_audit: MagicMock, client: TestClient) -> None:
        service = _mock_service()
        mock_session_obj = MagicMock()
        mock_session_obj.id = uuid4()
        mock_session_obj.state = "convened"
        mock_session_obj.present_members = 2
        service.convene_session = AsyncMock(return_value=mock_session_obj)
        client.app.dependency_overrides[get_committee_service] = lambda: service

        resp = client.post(
            f"/api/v1/committee/sessions/{uuid4()}/convene",
            json={"present_member_ids": ["m1", "m2"]},
        )
        assert resp.status_code == 200

    def test_convene_not_found(self, client: TestClient) -> None:
        service = _mock_service()
        service.convene_session = AsyncMock(side_effect=LookupError("not found"))
        client.app.dependency_overrides[get_committee_service] = lambda: service

        resp = client.post(
            f"/api/v1/committee/sessions/{uuid4()}/convene",
            json={"present_member_ids": ["m1"]},
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Start voting
# ---------------------------------------------------------------------------
class TestStartVoting:
    @patch("apps.api.routes.committee.AuditMixin._audit", new_callable=AsyncMock)
    def test_start_voting_success(self, mock_audit: MagicMock, client: TestClient) -> None:
        service = _mock_service()
        mock_session_obj = MagicMock()
        mock_session_obj.id = uuid4()
        mock_session_obj.state = "voting"
        mock_session_obj.agenda = {"proposals": [{"id": "p1"}]}
        service.start_voting = AsyncMock(return_value=mock_session_obj)
        client.app.dependency_overrides[get_committee_service] = lambda: service

        resp = client.post(
            f"/api/v1/committee/sessions/{uuid4()}/voting",
            json={"proposals": [{"proposal_id": "p1", "title": "Test", "action": "add"}]},
        )
        assert resp.status_code == 200

    def test_start_voting_invalid_transition(self, client: TestClient) -> None:
        from ia_investing.application.committee_service import InvalidTransitionError

        service = _mock_service()
        service.start_voting = AsyncMock(side_effect=InvalidTransitionError("bad transition"))
        client.app.dependency_overrides[get_committee_service] = lambda: service

        resp = client.post(
            f"/api/v1/committee/sessions/{uuid4()}/voting",
            json={"proposals": [{"proposal_id": "p1", "title": "Test", "action": "add"}]},
        )
        assert resp.status_code == 409


# ---------------------------------------------------------------------------
# Cast vote
# ---------------------------------------------------------------------------
class TestCastVote:
    @patch("apps.api.routes.committee.AuditMixin._audit", new_callable=AsyncMock)
    def test_cast_vote_success(self, mock_audit: MagicMock, client: TestClient) -> None:
        service = _mock_service()
        mock_vote = MagicMock()
        mock_vote.id = uuid4()
        mock_vote.vote = "in_favor"
        mock_vote.proposal_id = "p1"
        service.cast_vote = AsyncMock(return_value=mock_vote)
        client.app.dependency_overrides[get_committee_service] = lambda: service

        resp = client.post(
            f"/api/v1/committee/sessions/{uuid4()}/vote",
            json={"proposal_id": "p1", "vote": "in_favor"},
        )
        assert resp.status_code == 200

    def test_cast_vote_conflict_of_interest(self, client: TestClient) -> None:
        from ia_investing.application.committee_service import ConflictOfInterestError

        service = _mock_service()
        service.cast_vote = AsyncMock(side_effect=ConflictOfInterestError("conflict"))
        client.app.dependency_overrides[get_committee_service] = lambda: service

        resp = client.post(
            f"/api/v1/committee/sessions/{uuid4()}/vote",
            json={"proposal_id": "p1", "vote": "in_favor"},
        )
        assert resp.status_code in (403, 409)


# ---------------------------------------------------------------------------
# Finalize voting
# ---------------------------------------------------------------------------
class TestFinalizeVoting:
    @patch("apps.api.routes.committee.AuditMixin._audit", new_callable=AsyncMock)
    def test_finalize_success(self, mock_audit: MagicMock, client: TestClient) -> None:
        service = _mock_service()
        mock_session_obj = MagicMock()
        mock_session_obj.id = uuid4()
        mock_session_obj.state = "finalized"
        mock_session_obj.votes_in_favor = 3
        mock_session_obj.votes_against = 1
        service.finalize_voting = AsyncMock(return_value=mock_session_obj)
        client.app.dependency_overrides[get_committee_service] = lambda: service

        resp = client.post(f"/api/v1/committee/sessions/{uuid4()}/finalize")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Publish decision
# ---------------------------------------------------------------------------
class TestPublishDecision:
    @patch("apps.api.routes.committee.AuditMixin._audit", new_callable=AsyncMock)
    def test_publish_approve(self, mock_audit: MagicMock, client: TestClient) -> None:
        service = _mock_service()
        mock_session_obj = MagicMock()
        mock_session_obj.id = uuid4()
        mock_session_obj.state = "published"
        mock_session_obj.decision = "approve"
        mock_session_obj.published_at = datetime.now(UTC)
        service.publish_decision = AsyncMock(return_value=mock_session_obj)
        client.app.dependency_overrides[get_committee_service] = lambda: service

        resp = client.post(
            f"/api/v1/committee/sessions/{uuid4()}/publish",
            json={"decision": "approve"},
        )
        assert resp.status_code == 200

    @patch("apps.api.routes.committee.AuditMixin._audit", new_callable=AsyncMock)
    def test_publish_reject_with_rationale(self, mock_audit: MagicMock, client: TestClient) -> None:
        service = _mock_service()
        mock_session_obj = MagicMock()
        mock_session_obj.id = uuid4()
        mock_session_obj.state = "published"
        mock_session_obj.decision = "reject"
        mock_session_obj.published_at = datetime.now(UTC)
        service.publish_decision = AsyncMock(return_value=mock_session_obj)
        client.app.dependency_overrides[get_committee_service] = lambda: service

        resp = client.post(
            f"/api/v1/committee/sessions/{uuid4()}/publish",
            json={"decision": "reject", "rationale": "Not convinced"},
        )
        assert resp.status_code == 200
