from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from ia_investing.application.paper_execution._reconciliation import ReconciliationService
from ia_investing.domain.identity import InstitutionalAccessContext


def _context(org_id: UUID | None = None) -> InstitutionalAccessContext:
    org = org_id or uuid4()
    return InstitutionalAccessContext(
        "manager", org, frozenset({uuid4()}), frozenset({"reconciliation:write"}), "paper"
    )


def _mock_session() -> AsyncMock:
    session = AsyncMock()
    session.get = AsyncMock(return_value=None)
    session.execute = AsyncMock(return_value=MagicMock())
    session.scalars = AsyncMock(return_value=MagicMock())
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.scalar = AsyncMock(return_value=None)
    return session


def _mock_portfolio(organization_id: UUID | None = None) -> MagicMock:
    p = MagicMock()
    p.id = uuid4()
    p.organization_id = organization_id or uuid4()
    p.base_currency = "BRL"
    return p


@pytest.mark.asyncio
async def test_reconcile_portfolio_raises_without_permission() -> None:
    session = _mock_session()
    ctx = InstitutionalAccessContext("manager", uuid4(), frozenset({uuid4()}), frozenset(), "paper")
    service = ReconciliationService(session)
    with pytest.raises(PermissionError, match="reconciliation:write"):
        await service.reconcile_portfolio(uuid4(), as_of=datetime.now(UTC), context=ctx, correlation_id=uuid4())


@pytest.mark.asyncio
async def test_reconcile_portfolio_raises_on_naive_datetime() -> None:
    session = _mock_session()
    service = ReconciliationService(session)
    with pytest.raises(ValueError, match="timezone"):
        as_of = datetime(2026, 1, 1)
        await service.reconcile_portfolio(
            uuid4(), as_of=as_of, context=_context(), correlation_id=uuid4()
        )


@pytest.mark.asyncio
async def test_reconcile_portfolio_raises_when_portfolio_not_found() -> None:
    session = _mock_session()
    session.get.return_value = None
    service = ReconciliationService(session)
    with pytest.raises(LookupError, match="not found"):
        await service.reconcile_portfolio(
            uuid4(), as_of=datetime.now(UTC), context=_context(), correlation_id=uuid4()
        )


@pytest.mark.asyncio
async def test_reconcile_portfolio_raises_when_org_mismatch() -> None:
    session = _mock_session()
    ctx = _context()
    portfolio = _mock_portfolio(uuid4())  # different org
    session.get.return_value = portfolio
    service = ReconciliationService(session)
    with pytest.raises(LookupError, match="not found"):
        await service.reconcile_portfolio(
            portfolio.id, as_of=datetime.now(UTC), context=ctx, correlation_id=uuid4()
        )


@pytest.mark.asyncio
async def test_resolve_break_raises_without_permission() -> None:
    session = _mock_session()
    ctx = InstitutionalAccessContext("manager", uuid4(), frozenset({uuid4()}), frozenset(), "paper")
    service = ReconciliationService(session)
    with pytest.raises(PermissionError, match="reconciliation:write"):
        await service.resolve_break(
            uuid4(), resolution={}, context=ctx, correlation_id=uuid4()
        )


@pytest.mark.asyncio
async def test_resolve_break_raises_when_not_found() -> None:
    session = _mock_session()
    session.get.return_value = None
    service = ReconciliationService(session)
    with pytest.raises(LookupError, match="not found"):
        await service.resolve_break(
            uuid4(), resolution={}, context=_context(), correlation_id=uuid4()
        )


@pytest.mark.asyncio
async def test_resolve_break_returns_early_when_already_resolved() -> None:
    session = _mock_session()
    existing = MagicMock()
    existing.status = "resolved"
    existing.organization_id = uuid4()
    session.get.return_value = existing
    ctx = _context(existing.organization_id)
    service = ReconciliationService(session)
    result = await service.resolve_break(
        existing.id, resolution={}, context=ctx, correlation_id=uuid4()
    )
    assert result.status == "resolved"


@pytest.mark.asyncio
async def test_resolve_break_raises_when_evidence_missing() -> None:
    session = _mock_session()
    existing = MagicMock()
    existing.status = "open"
    existing.organization_id = uuid4()
    session.get.return_value = existing
    ctx = _context(existing.organization_id)
    service = ReconciliationService(session)
    with pytest.raises(ValueError, match="requires method and evidence"):
        await service.resolve_break(
            existing.id, resolution={"method": "review"}, context=ctx, correlation_id=uuid4()
        )


@pytest.mark.asyncio
async def test_resolve_break_raises_when_method_missing() -> None:
    session = _mock_session()
    existing = MagicMock()
    existing.status = "open"
    existing.organization_id = uuid4()
    session.get.return_value = existing
    ctx = _context(existing.organization_id)
    service = ReconciliationService(session)
    with pytest.raises(ValueError, match="requires method and evidence"):
        await service.resolve_break(
            existing.id, resolution={"evidence": "doc.pdf"}, context=ctx, correlation_id=uuid4()
        )
