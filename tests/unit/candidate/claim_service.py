"""F3-PR02: ClaimService and evidence edge-case tests."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from ia_investing.application.research import ClaimService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

ALL_PERMS = frozenset({"research_claims:verify", "research_evidence:read"})


def _make_claim(
    status: str = "pending",
    is_material: bool = False,
) -> MagicMock:
    claim = MagicMock()
    claim.id = uuid4()
    claim.status = status
    claim.is_material = is_material
    return claim


def _make_evidence(
    *,
    knowledge_at: datetime | None = None,
    revoked_at: datetime | None = None,
    valid_until: datetime | None = None,
) -> MagicMock:
    ev = MagicMock()
    ev.id = uuid4()
    ev.knowledge_at = knowledge_at or datetime(2026, 1, 1, tzinfo=UTC)
    ev.revoked_at = revoked_at
    ev.valid_until = valid_until
    return ev


def _make_link(evidence_id, stance: str = "supporting") -> MagicMock:
    link = MagicMock()
    link.evidence_id = evidence_id
    link.stance = stance
    return link


def _make_session(**kwargs) -> AsyncMock:
    session = AsyncMock()
    session.get = AsyncMock(return_value=kwargs.get("claim"))
    session.execute = AsyncMock(return_value=kwargs.get("execute_result", MagicMock()))
    return session


# ---------------------------------------------------------------------------
# Permission required
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_verify_requires_permission() -> None:
    session = _make_session()
    service = ClaimService(session)

    with pytest.raises(PermissionError, match="research_claims:verify"):
        await service.verify(
            claim_id=uuid4(),
            cutoff=datetime.now(UTC),
            actor_subject="analyst-1",
            permissions=frozenset(),
            correlation_id=uuid4(),
        )


# ---------------------------------------------------------------------------
# Claim not found
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_verify_claim_not_found() -> None:
    session = _make_session(claim=None)
    service = ClaimService(session)

    with pytest.raises(LookupError, match="not found"):
        await service.verify(
            claim_id=uuid4(),
            cutoff=datetime.now(UTC),
            actor_subject="analyst-1",
            permissions=ALL_PERMS,
            correlation_id=uuid4(),
        )


# ---------------------------------------------------------------------------
# Naive cutoff
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_verify_rejects_naive_cutoff() -> None:
    claim = _make_claim()
    session = _make_session(claim=claim)
    service = ClaimService(session)

    with pytest.raises(ValueError, match="timezone"):
        await service.verify(
            claim_id=claim.id,
            cutoff=datetime(2026, 7, 18),
            actor_subject="analyst-1",
            permissions=ALL_PERMS,
            correlation_id=uuid4(),
        )


# ---------------------------------------------------------------------------
# Material claim without valid evidence fails
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_material_claim_fails_without_evidence() -> None:
    claim = _make_claim(is_material=True)
    session = _make_session(
        claim=claim, execute_result=MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[]))))
    )
    service = ClaimService(session)

    with pytest.raises(ValueError, match="material claim cannot be verified"):
        await service.verify(
            claim_id=claim.id,
            cutoff=datetime(2026, 7, 18, tzinfo=UTC),
            actor_subject="analyst-1",
            permissions=ALL_PERMS,
            correlation_id=uuid4(),
        )


# ---------------------------------------------------------------------------
# Evidence filters: revoked, future, wrong stance
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_verify_filters_revoked_evidence() -> None:
    claim = _make_claim(is_material=True)
    ev = _make_evidence(revoked_at=datetime(2026, 6, 1, tzinfo=UTC))
    _make_link(ev.id, stance="supporting")
    result = MagicMock()
    result.scalars.return_value.all.return_value = [ev]
    result.__iter__ = lambda self: iter([(_make_evidence(revoked_at=datetime(2026, 6, 1, tzinfo=UTC)), 0.8)])
    session = _make_session(claim=claim, execute_result=result)
    service = ClaimService(session)

    with pytest.raises(ValueError, match="material claim cannot be verified"):
        await service.verify(
            claim_id=claim.id,
            cutoff=datetime(2026, 7, 18, tzinfo=UTC),
            actor_subject="analyst-1",
            permissions=ALL_PERMS,
            correlation_id=uuid4(),
        )


@pytest.mark.asyncio
async def test_verify_filters_future_evidence() -> None:
    claim = _make_claim(is_material=True)
    ev = _make_evidence(knowledge_at=datetime(2026, 12, 1, tzinfo=UTC))
    result = MagicMock()
    result.__iter__ = lambda self: iter([(ev, 0.8)])
    session = _make_session(claim=claim, execute_result=result)
    service = ClaimService(session)

    with pytest.raises(ValueError, match="material claim cannot be verified"):
        await service.verify(
            claim_id=claim.id,
            cutoff=datetime(2026, 7, 18, tzinfo=UTC),
            actor_subject="analyst-1",
            permissions=ALL_PERMS,
            correlation_id=uuid4(),
        )


@pytest.mark.asyncio
async def test_verify_filters_expired_evidence() -> None:
    claim = _make_claim(is_material=True)
    ev = _make_evidence(valid_until=datetime(2026, 1, 1, tzinfo=UTC))
    result = MagicMock()
    result.__iter__ = lambda self: iter([(ev, 0.8)])
    session = _make_session(claim=claim, execute_result=result)
    service = ClaimService(session)

    with pytest.raises(ValueError, match="material claim cannot be verified"):
        await service.verify(
            claim_id=claim.id,
            cutoff=datetime(2026, 7, 18, tzinfo=UTC),
            actor_subject="analyst-1",
            permissions=ALL_PERMS,
            correlation_id=uuid4(),
        )


@pytest.mark.asyncio
async def test_verify_filters_opposing_evidence() -> None:
    claim = _make_claim(is_material=True)
    ev = _make_evidence()
    result = MagicMock()
    result.__iter__ = lambda self: iter([(ev, 0.8)])
    session = _make_session(claim=claim, execute_result=result)
    service = ClaimService(session)

    with pytest.raises(ValueError, match="material claim cannot be verified"):
        await service.verify(
            claim_id=claim.id,
            cutoff=datetime(2026, 7, 18, tzinfo=UTC),
            actor_subject="analyst-1",
            permissions=ALL_PERMS,
            correlation_id=uuid4(),
        )


# ---------------------------------------------------------------------------
# Non-material claim succeeds without evidence
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_non_material_claim_succeeds_without_evidence() -> None:
    claim = _make_claim(is_material=False)
    result = MagicMock()
    result.__iter__ = lambda self: iter([])
    session = _make_session(claim=claim, execute_result=result)
    service = ClaimService(session)

    verified = await service.verify(
        claim_id=claim.id,
        cutoff=datetime(2026, 7, 18, tzinfo=UTC),
        actor_subject="analyst-1",
        permissions=ALL_PERMS,
        correlation_id=uuid4(),
    )

    assert verified.status == "verified"


# ---------------------------------------------------------------------------
# Valid supporting evidence allows verification
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_material_claim_verifies_with_valid_evidence() -> None:
    claim = _make_claim(is_material=True)
    ev = _make_evidence(knowledge_at=datetime(2026, 1, 1, tzinfo=UTC), revoked_at=None, valid_until=None)
    scalars_result = MagicMock()
    scalars_result.__iter__ = MagicMock(return_value=iter([ev]))
    result = MagicMock()
    result.scalars.return_value = scalars_result
    session = _make_session(claim=claim, execute_result=result)
    service = ClaimService(session)

    verified = await service.verify(
        claim_id=claim.id,
        cutoff=datetime(2026, 7, 18, tzinfo=UTC),
        actor_subject="analyst-1",
        permissions=ALL_PERMS,
        correlation_id=uuid4(),
    )

    assert verified.status == "verified"
