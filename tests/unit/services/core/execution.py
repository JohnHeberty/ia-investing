"""Unit tests for ExecutionService — lifecycle, state machine, dispatch, balance."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from ia_investing.application.execution_service import (
    ExecutionService,
    InsufficientBalanceError,
)
from ia_investing.domain.base_machine import InvalidTransitionError


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
def service(mock_session: AsyncMock, mock_audit: AsyncMock) -> ExecutionService:
    return ExecutionService(mock_session, mock_audit)


def _make_execution(**overrides: object) -> MagicMock:
    e = MagicMock()
    e.id = overrides.get("id", uuid.uuid4())
    e.order_id = overrides.get("order_id", "ORD-001")
    e.portfolio_id = overrides.get("portfolio_id", uuid.uuid4())
    e.action = overrides.get("action", "buy")
    e.quantity = Decimal(str(overrides.get("quantity", 100)))
    e.price_limit = overrides.get("price_limit", None)
    e.state = overrides.get("state", "pending")
    e.available_balance = Decimal(str(overrides.get("available_balance", 0)))
    e.required_amount = Decimal(str(overrides.get("required_amount", 0)))
    e.alert_triggered = overrides.get("alert_triggered", False)
    e.filled_quantity = overrides.get("filled_quantity", None)
    e.avg_price = overrides.get("avg_price", None)
    e.reason = overrides.get("reason", None)
    e.dispatched_at = overrides.get("dispatched_at", None)
    e.confirmed_at = overrides.get("confirmed_at", None)
    e.settled_at = overrides.get("settled_at", None)
    e.created_at = overrides.get("created_at", datetime.now(UTC))
    e.updated_at = overrides.get("updated_at", datetime.now(UTC))
    return e


def _make_portfolio(**overrides: object) -> MagicMock:
    p = MagicMock()
    p.id = overrides.get("id", uuid.uuid4())
    p.organization_id = overrides.get("organization_id", uuid.uuid4())
    return p


# ---------------------------------------------------------------------------
# create_execution
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
@pytest.mark.unit
class TestCreateExecution:
    async def test_create_execution(
        self, service: ExecutionService, mock_session: AsyncMock
    ) -> None:
        portfolio_id = uuid.uuid4()
        result = await service.create_execution(
            order_id="ORD-001",
            portfolio_id=portfolio_id,
            action="buy",
            quantity=Decimal("100"),
            price_limit=Decimal("50.00"),
            actor_id=uuid.uuid4(),
        )
        assert result.order_id == "ORD-001"
        assert result.state == "pending"
        assert result.quantity == Decimal("100")
        mock_session.add.assert_called_once()
        mock_session.flush.assert_awaited()

    async def test_create_execution_sell(
        self, service: ExecutionService, mock_session: AsyncMock
    ) -> None:
        result = await service.create_execution(
            order_id="ORD-002",
            portfolio_id=uuid.uuid4(),
            action="sell",
            quantity=Decimal("50"),
        )
        assert result.action == "sell"


# ---------------------------------------------------------------------------
# validate_execution
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
@pytest.mark.unit
class TestValidateExecution:
    async def test_validate_success(
        self, service: ExecutionService, mock_session: AsyncMock
    ) -> None:
        execution = _make_execution(state="pending")
        mock_session.get.return_value = execution

        result = await service.validate_execution(
            execution.id,
            available_balance=Decimal("10000"),
            required_amount=Decimal("5000"),
            actor_id=uuid.uuid4(),
        )
        assert result.state == "validated"
        assert result.available_balance == Decimal("10000")

    async def test_validate_not_found(
        self, service: ExecutionService, mock_session: AsyncMock
    ) -> None:
        mock_session.get.return_value = None
        with pytest.raises(LookupError, match="not found"):
            await service.validate_execution(uuid.uuid4())

    async def test_validate_wrong_state_raises(
        self, service: ExecutionService, mock_session: AsyncMock
    ) -> None:
        execution = _make_execution(state="dispatched")
        mock_session.get.return_value = execution
        with pytest.raises(InvalidTransitionError):
            await service.validate_execution(execution.id)


# ---------------------------------------------------------------------------
# queue_execution
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
@pytest.mark.unit
class TestQueueExecution:
    async def test_queue_success(
        self, service: ExecutionService, mock_session: AsyncMock
    ) -> None:
        execution = _make_execution(state="validated")
        mock_session.get.return_value = execution

        result = await service.queue_execution(execution.id)
        assert result.state == "queued"

    async def test_queue_wrong_state_raises(
        self, service: ExecutionService, mock_session: AsyncMock
    ) -> None:
        execution = _make_execution(state="pending")
        mock_session.get.return_value = execution
        with pytest.raises(InvalidTransitionError):
            await service.queue_execution(execution.id)


# ---------------------------------------------------------------------------
# dispatch_execution
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
@pytest.mark.unit
class TestDispatchExecution:
    async def test_dispatch_success(
        self, service: ExecutionService, mock_session: AsyncMock
    ) -> None:
        execution = _make_execution(
            state="queued", available_balance=Decimal("10000"), required_amount=Decimal("5000")
        )
        portfolio = _make_portfolio()

        async def fake_get(model, id_val, **kwargs):
            if model.__name__ == "Execution":
                return execution
            if model.__name__ == "Portfolio":
                return portfolio
            return None

        mock_session.get = fake_get

        result = await service.dispatch_execution(execution.id, actor_id=uuid.uuid4())
        assert result.state == "dispatched"
        assert result.dispatched_at is not None

    async def test_dispatch_insufficient_balance(
        self, service: ExecutionService, mock_session: AsyncMock
    ) -> None:
        execution = _make_execution(
            state="queued", available_balance=Decimal("100"), required_amount=Decimal("5000")
        )
        mock_session.get.return_value = execution

        with pytest.raises(InsufficientBalanceError, match="Insufficient balance"):
            await service.dispatch_execution(execution.id)

    async def test_dispatch_not_found(
        self, service: ExecutionService, mock_session: AsyncMock
    ) -> None:
        mock_session.get.return_value = None
        with pytest.raises(LookupError, match="not found"):
            await service.dispatch_execution(uuid.uuid4())

    async def test_dispatch_wrong_state_raises(
        self, service: ExecutionService, mock_session: AsyncMock
    ) -> None:
        execution = _make_execution(
            state="pending", available_balance=Decimal("10000"), required_amount=Decimal("5000")
        )
        mock_session.get.return_value = execution
        with pytest.raises(InvalidTransitionError):
            await service.dispatch_execution(execution.id)

    async def test_dispatch_creates_outbox_entry(
        self, service: ExecutionService, mock_session: AsyncMock
    ) -> None:
        execution = _make_execution(
            state="queued", available_balance=Decimal("10000"), required_amount=Decimal("5000")
        )
        portfolio = _make_portfolio()

        async def fake_get(model, id_val, **kwargs):
            if model.__name__ == "Execution":
                return execution
            if model.__name__ == "Portfolio":
                return portfolio
            return None

        mock_session.get = fake_get

        result = await service.dispatch_execution(execution.id)
        # Should have added at least 1 outbox entry
        assert mock_session.add.call_count >= 1


# ---------------------------------------------------------------------------
# confirm_execution
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
@pytest.mark.unit
class TestConfirmExecution:
    async def test_confirm_success(
        self, service: ExecutionService, mock_session: AsyncMock
    ) -> None:
        execution = _make_execution(state="dispatched")
        mock_session.get.return_value = execution

        result = await service.confirm_execution(
            execution.id,
            filled_quantity=Decimal("100"),
            avg_price=Decimal("49.95"),
            actor_id=uuid.uuid4(),
        )
        assert result.state == "confirmed"
        assert result.filled_quantity == Decimal("100")
        assert result.avg_price == Decimal("49.95")
        assert result.confirmed_at is not None

    async def test_confirm_wrong_state_raises(
        self, service: ExecutionService, mock_session: AsyncMock
    ) -> None:
        execution = _make_execution(state="pending")
        mock_session.get.return_value = execution
        with pytest.raises(InvalidTransitionError):
            await service.confirm_execution(
                execution.id, filled_quantity=Decimal("100"), avg_price=Decimal("50")
            )


# ---------------------------------------------------------------------------
# fail_execution
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
@pytest.mark.unit
class TestFailExecution:
    async def test_fail_from_pending(
        self, service: ExecutionService, mock_session: AsyncMock
    ) -> None:
        execution = _make_execution(state="pending")
        mock_session.get.return_value = execution

        result = await service.fail_execution(
            execution.id, reason="Market closed", actor_id=uuid.uuid4()
        )
        assert result.state == "failed"
        assert result.reason == "Market closed"
        assert result.alert_triggered is True

    async def test_fail_from_dispatched(
        self, service: ExecutionService, mock_session: AsyncMock
    ) -> None:
        execution = _make_execution(state="dispatched")
        mock_session.get.return_value = execution

        result = await service.fail_execution(execution.id, reason="Timeout")
        assert result.state == "failed"

    async def test_fail_from_queued(
        self, service: ExecutionService, mock_session: AsyncMock
    ) -> None:
        execution = _make_execution(state="queued")
        mock_session.get.return_value = execution

        result = await service.fail_execution(execution.id, reason="Cancelled")
        assert result.state == "failed"

    async def test_fail_from_validated(
        self, service: ExecutionService, mock_session: AsyncMock
    ) -> None:
        execution = _make_execution(state="validated")
        mock_session.get.return_value = execution

        result = await service.fail_execution(execution.id, reason="Rejected")
        assert result.state == "failed"

    async def test_fail_from_confirmed(
        self, service: ExecutionService, mock_session: AsyncMock
    ) -> None:
        execution = _make_execution(state="confirmed")
        mock_session.get.return_value = execution

        result = await service.fail_execution(execution.id, reason="Post-trade error")
        assert result.state == "failed"


# ---------------------------------------------------------------------------
# settle_execution
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
@pytest.mark.unit
class TestSettleExecution:
    async def test_settle_success(
        self, service: ExecutionService, mock_session: AsyncMock
    ) -> None:
        execution = _make_execution(state="confirmed")
        mock_session.get.return_value = execution

        result = await service.settle_execution(execution.id, actor_id=uuid.uuid4())
        assert result.state == "settled"
        assert result.settled_at is not None

    async def test_settle_already_settled_idempotent(
        self, service: ExecutionService, mock_session: AsyncMock
    ) -> None:
        execution = _make_execution(state="settled")
        mock_session.get.return_value = execution

        result = await service.settle_execution(execution.id)
        assert result.state == "settled"

    async def test_settle_wrong_state_raises(
        self, service: ExecutionService, mock_session: AsyncMock
    ) -> None:
        execution = _make_execution(state="dispatched")
        mock_session.get.return_value = execution
        with pytest.raises(InvalidTransitionError):
            await service.settle_execution(execution.id)

    async def test_settle_not_found(
        self, service: ExecutionService, mock_session: AsyncMock
    ) -> None:
        mock_session.get.return_value = None
        with pytest.raises(LookupError, match="not found"):
            await service.settle_execution(uuid.uuid4())


# ---------------------------------------------------------------------------
# get_execution
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
@pytest.mark.unit
class TestGetExecution:
    async def test_get_execution_success(
        self, service: ExecutionService, mock_session: AsyncMock
    ) -> None:
        execution = _make_execution(state="pending")
        mock_session.get.return_value = execution

        result = await service.get_execution(execution.id)
        assert result["state"] == "pending"
        assert result["order_id"] == "ORD-001"
        assert "allowed_transitions" in result
        assert "state_history" in result

    async def test_get_execution_not_found(
        self, service: ExecutionService, mock_session: AsyncMock
    ) -> None:
        mock_session.get.return_value = None
        with pytest.raises(LookupError, match="not found"):
            await service.get_execution(uuid.uuid4())


# ---------------------------------------------------------------------------
# list_executions
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
@pytest.mark.unit
class TestListExecutions:
    async def test_list_empty(self, service: ExecutionService, mock_session: AsyncMock) -> None:
        mock_session.scalar.return_value = 0
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        executions, total = await service.list_executions()
        assert total == 0
        assert executions == []

    async def test_list_with_filters(
        self, service: ExecutionService, mock_session: AsyncMock
    ) -> None:
        mock_session.scalar.return_value = 2
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [
            _make_execution(state="confirmed"),
            _make_execution(state="settled"),
        ]
        mock_session.execute.return_value = mock_result

        executions, total = await service.list_executions(
            portfolio_id=uuid.uuid4(),
            state="confirmed",
            from_date=datetime(2026, 1, 1, tzinfo=UTC),
            to_date=datetime(2026, 12, 31, tzinfo=UTC),
            limit=10,
            offset=0,
        )
        assert total == 2
        assert len(executions) == 2


# ---------------------------------------------------------------------------
# State machine full lifecycle
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
@pytest.mark.unit
class TestFullLifecycle:
    async def test_pending_to_settled(
        self, service: ExecutionService, mock_session: AsyncMock
    ) -> None:
        execution = _make_execution(state="pending")
        mock_session.get.return_value = execution

        result = await service.validate_execution(
            execution.id, available_balance=Decimal("20000"), required_amount=Decimal("5000")
        )
        assert result.state == "validated"

        mock_session.get.return_value = execution
        result = await service.queue_execution(execution.id)
        assert result.state == "queued"

        portfolio = _make_portfolio()

        async def fake_get(model, id_val, **kwargs):
            if model.__name__ == "Execution":
                return execution
            if model.__name__ == "Portfolio":
                return portfolio
            return None

        mock_session.get = fake_get
        result = await service.dispatch_execution(execution.id)
        assert result.state == "dispatched"

        mock_session.get.return_value = execution
        result = await service.confirm_execution(
            execution.id, filled_quantity=Decimal("100"), avg_price=Decimal("49.95")
        )
        assert result.state == "confirmed"

        mock_session.get.return_value = execution
        result = await service.settle_execution(execution.id)
        assert result.state == "settled"

    async def test_pending_to_failed_to_retry(
        self, service: ExecutionService, mock_session: AsyncMock
    ) -> None:
        execution = _make_execution(state="pending")
        mock_session.get.return_value = execution

        result = await service.fail_execution(execution.id, reason="Error")
        assert result.state == "failed"
        assert execution.alert_triggered is True

        # retry goes from failed to pending
        mock_session.get.return_value = execution
        result = await service._transition(execution.id, "retry")
        assert result.state == "pending"


# ---------------------------------------------------------------------------
# _transition error paths
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
@pytest.mark.unit
class TestTransitionErrors:
    async def test_transition_not_found(
        self, service: ExecutionService, mock_session: AsyncMock
    ) -> None:
        mock_session.get.return_value = None
        with pytest.raises(LookupError, match="not found"):
            await service._transition(uuid.uuid4(), "run_validation")

    async def test_transition_invalid_trigger(
        self, service: ExecutionService, mock_session: AsyncMock
    ) -> None:
        execution = _make_execution(state="pending")
        mock_session.get.return_value = execution
        with pytest.raises(InvalidTransitionError):
            await service._transition(execution.id, "nonexistent_trigger")
