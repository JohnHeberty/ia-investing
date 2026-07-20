"""F3-PR03: ResearchReviewService authorization, double-submission, expiry, locking tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from ia_investing.application.reviews import ResearchReviewService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

ALL_PERMS = frozenset({
    "research_assessments:create",
    "research_reviews:request",
    "research_reviews:decide",
})


def _make_assessment(
    author_id: str = "analyst-1",
    expires_at: datetime | None = None,
    data_as_of: datetime | None = None,
) -> MagicMock:
    a = MagicMock()
    a.id = uuid4()
    a.author_id = author_id
    a.result_sha256 = "hash-abc"
    a.expires_at = expires_at or (datetime.now(UTC) + timedelta(days=30))
    a.data_as_of = data_as_of or datetime.now(UTC)
    return a


def _make_review_request(
    status: str = "pending",
    required_reviewer_role: str = "reviewer",
    assessment_id=None,
) -> MagicMock:
    r = MagicMock()
    r.id = uuid4()
    r.status = status
    r.required_reviewer_role = required_reviewer_role
    r.assessment_id = assessment_id or uuid4()
    r.due_at = None
    return r


def _make_session(**kwargs) -> AsyncMock:
    session = AsyncMock()
    session.get = AsyncMock(return_value=kwargs.get("entity"))
    session.flush = AsyncMock()
    return session


# ---------------------------------------------------------------------------
# create_assessment: permission required
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_assessment_requires_permission() -> None:
    session = _make_session()
    service = ResearchReviewService(session)

    with pytest.raises(PermissionError, match="research_assessments:create"):
        await service.create_assessment(
            research_case_id=uuid4(),
            assessment_type="filing_review",
            author_type="agent",
            author_id="analyst-1",
            schema_name="filing_review_v1",
            schema_version="1.0",
            result={"verdict": "positive"},
            data_as_of=datetime.now(UTC),
            expires_at=datetime.now(UTC) + timedelta(days=30),
            permissions=frozenset(),
        )


@pytest.mark.asyncio
async def test_create_assessment_rejects_naive_timestamps() -> None:
    session = _make_session()
    service = ResearchReviewService(session)

    with pytest.raises(ValueError, match="aware timestamps"):
        await service.create_assessment(
            research_case_id=uuid4(),
            assessment_type="filing_review",
            author_type="agent",
            author_id="analyst-1",
            schema_name="filing_review_v1",
            schema_version="1.0",
            result={"verdict": "positive"},
            data_as_of=datetime(2026, 1, 1),
            expires_at=datetime(2026, 2, 1),
            permissions=ALL_PERMS,
        )


@pytest.mark.asyncio
async def test_create_assessment_rejects_expiry_before_data_as_of() -> None:
    session = _make_session()
    service = ResearchReviewService(session)
    now = datetime.now(UTC)

    with pytest.raises(ValueError, match="expiry after data_as_of"):
        await service.create_assessment(
            research_case_id=uuid4(),
            assessment_type="filing_review",
            author_type="agent",
            author_id="analyst-1",
            schema_name="filing_review_v1",
            schema_version="1.0",
            result={"verdict": "positive"},
            data_as_of=now,
            expires_at=now - timedelta(days=1),
            permissions=ALL_PERMS,
        )


# ---------------------------------------------------------------------------
# request_review: permission required
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_request_review_requires_permission() -> None:
    session = _make_session()
    service = ResearchReviewService(session)

    with pytest.raises(PermissionError, match="research_reviews:request"):
        await service.request_review(
            assessment_id=uuid4(),
            reviewer_role="reviewer",
            requested_by="analyst-1",
            due_at=None,
            permissions=frozenset(),
        )


@pytest.mark.asyncio
async def test_request_review_assessment_not_found() -> None:
    session = _make_session(entity=None)
    service = ResearchReviewService(session)

    with pytest.raises(LookupError, match="not found"):
        await service.request_review(
            assessment_id=uuid4(),
            reviewer_role="reviewer",
            requested_by="analyst-1",
            due_at=None,
            permissions=ALL_PERMS,
        )


# ---------------------------------------------------------------------------
# decide: permission required
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_decide_requires_permission() -> None:
    session = _make_session()
    service = ResearchReviewService(session)

    with pytest.raises(PermissionError, match="research_reviews:decide"):
        await service.decide(
            review_request_id=uuid4(),
            decision="approved",
            reviewer_id="reviewer-1",
            reviewer_roles=frozenset({"reviewer"}),
            permissions=frozenset(),
            comment="LGTM",
            reason="evidence supports",
            correlation_id=uuid4(),
        )


# ---------------------------------------------------------------------------
# decide: double submission (already decided)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_decide_rejects_already_decided_request() -> None:
    request = _make_review_request(status="approved")
    session = _make_session(entity=request)
    service = ResearchReviewService(session)

    with pytest.raises(ValueError, match="already decided"):
        await service.decide(
            review_request_id=request.id,
            decision="approved",
            reviewer_id="reviewer-1",
            reviewer_roles=frozenset({"reviewer"}),
            permissions=ALL_PERMS,
            comment="LGTM",
            reason="evidence supports",
            correlation_id=uuid4(),
        )


@pytest.mark.asyncio
async def test_decide_rejects_rejected_request() -> None:
    request = _make_review_request(status="rejected")
    session = _make_session(entity=request)
    service = ResearchReviewService(session)

    with pytest.raises(ValueError, match="already decided"):
        await service.decide(
            review_request_id=request.id,
            decision="approved",
            reviewer_id="reviewer-1",
            reviewer_roles=frozenset({"reviewer"}),
            permissions=ALL_PERMS,
            comment="LGTM",
            reason="evidence supports",
            correlation_id=uuid4(),
        )


# ---------------------------------------------------------------------------
# decide: reviewer role mismatch
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_decide_rejects_wrong_reviewer_role() -> None:
    request = _make_review_request(status="pending", required_reviewer_role="senior_reviewer")
    session = _make_session(entity=request)
    service = ResearchReviewService(session)

    with pytest.raises(PermissionError, match="required role"):
        await service.decide(
            review_request_id=request.id,
            decision="approved",
            reviewer_id="reviewer-1",
            reviewer_roles=frozenset({"junior_reviewer"}),
            permissions=ALL_PERMS,
            comment="LGTM",
            reason="evidence supports",
            correlation_id=uuid4(),
        )


# ---------------------------------------------------------------------------
# decide: expired assessment
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_decide_rejects_expired_assessment() -> None:
    assessment = _make_assessment(expires_at=datetime(2026, 1, 1, tzinfo=UTC))
    request = _make_review_request(status="pending", assessment_id=assessment.id)

    session = AsyncMock()
    session.get = AsyncMock(side_effect=[request, assessment])
    session.flush = AsyncMock()

    service = ResearchReviewService(session)
    with pytest.raises(ValueError, match="expired"):
        await service.decide(
            review_request_id=request.id,
            decision="approved",
            reviewer_id="reviewer-1",
            reviewer_roles=frozenset({"reviewer"}),
            permissions=ALL_PERMS,
            comment="LGTM",
            reason="evidence supports",
            correlation_id=uuid4(),
        )


# ---------------------------------------------------------------------------
# decide: segregation of duties
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_decide_rejects_self_approve() -> None:
    assessment = _make_assessment(author_id="analyst-1")
    request = _make_review_request(status="pending", assessment_id=assessment.id)

    session = AsyncMock()
    session.get = AsyncMock(side_effect=[request, assessment])
    session.flush = AsyncMock()

    service = ResearchReviewService(session)
    with pytest.raises(ValueError, match="own work"):
        await service.decide(
            review_request_id=request.id,
            decision="approved",
            reviewer_id="analyst-1",
            reviewer_roles=frozenset({"reviewer"}),
            permissions=ALL_PERMS,
            comment="LGTM",
            reason="evidence supports",
            correlation_id=uuid4(),
        )


# ---------------------------------------------------------------------------
# decide: request not found
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_decide_request_not_found() -> None:
    session = _make_session(entity=None)
    service = ResearchReviewService(session)

    with pytest.raises(LookupError, match="not found"):
        await service.decide(
            review_request_id=uuid4(),
            decision="approved",
            reviewer_id="reviewer-1",
            reviewer_roles=frozenset({"reviewer"}),
            permissions=ALL_PERMS,
            comment="LGTM",
            reason="evidence supports",
            correlation_id=uuid4(),
        )


# ---------------------------------------------------------------------------
# decide: invalid decision value
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_decide_rejects_invalid_decision() -> None:
    assessment = _make_assessment(author_id="analyst-1")
    request = _make_review_request(status="pending", assessment_id=assessment.id)

    session = AsyncMock()
    session.get = AsyncMock(side_effect=[request, assessment])
    session.flush = AsyncMock()

    service = ResearchReviewService(session)
    with pytest.raises(ValueError, match="invalid review decision"):
        await service.decide(
            review_request_id=request.id,
            decision="maybe",
            reviewer_id="reviewer-1",
            reviewer_roles=frozenset({"reviewer"}),
            permissions=ALL_PERMS,
            comment="unsure",
            reason="unclear",
            correlation_id=uuid4(),
        )
