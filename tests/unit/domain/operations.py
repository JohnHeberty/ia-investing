"""Unit tests for ia_investing.application.operations — OperationService."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from ia_investing.application.operations import (
    AgentRunCommand,
    IdempotencyConflictError,
    OperationService,
    PortfolioOperationCommand,
    _request_hash,
)
from ia_investing.contracts.v1 import OperationState


@pytest.mark.unit
class TestRequestHash:
    def test_deterministic(self):
        h1 = _request_hash({"a": 1, "b": 2})
        h2 = _request_hash({"b": 2, "a": 1})
        assert h1 == h2

    def test_different_payloads(self):
        h1 = _request_hash({"a": 1})
        h2 = _request_hash({"a": 2})
        assert h1 != h2

    def test_is_hex_64(self):
        h = _request_hash({})
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)


@pytest.mark.unit
class TestAgentRunCommand:
    def test_payload(self):
        cmd = AgentRunCommand(agent_name="test", input_data={"k": "v"}, actor_subject="u1")
        p = cmd.payload()
        assert p["agent_name"] == "test"
        assert p["input_data"] == {"k": "v"}


@pytest.mark.unit
class TestOperationService:
    @pytest.mark.asyncio
    async def test_get_not_found(self):
        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=None)
        svc = OperationService(mock_session, AsyncMock())
        result = await svc.get(uuid4())
        assert result is None

    @pytest.mark.asyncio
    async def test_get_found(self):
        mock_session = AsyncMock()
        now = datetime.now(UTC)
        op = SimpleNamespace(
            id=uuid4(), state=OperationState.PENDING,
            created_at=now, updated_at=now,
            result_url=None, error_code=None, error_detail=None,
        )
        mock_session.get = AsyncMock(return_value=op)
        svc = OperationService(mock_session, AsyncMock())
        result = await svc.get(op.id)
        assert result is not None
        assert result.operation_id == op.id

    @pytest.mark.asyncio
    async def test_submit_agent_run_existing_idempotent(self):
        mock_session = AsyncMock()
        op_id = uuid4()
        req_data = {"capability": "test", "input_payload": {}, "data_as_of": "", "knowledge_cutoff": "", "case_id": None, "requested_by": "u1"}
        rh = _request_hash(req_data)
        existing = SimpleNamespace(id=op_id, request_hash=rh, state=OperationState.PENDING)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing
        mock_session.execute = AsyncMock(return_value=mock_result)

        svc = OperationService(mock_session, AsyncMock())
        cmd = AgentRunCommand(agent_name="test", input_data={}, actor_subject="u1")
        result = await svc.submit_agent_run(cmd, "idem-key")
        assert result.operation_id == op_id

    @pytest.mark.asyncio
    async def test_submit_agent_run_conflict(self):
        mock_session = AsyncMock()
        existing = SimpleNamespace(id=uuid4(), request_hash="different_hash", state=OperationState.PENDING)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing
        mock_session.execute = AsyncMock(return_value=mock_result)

        svc = OperationService(mock_session, AsyncMock())
        cmd = AgentRunCommand(agent_name="test", input_data={}, actor_subject="u1")
        with pytest.raises(IdempotencyConflictError):
            await svc.submit_agent_run(cmd, "idem-key")

    @pytest.mark.asyncio
    async def test_submit_agent_run_new(self):
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.commit = AsyncMock()

        with patch("ia_investing.application.operations.create_domain_audit_entry", new_callable=AsyncMock):
            svc = OperationService(mock_session, AsyncMock())
            cmd = AgentRunCommand(agent_name="test", input_data={"k": "v"}, actor_subject="u1")
            result = await svc.submit_agent_run(cmd, "idem-key")
            assert result.operation_id is not None

    @pytest.mark.asyncio
    async def test_submit_agent_run_integrity_error_race(self):
        mock_session = AsyncMock()
        op_id = uuid4()
        # Both calls return None (no existing)
        mock_result_none = MagicMock()
        mock_result_none.scalar_one_or_none.return_value = None

        mock_session.execute = AsyncMock(return_value=mock_result_none)
        mock_session.commit = AsyncMock(side_effect=IntegrityError("dup", {}, Exception()))
        mock_session.rollback = AsyncMock()

        with patch("ia_investing.application.operations.create_domain_audit_entry", new_callable=AsyncMock):
            svc = OperationService(mock_session, AsyncMock())
            cmd = AgentRunCommand(agent_name="test", input_data={}, actor_subject="u1")
            # Should re-raise IntegrityError since no existing found after rollback
            with pytest.raises(IntegrityError):
                await svc.submit_agent_run(cmd, "idem-key")

    @pytest.mark.asyncio
    async def test_submit_portfolio_operation_new(self):
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.commit = AsyncMock()

        with patch("ia_investing.application.operations.create_domain_audit_entry", new_callable=AsyncMock):
            svc = OperationService(mock_session, AsyncMock())
            cmd = PortfolioOperationCommand(operation_type="rebalance", payload={"a": 1}, actor_subject="u1")
            result = await svc.submit_portfolio_operation(cmd, "idem-key", "u1")
            assert result.operation_id is not None

    @pytest.mark.asyncio
    async def test_submit_portfolio_operation_existing(self):
        mock_session = AsyncMock()
        op_id = uuid4()
        rh = _request_hash({"a": 1})
        existing = SimpleNamespace(id=op_id, request_hash=rh, state=OperationState.PENDING)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing
        mock_session.execute = AsyncMock(return_value=mock_result)

        svc = OperationService(mock_session, AsyncMock())
        cmd = PortfolioOperationCommand(operation_type="rebalance", payload={"a": 1}, actor_subject="u1")
        result = await svc.submit_portfolio_operation(cmd, "idem-key", "u1")
        assert result.operation_id == op_id

    @pytest.mark.asyncio
    async def test_submit_portfolio_operation_conflict(self):
        mock_session = AsyncMock()
        existing = SimpleNamespace(id=uuid4(), request_hash="diff", state=OperationState.PENDING)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing
        mock_session.execute = AsyncMock(return_value=mock_result)

        svc = OperationService(mock_session, AsyncMock())
        cmd = PortfolioOperationCommand(operation_type="rebalance", payload={"a": 1}, actor_subject="u1")
        with pytest.raises(IdempotencyConflictError):
            await svc.submit_portfolio_operation(cmd, "idem-key", "u1")

    @pytest.mark.asyncio
    async def test_submit_portfolio_operation_with_workflow(self):
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.commit = AsyncMock()
        mock_session.merge = AsyncMock(return_value=SimpleNamespace(state=OperationState.PENDING))

        mock_temporal = AsyncMock()

        with patch("ia_investing.application.operations.create_domain_audit_entry", new_callable=AsyncMock):
            svc = OperationService(mock_session, mock_temporal)
            cmd = PortfolioOperationCommand(
                operation_type="rebalance", payload={"a": 1}, actor_subject="u1",
                workflow_id="wf-1", workflow_class=MagicMock(), workflow_input={},
            )
            result = await svc.submit_portfolio_operation(cmd, "idem-key", "u1")
            assert result.operation_id is not None
            mock_temporal.start_workflow.assert_called_once()
