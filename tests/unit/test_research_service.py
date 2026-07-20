"""F3-PR01: ResearchCaseService transition tests."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from ia_investing.application.research import (
    CASE_TRANSITIONS,
    CreateResearchCase,
    ResearchCaseService,
    ResearchConcurrencyError,
    ResearchIdempotencyConflictError,
    required_permission,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

ALL_PERMS = frozenset({
    "research_cases:create",
    "research_cases:submit",
    "research_cases:assign",
    "research_cases:review",
    "research_cases:close",
    "research_cases:reopen",
})


def _make_case(state: str = "draft", lock_version: int = 1, **extra: Any) -> MagicMock:
    case = MagicMock()
    case.id = uuid4()
    case.state = state
    case.lock_version = lock_version
    case.idempotency_key = extra.get("idempotency_key", f"ik-{uuid4()}")
    case.request_hash = extra.get("request_hash", "hash-abc")
    return case


def _make_question(status: str = "open", is_required: bool = True) -> MagicMock:
    q = MagicMock()
    q.status = status
    q.is_required = is_required
    return q


def _make_session(**kwargs: Any) -> AsyncMock:
    session = AsyncMock()
    session.get = AsyncMock(return_value=kwargs.get("case"))
    session.execute = AsyncMock(return_value=kwargs.get("execute_result", MagicMock()))
    session.scalar = AsyncMock(return_value=kwargs.get("scalar_result", 0))
    return session


# ---------------------------------------------------------------------------
# Transition table completeness
# ---------------------------------------------------------------------------


def test_transition_table_covers_all_states() -> None:
    expected_states = {"draft", "triage", "in_research", "review", "approved", "rejected", "closed"}
    assert set(CASE_TRANSITIONS.keys()) == expected_states


def test_all_transitions_have_permissions() -> None:
    for current, targets in CASE_TRANSITIONS.items():
        for target, perm in targets.items():
            assert required_permission(current, target) == perm


def test_invalid_transition_raises() -> None:
    with pytest.raises(ValueError, match="invalid research case transition"):
        required_permission("draft", "approved")


def test_invalid_transition_draft_to_closed() -> None:
    with pytest.raises(ValueError, match="invalid"):
        required_permission("draft", "closed")


# ---------------------------------------------------------------------------
# Successful transitions
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_transition_draft_to_triage() -> None:
    case = _make_case(state="draft", lock_version=1)
    session = _make_session(case=case)

    service = ResearchCaseService(session)
    result = await service.transition(
        case_id=case.id,
        target="triage",
        expected_version=1,
        actor_subject="analyst-1",
        permissions=ALL_PERMS,
        correlation_id=uuid4(),
        reason="submitting for triage",
    )

    assert result.state == "triage"
    assert result.lock_version == 2


@pytest.mark.asyncio
async def test_transition_triage_to_in_research() -> None:
    case = _make_case(state="triage", lock_version=2)
    session = _make_session(case=case)

    service = ResearchCaseService(session)
    result = await service.transition(
        case_id=case.id,
        target="in_research",
        expected_version=2,
        actor_subject="analyst-1",
        permissions=ALL_PERMS,
        correlation_id=uuid4(),
        reason="assigning research",
    )

    assert result.state == "in_research"
    assert result.lock_version == 3


@pytest.mark.asyncio
async def test_transition_in_research_to_review() -> None:
    case = _make_case(state="in_research", lock_version=3)
    session = _make_session(case=case)

    service = ResearchCaseService(session)
    result = await service.transition(
        case_id=case.id,
        target="review",
        expected_version=3,
        actor_subject="analyst-1",
        permissions=ALL_PERMS,
        correlation_id=uuid4(),
        reason="submitting for review",
    )

    assert result.state == "review"
    assert result.lock_version == 4


@pytest.mark.asyncio
async def test_transition_review_to_approved() -> None:
    case = _make_case(state="review", lock_version=4)
    session = _make_session(case=case)

    service = ResearchCaseService(session)
    result = await service.transition(
        case_id=case.id,
        target="approved",
        expected_version=4,
        actor_subject="reviewer-1",
        permissions=ALL_PERMS,
        correlation_id=uuid4(),
        reason="looks good",
    )

    assert result.state == "approved"
    assert result.lock_version == 5


@pytest.mark.asyncio
async def test_transition_review_to_rejected() -> None:
    case = _make_case(state="review", lock_version=4)
    session = _make_session(case=case)

    service = ResearchCaseService(session)
    result = await service.transition(
        case_id=case.id,
        target="rejected",
        expected_version=4,
        actor_subject="reviewer-1",
        permissions=ALL_PERMS,
        correlation_id=uuid4(),
        reason="insufficient evidence",
    )

    assert result.state == "rejected"
    assert result.lock_version == 5


@pytest.mark.asyncio
async def test_transition_approved_to_closed() -> None:
    case = _make_case(state="approved", lock_version=5)
    session = _make_session(case=case)

    service = ResearchCaseService(session)
    result = await service.transition(
        case_id=case.id,
        target="closed",
        expected_version=5,
        actor_subject="analyst-1",
        permissions=ALL_PERMS,
        correlation_id=uuid4(),
        reason="case completed",
    )

    assert result.state == "closed"
    assert result.lock_version == 6


@pytest.mark.asyncio
async def test_transition_rejected_to_closed() -> None:
    case = _make_case(state="rejected", lock_version=5)
    session = _make_session(case=case)

    service = ResearchCaseService(session)
    result = await service.transition(
        case_id=case.id,
        target="closed",
        expected_version=5,
        actor_subject="analyst-1",
        permissions=ALL_PERMS,
        correlation_id=uuid4(),
        reason="closing rejected case",
    )

    assert result.state == "closed"
    assert result.lock_version == 6


@pytest.mark.asyncio
async def test_transition_closed_to_triage_reopen() -> None:
    case = _make_case(state="closed", lock_version=6)
    session = _make_session(case=case)

    service = ResearchCaseService(session)
    result = await service.transition(
        case_id=case.id,
        target="triage",
        expected_version=6,
        actor_subject="analyst-1",
        permissions=ALL_PERMS,
        correlation_id=uuid4(),
        reason="new evidence found",
    )

    assert result.state == "triage"
    assert result.lock_version == 7


# ---------------------------------------------------------------------------
# Concurrent transitions (lock_version mismatch)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_transition_concurrent_version_mismatch() -> None:
    case = _make_case(state="draft", lock_version=3)
    session = _make_session(case=case)

    service = ResearchCaseService(session)
    with pytest.raises(ResearchConcurrencyError, match="ETag no longer matches"):
        await service.transition(
            case_id=case.id,
            target="triage",
            expected_version=1,
            actor_subject="analyst-1",
            permissions=ALL_PERMS,
            correlation_id=uuid4(),
            reason="concurrent edit",
        )


@pytest.mark.asyncio
async def test_transition_concurrent_version_mismatch_on_review() -> None:
    case = _make_case(state="review", lock_version=7)
    session = _make_session(case=case)

    service = ResearchCaseService(session)
    with pytest.raises(ResearchConcurrencyError, match="ETag no longer matches"):
        await service.transition(
            case_id=case.id,
            target="approved",
            expected_version=4,
            actor_subject="reviewer-1",
            permissions=ALL_PERMS,
            correlation_id=uuid4(),
            reason="stale review",
        )


# ---------------------------------------------------------------------------
# Permission denied
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_transition_permission_denied() -> None:
    case = _make_case(state="review", lock_version=4)
    session = _make_session(case=case)

    service = ResearchCaseService(session)
    with pytest.raises(PermissionError, match="permission required"):
        await service.transition(
            case_id=case.id,
            target="approved",
            expected_version=4,
            actor_subject="analyst-1",
            permissions=frozenset(),
            correlation_id=uuid4(),
            reason="no perms",
        )


@pytest.mark.asyncio
async def test_transition_wrong_permission_for_target() -> None:
    case = _make_case(state="draft", lock_version=1)
    session = _make_session(case=case)

    service = ResearchCaseService(session)
    with pytest.raises(PermissionError, match="research_cases:submit"):
        await service.transition(
            case_id=case.id,
            target="triage",
            expected_version=1,
            actor_subject="analyst-1",
            permissions=frozenset({"research_cases:review"}),
            correlation_id=uuid4(),
            reason="wrong perm",
        )


# ---------------------------------------------------------------------------
# Case not found
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_transition_case_not_found() -> None:
    session = _make_session(case=None)

    service = ResearchCaseService(session)
    with pytest.raises(LookupError, match="not found"):
        await service.transition(
            case_id=uuid4(),
            target="triage",
            expected_version=1,
            actor_subject="analyst-1",
            permissions=ALL_PERMS,
            correlation_id=uuid4(),
            reason="missing",
        )


# ---------------------------------------------------------------------------
# Invalid transitions at service level
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_transition_draft_to_approved_invalid() -> None:
    case = _make_case(state="draft", lock_version=1)
    session = _make_session(case=case)

    service = ResearchCaseService(session)
    with pytest.raises(ValueError, match="invalid research case transition"):
        await service.transition(
            case_id=case.id,
            target="approved",
            expected_version=1,
            actor_subject="analyst-1",
            permissions=ALL_PERMS,
            correlation_id=uuid4(),
            reason="skip steps",
        )


@pytest.mark.asyncio
async def test_transition_draft_to_closed_invalid() -> None:
    case = _make_case(state="draft", lock_version=1)
    session = _make_session(case=case)

    service = ResearchCaseService(session)
    with pytest.raises(ValueError, match="invalid research case transition"):
        await service.transition(
            case_id=case.id,
            target="closed",
            expected_version=1,
            actor_subject="analyst-1",
            permissions=ALL_PERMS,
            correlation_id=uuid4(),
            reason="skip steps",
        )


# ---------------------------------------------------------------------------
# Closed case blocks on open questions
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_transition_to_closed_blocked_by_open_questions() -> None:
    case = _make_case(state="approved", lock_version=5)
    open_q = _make_question(status="open", is_required=True)
    result = MagicMock()
    result.scalars.return_value.all.return_value = [open_q]
    session = _make_session(case=case, execute_result=result, scalar_result=1)

    service = ResearchCaseService(session)
    with pytest.raises(ValueError, match="required research questions are still open"):
        await service.transition(
            case_id=case.id,
            target="closed",
            expected_version=5,
            actor_subject="analyst-1",
            permissions=ALL_PERMS,
            correlation_id=uuid4(),
            reason="closing",
        )


@pytest.mark.asyncio
async def test_transition_to_closed_allowed_when_questions_done() -> None:
    case = _make_case(state="approved", lock_version=5)
    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    session = _make_session(case=case, execute_result=result, scalar_result=0)

    service = ResearchCaseService(session)
    result = await service.transition(
        case_id=case.id,
        target="closed",
        expected_version=5,
        actor_subject="analyst-1",
        permissions=ALL_PERMS,
        correlation_id=uuid4(),
        reason="closing",
    )

    assert result.state == "closed"


# ---------------------------------------------------------------------------
# Create: idempotency and permissions
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_requires_permission() -> None:
    session = _make_session()
    service = ResearchCaseService(session)
    cmd = CreateResearchCase(
        case_type="fundamental",
        title="PETR4 analysis",
        priority="high",
        issuer_id=uuid4(),
        instrument_id=None,
        data_as_of=datetime.now(UTC),
        due_at=None,
        questions=("What is the target price?",),
    )

    with pytest.raises(PermissionError, match="research_cases:create"):
        await service.create(
            command=cmd,
            actor_subject="analyst-1",
            permissions=frozenset(),
            idempotency_key="ik-1",
            correlation_id=uuid4(),
        )


@pytest.mark.asyncio
async def test_create_rejects_naive_datetime() -> None:
    session = _make_session()
    service = ResearchCaseService(session)
    cmd = CreateResearchCase(
        case_type="fundamental",
        title="PETR4",
        priority="high",
        issuer_id=uuid4(),
        instrument_id=None,
        data_as_of=datetime(2026, 1, 1),
        due_at=None,
        questions=("Q1",),
    )

    with pytest.raises(ValueError, match="timezone"):
        await service.create(
            command=cmd,
            actor_subject="analyst-1",
            permissions=frozenset({"research_cases:create"}),
            idempotency_key="ik-2",
            correlation_id=uuid4(),
        )


# ---------------------------------------------------------------------------
# list_cases: as_of timezone
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_cases_rejects_naive_as_of() -> None:
    session = _make_session()
    service = ResearchCaseService(session)

    with pytest.raises(ValueError, match="timezone"):
        await service.list_cases(state=None, as_of=datetime(2026, 1, 1), after=None, limit=10)
