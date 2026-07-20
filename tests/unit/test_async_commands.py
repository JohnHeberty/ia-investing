from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from ia_investing.application.operations import (
    IdempotencyConflictError,
    OperationService,
    PortfolioOperationCommand,
    _request_hash,
)
from ia_investing.contracts.v1 import OperationAcceptedV1, OperationState, OperationStatusV1


def _make_operation(
    operation_id: UUID | None = None,
    operation_type: str = "portfolio-optimization",
    state: OperationState = OperationState.PENDING,
    idempotency_key: str = "test-key-123",
    request_hash: str = "abc123",
) -> MagicMock:
    op = MagicMock()
    op.id = operation_id or uuid4()
    op.operation_type = operation_type
    op.state = state
    op.idempotency_key = idempotency_key
    op.request_hash = request_hash
    op.created_at = datetime.now(UTC)
    op.updated_at = datetime.now(UTC)
    op.result_url = None
    op.error_code = None
    op.error_detail = None
    op.request_data = {}
    return op


class TestPortfolioOperationCommand:
    def test_frozen_dataclass(self) -> None:
        cmd = PortfolioOperationCommand(
            operation_type="backtest",
            payload={"key": "value"},
            actor_subject="user@test.com",
        )
        assert cmd.operation_type == "backtest"
        assert cmd.payload == {"key": "value"}
        assert cmd.actor_subject == "user@test.com"
        assert cmd.workflow_class is None
        assert cmd.workflow_id is None

    def test_defaults(self) -> None:
        cmd = PortfolioOperationCommand(
            operation_type="risk-assessment",
            payload={},
            actor_subject="user@test.com",
        )
        assert cmd.task_queue.value == "portfolio-risk"


class TestRequestHash:
    def test_deterministic(self) -> None:
        payload = {"key": "value", "num": 42}
        h1 = _request_hash(payload)
        h2 = _request_hash(payload)
        assert h1 == h2

    def test_different_payloads_different_hashes(self) -> None:
        h1 = _request_hash({"a": 1})
        h2 = _request_hash({"b": 2})
        assert h1 != h2

    def test_sort_keys(self) -> None:
        h1 = _request_hash({"b": 2, "a": 1})
        h2 = _request_hash({"a": 1, "b": 2})
        assert h1 == h2

    def test_sha256_format(self) -> None:
        h = _request_hash({"x": 1})
        assert len(h) == 64
        hashlib.sha256(b"test").hexdigest()  # no error


