"""Tests for ia_investing.application.paper_execution._reconciliation — extended coverage."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from ia_investing.application.paper_execution._reconciliation import (
    ExecutionData,
    ReconciliationService,
)
from ia_investing.domain.identity import InstitutionalAccessContext


def _context(org_id: UUID | None = None, perms: frozenset[str] | None = None) -> InstitutionalAccessContext:
    org = org_id or uuid4()
    return InstitutionalAccessContext(
        "ops_user", org, frozenset({uuid4()}), perms or frozenset({"reconciliation:write"}), "paper"
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


def _mock_portfolio(org_id: UUID | None = None) -> MagicMock:
    p = MagicMock()
    p.id = uuid4()
    p.organization_id = org_id or uuid4()
    p.base_currency = "BRL"
    return p


# --- Permission / validation tests ---


@pytest.mark.unit
@pytest.mark.asyncio
async def test_reconcile_portfolio_requires_reconciliation_write() -> None:
    session = _mock_session()
    ctx = InstitutionalAccessContext("ops", uuid4(), frozenset({uuid4()}), frozenset(), "paper")
    service = ReconciliationService(session)
    with pytest.raises(PermissionError, match="reconciliation:write"):
        await service.reconcile_portfolio(
            uuid4(), as_of=datetime.now(UTC), context=ctx, correlation_id=uuid4()
        )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_reconcile_portfolio_rejects_naive_datetime() -> None:
    session = _mock_session()
    service = ReconciliationService(session)
    with pytest.raises(ValueError, match="timezone"):
        await service.reconcile_portfolio(
            uuid4(), as_of=datetime(2026, 1, 1), context=_context(), correlation_id=uuid4()
        )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_reconcile_portfolio_portfolio_not_found() -> None:
    session = _mock_session()
    session.get.return_value = None
    service = ReconciliationService(session)
    with pytest.raises(LookupError, match="not found"):
        await service.reconcile_portfolio(
            uuid4(), as_of=datetime.now(UTC), context=_context(), correlation_id=uuid4()
        )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_reconcile_portfolio_org_mismatch() -> None:
    session = _mock_session()
    ctx = _context()
    portfolio = _mock_portfolio(uuid4())  # different org
    session.get.return_value = portfolio
    service = ReconciliationService(session)
    with pytest.raises(LookupError, match="not found"):
        await service.reconcile_portfolio(
            portfolio.id, as_of=datetime.now(UTC), context=ctx, correlation_id=uuid4()
        )


# --- resolve_break tests ---


@pytest.mark.unit
@pytest.mark.asyncio
async def test_resolve_break_requires_permission() -> None:
    session = _mock_session()
    ctx = InstitutionalAccessContext("ops", uuid4(), frozenset({uuid4()}), frozenset(), "paper")
    service = ReconciliationService(session)
    with pytest.raises(PermissionError, match="reconciliation:write"):
        await service.resolve_break(uuid4(), resolution={}, context=ctx, correlation_id=uuid4())


@pytest.mark.unit
@pytest.mark.asyncio
async def test_resolve_break_not_found() -> None:
    session = _mock_session()
    session.get.return_value = None
    service = ReconciliationService(session)
    with pytest.raises(LookupError, match="not found"):
        await service.resolve_break(uuid4(), resolution={}, context=_context(), correlation_id=uuid4())


@pytest.mark.unit
@pytest.mark.asyncio
async def test_resolve_break_already_resolved() -> None:
    session = _mock_session()
    existing = MagicMock()
    existing.status = "resolved"
    existing.organization_id = uuid4()
    session.get.return_value = existing
    ctx = _context(existing.organization_id)
    service = ReconciliationService(session)
    result = await service.resolve_break(existing.id, resolution={}, context=ctx, correlation_id=uuid4())
    assert result.status == "resolved"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_resolve_break_missing_evidence() -> None:
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


@pytest.mark.unit
@pytest.mark.asyncio
async def test_resolve_break_missing_method() -> None:
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


@pytest.mark.unit
@pytest.mark.asyncio
async def test_resolve_break_success() -> None:
    session = _mock_session()
    existing = MagicMock()
    existing.status = "open"
    existing.organization_id = uuid4()
    existing.id = uuid4()
    session.get.return_value = existing
    ctx = _context(existing.organization_id)
    service = ReconciliationService(session)

    with patch(
        "ia_investing.application.paper_execution._reconciliation.audit_entity",
        new_callable=AsyncMock,
    ):
        result = await service.resolve_break(
            existing.id,
            resolution={"method": "review", "evidence": "confirmed.pdf"},
            context=ctx,
            correlation_id=uuid4(),
        )

    assert result.status == "resolved"
    assert result.resolution is not None and "resolved_by" in result.resolution


@pytest.mark.unit
@pytest.mark.asyncio
async def test_resolve_break_compensating_entry() -> None:
    session = _mock_session()
    existing = MagicMock()
    existing.status = "open"
    existing.organization_id = uuid4()
    existing.id = uuid4()
    existing.rule = "fill_missing_ledger"
    existing.resource_key = "fill-123"
    existing.portfolio_id = uuid4()
    existing.expected = {"quantity": "100", "amount": "5000"}
    existing.actual = {"quantity": "100", "amount": "5100"}
    session.get.return_value = existing
    ctx = _context(existing.organization_id)
    service = ReconciliationService(session)

    with patch(
        "ia_investing.application.paper_execution._reconciliation.audit_entity",
        new_callable=AsyncMock,
    ), patch.object(
        service, "_resolve_instrument_from_break", new_callable=AsyncMock, return_value=uuid4()
    ), patch.object(
        service, "_create_compensating_entry", new_callable=AsyncMock
    ) as mock_create:
        await service.resolve_break(
            existing.id,
            resolution={
                "method": "compensating_entry",
                "evidence": "doc.pdf",
                "compensating_reference": "REF-001",
            },
            context=ctx,
            correlation_id=uuid4(),
        )
        mock_create.assert_called_once()


# --- ExecutionData dataclass ---


@pytest.mark.unit
def test_execution_data_frozen() -> None:
    data = ExecutionData(
        portfolio=MagicMock(),
        orders=[],
        fills=[],
        ledger=[],
    )
    with pytest.raises(AttributeError):
        data.portfolio = MagicMock()  # type: ignore[misc]


# --- _detect_execution_breaks delegation ---


@pytest.mark.unit
def test_detect_execution_breaks_empty() -> None:
    session = _mock_session()
    service = ReconciliationService(session)
    data = ExecutionData(
        portfolio=MagicMock(),
        orders=[],
        fills=[],
        ledger=[],
    )
    with patch(
        "ia_investing.application.paper_execution._reconciliation.reconcile_execution",
        return_value=(),
    ) as mock_reconcile:
        result = service._detect_execution_breaks(data)
        assert result == ()
        mock_reconcile.assert_called_once()


# --- _persist_break dedup ---


@pytest.mark.unit
@pytest.mark.asyncio
async def test_persist_break_dedup_existing() -> None:
    session = _mock_session()
    existing = MagicMock()
    existing.id = uuid4()
    session.scalar.return_value = existing

    service = ReconciliationService(session)
    ctx = _context()

    with patch(
        "ia_investing.application.paper_execution._reconciliation.audit_entity",
        new_callable=AsyncMock,
    ):
        result = await service._persist_break(
            portfolio_id=uuid4(),
            as_of=datetime.now(UTC),
            context=ctx,
            correlation_id=uuid4(),
            rule="fill_missing_ledger",
            resource_key="key-1",
            expected={"qty": 10},
            actual={"qty": 10},
            severity="warning",
            blocking=False,
        )

    assert result is existing
    session.add.assert_not_called()


# --- _reconcile_version_breaks ---


@pytest.mark.unit
@pytest.mark.asyncio
async def test_reconcile_version_breaks_no_version() -> None:
    session = _mock_session()
    session.scalar.return_value = None  # no latest version
    service = ReconciliationService(session)

    result = await service._reconcile_version_breaks(
        _mock_portfolio(), datetime.now(UTC), _context(), uuid4()
    )
    assert result == []
