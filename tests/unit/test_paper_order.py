"""Tests for ia_investing.application.paper_execution._order — order simulation."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from ia_investing.application.paper_execution._order import OrderService
from ia_investing.domain.identity import InstitutionalAccessContext


def _context(org_id: UUID | None = None) -> InstitutionalAccessContext:
    org = org_id or uuid4()
    return InstitutionalAccessContext(
        "ops_user", org, frozenset({uuid4()}),
        frozenset({"paper_orders:operate", "reconciliation:write"}), "paper"
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


def _make_intent(
    *,
    org_id: UUID | None = None,
    status: str = "approved",
    side: str = "buy",
    quantity: Decimal = Decimal("100"),
) -> MagicMock:
    intent = MagicMock()
    intent.id = uuid4()
    intent.organization_id = org_id or uuid4()
    intent.portfolio_id = uuid4()
    intent.portfolio_version_id = uuid4()
    intent.instrument_id = uuid4()
    intent.status = status
    intent.side = side
    intent.quantity = quantity
    intent.limit_price = None
    intent.order_type = "market"
    intent.earliest_execution_at = datetime(2026, 1, 5, tzinfo=UTC)
    intent.expires_at = datetime(2026, 1, 10, tzinfo=UTC)
    intent.approved_by = "pm@test.com"
    intent.approval_decision = {"decided_at": "2026-01-04T10:00:00+00:00"}
    intent.updated_at = datetime(2026, 1, 4, tzinfo=UTC)
    return intent


def _make_model(org_id: UUID | None = None) -> MagicMock:
    model = MagicMock()
    model.id = uuid4()
    model.organization_id = org_id or uuid4()
    model.status = "approved"
    model.logical_id = "model-1"
    model.version = 1
    model.configuration = {
        "lot_size": 1,
        "max_participation": "0.1",
        "spread_bps": "5",
        "impact_bps_at_full_participation": "20",
        "fee_bps": "10",
        "tax_bps": "15",
        "latency_ms": 100,
    }
    return model


# --- Validation errors ---


@pytest.mark.unit
@pytest.mark.asyncio
async def test_simulate_intent_not_found() -> None:
    session = _mock_session()
    session.get.return_value = None
    service = OrderService(session)
    with pytest.raises(LookupError, match="not found"):
        await service.simulate(
            uuid4(),
            execution_model_version_id=uuid4(),
            seed=42,
            context=_context(),
            correlation_id=uuid4(),
        )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_simulate_org_mismatch() -> None:
    session = _mock_session()
    ctx = _context()
    intent = _make_intent(org_id=uuid4())  # different org
    session.get.return_value = intent
    service = OrderService(session)
    with pytest.raises(LookupError, match="not found"):
        await service.simulate(
            intent.id,
            execution_model_version_id=uuid4(),
            seed=42,
            context=ctx,
            correlation_id=uuid4(),
        )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_simulate_not_approved() -> None:
    session = _mock_session()
    ctx = _context()
    intent = _make_intent(org_id=ctx.organization_id, status="pending_approval")
    session.get.return_value = intent
    service = OrderService(session)
    with pytest.raises(ValueError, match="only an approved"):
        await service.simulate(
            intent.id,
            execution_model_version_id=uuid4(),
            seed=42,
            context=ctx,
            correlation_id=uuid4(),
        )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_simulate_no_approved_by() -> None:
    session = _mock_session()
    ctx = _context()
    intent = _make_intent(org_id=ctx.organization_id, status="approved")
    intent.approved_by = None
    session.get.return_value = intent
    service = OrderService(session)
    with pytest.raises(ValueError, match="only an approved"):
        await service.simulate(
            intent.id,
            execution_model_version_id=uuid4(),
            seed=42,
            context=ctx,
            correlation_id=uuid4(),
        )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_simulate_portfolio_not_found() -> None:
    session = _mock_session()
    ctx = _context()
    intent = _make_intent(org_id=ctx.organization_id)

    call_count = 0
    async def _get(model, oid, with_for_update=None):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return intent  # TradeIntent
        return None  # ModelPortfolio

    session.get = AsyncMock(side_effect=_get)
    service = OrderService(session)
    with pytest.raises(LookupError, match="portfolio not found"):
        await service.simulate(
            intent.id,
            execution_model_version_id=uuid4(),
            seed=42,
            context=ctx,
            correlation_id=uuid4(),
        )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_simulate_model_not_found() -> None:
    session = _mock_session()
    ctx = _context()
    intent = _make_intent(org_id=ctx.organization_id)
    portfolio = MagicMock()
    portfolio.id = intent.portfolio_id
    portfolio.organization_id = ctx.organization_id

    call_count = 0
    async def _get(model, oid, with_for_update=None):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return intent
        if call_count == 2:
            return portfolio
        return None

    session.get = AsyncMock(side_effect=_get)
    service = OrderService(session)
    with pytest.raises(ValueError, match="execution model version"):
        await service.simulate(
            intent.id,
            execution_model_version_id=uuid4(),
            seed=42,
            context=ctx,
            correlation_id=uuid4(),
        )


# --- Idempotency ---


@pytest.mark.unit
@pytest.mark.asyncio
async def test_simulate_idempotent_existing_order() -> None:
    session = _mock_session()
    ctx = _context()
    intent = _make_intent(org_id=ctx.organization_id)
    portfolio = MagicMock()
    portfolio.id = intent.portfolio_id
    portfolio.organization_id = ctx.organization_id
    model = _make_model(ctx.organization_id)

    existing_order = MagicMock()
    existing_order.id = uuid4()
    existing_order.submit_key = f"paper-intent:{intent.id}:model:{model.id}"

    fill1 = MagicMock()
    fill1.sequence = 1

    call_count = 0
    async def _get(model_cls, oid, with_for_update=None):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return intent
        if call_count == 2:
            return portfolio
        if call_count == 3:
            return model
        return None

    session.get = AsyncMock(side_effect=_get)

    exec_result = MagicMock()
    exec_result.scalar_one_or_none.return_value = existing_order
    session.execute = AsyncMock(return_value=exec_result)

    fill_result = MagicMock()
    fill_result.all.return_value = [fill1]
    session.scalars = AsyncMock(return_value=fill_result)

    service = OrderService(session)
    order, fills = await service.simulate(
        intent.id,
        execution_model_version_id=model.id,
        seed=42,
        context=ctx,
        correlation_id=uuid4(),
    )
    assert order is existing_order
    assert len(fills) == 1


# --- get_order_with_intent ---


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_order_with_intent_order_not_found() -> None:
    session = _mock_session()
    session.get.return_value = None
    service = OrderService(session)
    result = await service.get_order_with_intent(uuid4(), uuid4())
    assert result is None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_order_with_intent_org_mismatch() -> None:
    session = _mock_session()
    order = MagicMock()
    order.trade_intent_id = uuid4()
    intent = MagicMock()
    intent.organization_id = uuid4()

    call_count = 0
    async def _get(model, oid, with_for_update=None):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return order
        return intent

    session.get = AsyncMock(side_effect=_get)
    service = OrderService(session)
    result = await service.get_order_with_intent(order.id, uuid4())
    assert result is None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_order_with_intent_success() -> None:
    session = _mock_session()
    org_id = uuid4()
    order = MagicMock()
    order.trade_intent_id = uuid4()
    intent = MagicMock()
    intent.organization_id = org_id

    call_count = 0
    async def _get(model, oid, with_for_update=None):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return order
        return intent

    session.get = AsyncMock(side_effect=_get)
    service = OrderService(session)
    result = await service.get_order_with_intent(order.id, org_id)
    assert result == (order, intent)


# --- list_fills_for_order ---


@pytest.mark.unit
@pytest.mark.asyncio
async def test_list_fills_for_order() -> None:
    session = _mock_session()
    fill1 = MagicMock()
    fill1.sequence = 1
    fill2 = MagicMock()
    fill2.sequence = 2
    result = MagicMock()
    result.all.return_value = [fill1, fill2]
    session.scalars = AsyncMock(return_value=result)
    service = OrderService(session)
    fills = await service.list_fills_for_order(uuid4())
    assert len(fills) == 2