class TestSubmitPortfolioOperation:
    @pytest.fixture
    def mock_session(self) -> MagicMock:
        session = AsyncMock()
        session.execute = AsyncMock()
        session.commit = AsyncMock()
        session.add = MagicMock()
        return session

    @pytest.fixture
    def mock_temporal(self) -> MagicMock:
        client = AsyncMock()
        client.start_workflow = AsyncMock()
        return client

    @pytest.fixture
    def service(self, mock_session: MagicMock, mock_temporal: MagicMock) -> OperationService:
        return OperationService(mock_session, mock_temporal)

    @pytest.mark.asyncio
    async def test_new_operation_created(self, service: OperationService, mock_session: MagicMock) -> None:
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        cmd = PortfolioOperationCommand(
            operation_type="portfolio-optimization",
            payload={"portfolio_id": "abc", "as_of": "2025-01-01T00:00:00Z"},
            actor_subject="user@test.com",
        )
        result = await service.submit_portfolio_operation(cmd, "idem-key-001", "user@test.com")

        assert isinstance(result, OperationAcceptedV1)
        assert result.state == OperationState.PENDING
        assert mock_session.add.call_count == 2  # Operation + AuditLog
        assert mock_session.commit.call_count == 1

    @pytest.mark.asyncio
    async def test_existing_idempotent_returns_existing(
        self, service: OperationService, mock_session: MagicMock
    ) -> None:
        existing_op = _make_operation(state=OperationState.RUNNING)
        payload = {"portfolio_id": "abc", "as_of": "2025-01-01T00:00:00Z"}
        request_hash = _request_hash(payload)
        existing_op.request_hash = request_hash

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_op
        mock_session.execute.return_value = mock_result

        cmd = PortfolioOperationCommand(
            operation_type="portfolio-optimization",
            payload=payload,
            actor_subject="user@test.com",
        )
        result = await service.submit_portfolio_operation(cmd, "idem-key-001", "user@test.com")

        assert result.operation_id == existing_op.id
        assert result.state == OperationState.RUNNING

    @pytest.mark.asyncio
    async def test_idempotency_conflict_on_different_hash(
        self, service: OperationService, mock_session: MagicMock
    ) -> None:
        existing_op = _make_operation(request_hash="different-hash-value")
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_op
        mock_session.execute.return_value = mock_result

        cmd = PortfolioOperationCommand(
            operation_type="portfolio-optimization",
            payload={"portfolio_id": "abc"},
            actor_subject="user@test.com",
        )
        with pytest.raises(IdempotencyConflictError):
            await service.submit_portfolio_operation(cmd, "idem-key-001", "user@test.com")

    @pytest.mark.asyncio
    async def test_workflow_started_when_provided(
        self, service: OperationService, mock_session: MagicMock, mock_temporal: MagicMock
    ) -> None:
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        workflow_cls = MagicMock()
        workflow_cls.run = MagicMock()
        cmd = PortfolioOperationCommand(
            operation_type="portfolio-optimization",
            payload={"portfolio_id": "abc"},
            actor_subject="user@test.com",
            workflow_id="wf-123",
            workflow_class=workflow_cls,
            workflow_input={"input": "data"},
        )
        result = await service.submit_portfolio_operation(cmd, "idem-key-001", "user@test.com")

        assert isinstance(result, OperationAcceptedV1)
        mock_temporal.start_workflow.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_workflow_failure_marks_failed(
        self, service: OperationService, mock_session: MagicMock, mock_temporal: MagicMock
    ) -> None:
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result
        mock_temporal.start_workflow.side_effect = RuntimeError("temporal unavailable")

        workflow_cls = MagicMock()
        workflow_cls.run = MagicMock()
        cmd = PortfolioOperationCommand(
            operation_type="portfolio-optimization",
            payload={"portfolio_id": "abc"},
            actor_subject="user@test.com",
            workflow_id="wf-123",
            workflow_class=workflow_cls,
            workflow_input={"input": "data"},
        )
        with pytest.raises(RuntimeError, match="temporal unavailable"):
            await service.submit_portfolio_operation(cmd, "idem-key-001", "user@test.com")

        assert mock_session.commit.call_count == 2  # create + mark failed

    @pytest.mark.asyncio
    async def test_no_workflow_skips_temporal(
        self, service: OperationService, mock_session: MagicMock, mock_temporal: MagicMock
    ) -> None:
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        cmd = PortfolioOperationCommand(
            operation_type="backtest",
            payload={"start_date": "2024-01-01"},
            actor_subject="user@test.com",
        )
        result = await service.submit_portfolio_operation(cmd, "idem-key-002", "user@test.com")

        assert isinstance(result, OperationAcceptedV1)
        mock_temporal.start_workflow.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_operation_types(self, service: OperationService, mock_session: MagicMock) -> None:
        for op_type in ("portfolio-optimization", "risk-assessment", "backtest"):
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = None
            mock_session.execute.return_value = mock_result

            cmd = PortfolioOperationCommand(
                operation_type=op_type,
                payload={"data": 1},
                actor_subject="user@test.com",
            )
            result = await service.submit_portfolio_operation(cmd, f"idem-{op_type}", "user@test.com")
            assert isinstance(result, OperationAcceptedV1)


class TestAsyncCommandSchemas:
    def test_operation_accepted_v1(self) -> None:
        op_id = uuid4()
        result = OperationAcceptedV1(operation_id=op_id)
        assert result.schema_version == "1.0"
        assert result.state == OperationState.PENDING
        assert result.operation_id == op_id

    def test_operation_status_v1(self) -> None:
        op_id = uuid4()
        now = datetime.now(UTC)
        result = OperationStatusV1(
            operation_id=op_id,
            state=OperationState.SUCCEEDED,
            created_at=now,
            updated_at=now,
        )
        assert result.result_url is None
        assert result.error_code is None
        assert result.metadata == {}

    def test_operation_states(self) -> None:
        assert OperationState.PENDING.value == "pending"
        assert OperationState.RUNNING.value == "running"
        assert OperationState.SUCCEEDED.value == "succeeded"
        assert OperationState.FAILED.value == "failed"
        assert OperationState.CANCELLED.value == "cancelled"
