"""F3-PR04: ThesisService invalidation, rollback, two revisions, as_of tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from ia_investing.application.theses import ThesisService, ThesisSnapshot
from ia_investing.application.research import ResearchConcurrencyError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

ALL_PERMS = frozenset({
    "research_theses:create",
    "research_theses:revise",
    "research_theses:approve",
    "research_claims:verify",
    "research_evidence:read",
})


def _snapshot(
    summary: str = "Base thesis",
    recommendation: str = "buy",
    confidence: Decimal = Decimal("0.80"),
    data_as_of: datetime | None = None,
    expires_at: datetime | None = None,
) -> ThesisSnapshot:
    now = data_as_of or datetime(2026, 7, 18, tzinfo=UTC)
    exp = expires_at or (now + timedelta(days=90))
    return ThesisSnapshot(
        summary=summary,
        assumptions=[{"name": "WACC", "value": "0.10"}],
        catalysts=[{"text": "Crescimento"}],
        risks=[{"text": "Câmbio"}],
        invalidation_criteria=[{"metric": "leverage", "op": ">", "value": "4"}],
        recommendation=recommendation,
        recommendation_confidence=confidence,
        data_as_of=now,
        expires_at=exp,
    )


def _make_thesis(status: str = "draft", lock_version: int = 1) -> MagicMock:
    t = MagicMock()
    t.id = uuid4()
    t.status = status
    t.lock_version = lock_version
    return t


def _make_version(
    version_number: int = 1,
    status: str = "draft",
    thesis_id=None,
    recommendation: str = "buy",
    summary: str = "Base",
    expires_at: datetime | None = None,
    data_as_of: datetime | None = None,
) -> MagicMock:
    now = datetime.now(UTC)
    v = MagicMock()
    v.id = uuid4()
    v.thesis_id = thesis_id or uuid4()
    v.version_number = version_number
    v.status = status
    v.summary = summary
    v.recommendation = recommendation
    v.recommendation_confidence = Decimal("0.80")
    v.assumptions = [{"name": "WACC", "value": "0.10"}]
    v.catalysts = [{"text": "Crescimento"}]
    v.risks = [{"text": "Câmbio"}]
    v.invalidation_criteria = [{"metric": "leverage", "op": ">", "value": "4"}]
    v.data_as_of = data_as_of or now
    v.expires_at = expires_at or (now + timedelta(days=90))
    v.valid_from = None
    v.valid_to = None
    v.content_sha256 = "hash-v1"
    v.change_set = {}
    v.created_by = "analyst-1"
    return v


def _make_review_decision(
    decision: str = "approved",
    reviewer_id: str = "reviewer-1",
) -> MagicMock:
    d = MagicMock()
    d.id = uuid4()
    d.decision = decision
    d.reviewer_id = reviewer_id
    return d


def _make_claim(status: str = "verified") -> MagicMock:
    c = MagicMock()
    c.id = uuid4()
    c.status = status
    return c


def _make_session(**kwargs) -> AsyncMock:
    session = AsyncMock()
    session.get = AsyncMock(return_value=kwargs.get("entity"))
    session.execute = AsyncMock(return_value=kwargs.get("execute_result", MagicMock()))
    session.flush = AsyncMock()
    return session


# ---------------------------------------------------------------------------
# create_draft: permission required
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_draft_requires_permission() -> None:
    session = _make_session()
    service = ThesisService(session)

    with pytest.raises(PermissionError, match="research_theses:create"):
        await service.create_draft(
            issuer_id=uuid4(),
            instrument_id=None,
            snapshot=_snapshot(),
            actor_subject="analyst-1",
            permissions=frozenset(),
            evidence_ids=[],
            claim_ids=[],
        )


@pytest.mark.asyncio
async def test_create_draft_rejects_naive_timestamps() -> None:
    session = _make_session()
    service = ThesisService(session)
    snap = ThesisSnapshot(
        summary="Test",
        assumptions=[],
        catalysts=[],
        risks=[],
        invalidation_criteria=[],
        recommendation="buy",
        recommendation_confidence=Decimal("0.80"),
        data_as_of=datetime(2026, 1, 1),
        expires_at=datetime(2026, 4, 1),
    )

    with pytest.raises(ValueError, match="timezone"):
        await service.create_draft(
            issuer_id=uuid4(),
            instrument_id=None,
            snapshot=snap,
            actor_subject="analyst-1",
            permissions=ALL_PERMS,
            evidence_ids=[],
            claim_ids=[],
        )


@pytest.mark.asyncio
async def test_create_draft_rejects_expiry_before_data_as_of() -> None:
    session = _make_session()
    service = ThesisService(session)
    now = datetime.now(UTC)
    snap = ThesisSnapshot(
        summary="Test",
        assumptions=[],
        catalysts=[],
        risks=[],
        invalidation_criteria=[],
        recommendation="buy",
        recommendation_confidence=Decimal("0.80"),
        data_as_of=now,
        expires_at=now - timedelta(days=1),
    )

    with pytest.raises(ValueError, match="expiry must be after"):
        await service.create_draft(
            issuer_id=uuid4(),
            instrument_id=None,
            snapshot=snap,
            actor_subject="analyst-1",
            permissions=ALL_PERMS,
            evidence_ids=[],
            claim_ids=[],
        )


# ---------------------------------------------------------------------------
# revise: permission required
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_revise_requires_permission() -> None:
    session = _make_session()
    service = ThesisService(session)

    with pytest.raises(PermissionError, match="research_theses:revise"):
        await service.revise(
            thesis_id=uuid4(),
            expected_version=1,
            snapshot=_snapshot(),
            actor_subject="analyst-1",
            permissions=frozenset(),
            evidence_ids=[],
            claim_ids=[],
        )


@pytest.mark.asyncio
async def test_revise_thesis_not_found() -> None:
    session = _make_session(entity=None)
    service = ThesisService(session)

    with pytest.raises(LookupError, match="not found"):
        await service.revise(
            thesis_id=uuid4(),
            expected_version=1,
            snapshot=_snapshot(),
            actor_subject="analyst-1",
            permissions=ALL_PERMS,
            evidence_ids=[],
            claim_ids=[],
        )


# ---------------------------------------------------------------------------
# revise: concurrency conflict
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_revise_concurrency_conflict() -> None:
    thesis = _make_thesis(lock_version=3)
    session = _make_session(entity=thesis)
    service = ThesisService(session)

    with pytest.raises(ResearchConcurrencyError, match="ETag no longer matches"):
        await service.revise(
            thesis_id=thesis.id,
            expected_version=1,
            snapshot=_snapshot(),
            actor_subject="analyst-1",
            permissions=ALL_PERMS,
            evidence_ids=[],
            claim_ids=[],
        )


# ---------------------------------------------------------------------------
# Two revisions: version_number increments
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_two_revisions_increment_version_number() -> None:
    thesis = _make_thesis(status="draft", lock_version=2)
    v1 = _make_version(version_number=1, thesis_id=thesis.id)

    session = AsyncMock()
    session.get = AsyncMock(return_value=thesis)
    session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=v1)))
    session.flush = AsyncMock()
    service = ThesisService(session)

    result = await service.revise(
        thesis_id=thesis.id,
        expected_version=2,
        snapshot=_snapshot(summary="Revision 2"),
        actor_subject="analyst-1",
        permissions=ALL_PERMS,
        evidence_ids=[],
        claim_ids=[],
    )

    assert result.version_number == 2
    assert thesis.lock_version == 3


# ---------------------------------------------------------------------------
# activate: permission required
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_activate_requires_permission() -> None:
    session = _make_session()
    service = ThesisService(session)

    with pytest.raises(PermissionError, match="research_theses:approve"):
        await service.activate(
            version_id=uuid4(),
            review_decision_id=uuid4(),
            actor_subject="reviewer-1",
            permissions=frozenset(),
            correlation_id=uuid4(),
        )


# ---------------------------------------------------------------------------
# activate: version not found
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_activate_version_not_found() -> None:
    session = _make_session(entity=None)
    service = ThesisService(session)

    with pytest.raises(LookupError, match="not found"):
        await service.activate(
            version_id=uuid4(),
            review_decision_id=uuid4(),
            actor_subject="reviewer-1",
            permissions=ALL_PERMS,
            correlation_id=uuid4(),
        )


# ---------------------------------------------------------------------------
# activate: only draft versions can be activated
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_activate_rejects_already_active_version() -> None:
    version = _make_version(status="active")
    session = _make_session(entity=version)
    service = ThesisService(session)

    with pytest.raises(ValueError, match="only a draft"):
        await service.activate(
            version_id=version.id,
            review_decision_id=uuid4(),
            actor_subject="reviewer-1",
            permissions=ALL_PERMS,
            correlation_id=uuid4(),
        )


# ---------------------------------------------------------------------------
# activate: requires approved review
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_activate_rejects_without_approved_review() -> None:
    version = _make_version(status="draft")
    decision = _make_review_decision(decision="rejected")

    session = AsyncMock()
    session.get = AsyncMock(return_value=version)
    session.flush = AsyncMock()
    service = ThesisService(session)

    with pytest.raises(ValueError, match="approved independent review"):
        await service.activate(
            version_id=version.id,
            review_decision_id=decision.id,
            actor_subject="reviewer-1",
            permissions=ALL_PERMS,
            correlation_id=uuid4(),
        )


# ---------------------------------------------------------------------------
# activate: reviewer must match
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_activate_rejects_wrong_reviewer() -> None:
    version = _make_version(status="draft")
    decision = _make_review_decision(decision="approved", reviewer_id="reviewer-1")

    session = AsyncMock()
    session.get = AsyncMock(side_effect=[version, decision])
    session.flush = AsyncMock()
    service = ThesisService(session)

    with pytest.raises(PermissionError, match="recorded reviewer"):
        await service.activate(
            version_id=version.id,
            review_decision_id=decision.id,
            actor_subject="reviewer-2",
            permissions=ALL_PERMS,
            correlation_id=uuid4(),
        )


# ---------------------------------------------------------------------------
# activate: requires evidence and verified claims
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_activate_rejects_without_evidence() -> None:
    version = _make_version(status="draft")
    decision = _make_review_decision(decision="approved", reviewer_id="reviewer-1")

    session = AsyncMock()
    session.get = AsyncMock(side_effect=[version, decision])
    session.flush = AsyncMock()
    session.scalar = AsyncMock(side_effect=[0, 0])
    service = ThesisService(session)

    with pytest.raises(ValueError, match="evidence and at least one verified claim"):
        await service.activate(
            version_id=version.id,
            review_decision_id=decision.id,
            actor_subject="reviewer-1",
            permissions=ALL_PERMS,
            correlation_id=uuid4(),
        )


# ---------------------------------------------------------------------------
# activate: expired version
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_activate_rejects_expired_version() -> None:
    version = _make_version(status="draft", expires_at=datetime(2026, 1, 1, tzinfo=UTC))
    decision = _make_review_decision(decision="approved", reviewer_id="reviewer-1")

    session = AsyncMock()
    session.get = AsyncMock(side_effect=[version, decision])
    session.flush = AsyncMock()
    session.scalar = AsyncMock(side_effect=[1, 1])
    service = ThesisService(session)

    with pytest.raises(ValueError, match="expired"):
        await service.activate(
            version_id=version.id,
            review_decision_id=decision.id,
            actor_subject="reviewer-1",
            permissions=ALL_PERMS,
            correlation_id=uuid4(),
        )


# ---------------------------------------------------------------------------
# active_as_of: timezone required
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_active_as_of_requires_timezone() -> None:
    session = _make_session()
    service = ThesisService(session)

    with pytest.raises(ValueError, match="timezone"):
        await service.active_as_of(thesis_id=uuid4(), as_of=datetime(2026, 7, 18))


# ---------------------------------------------------------------------------
# get_lock_version
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_lock_version_returns_none_for_missing_thesis() -> None:
    session = _make_session(entity=None)
    service = ThesisService(session)

    result = await service.get_lock_version(uuid4())
    assert result is None


@pytest.mark.asyncio
async def test_get_lock_version_returns_version() -> None:
    thesis = _make_thesis(lock_version=5)
    session = _make_session(entity=thesis)
    service = ThesisService(session)

    result = await service.get_lock_version(thesis.id)
    assert result == 5


# ---------------------------------------------------------------------------
# mark_expired_stale
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mark_expired_stale_returns_count() -> None:
    result_mock = MagicMock()
    result_mock.rowcount = 3
    session = AsyncMock()
    session.execute = AsyncMock(return_value=result_mock)
    service = ThesisService(session)

    count = await service.mark_expired_stale(now=datetime.now(UTC))
    assert count == 3


@pytest.mark.asyncio
async def test_mark_expired_stale_returns_zero_when_none() -> None:
    result_mock = MagicMock()
    result_mock.rowcount = 0
    session = AsyncMock()
    session.execute = AsyncMock(return_value=result_mock)
    service = ThesisService(session)

    count = await service.mark_expired_stale(now=datetime.now(UTC))
    assert count == 0
