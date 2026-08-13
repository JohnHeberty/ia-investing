from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from temporalio.exceptions import ApplicationError

from ia_investing.orchestration.activities.operations import (
    OPERATION_ACTIVITIES,
    _set_state,
    cancel_operation,
    complete_operation,
    fail_operation,
    set_operation_running,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
VALID_ID = "12345678-1234-5678-1234-567812345678"


@pytest.fixture()
def mock_session():
    session = AsyncMock()
    result = MagicMock()
    result.rowcount = 1
    session.execute.return_value = result
    return session


# ---------------------------------------------------------------------------
# Tests: _set_state
# ---------------------------------------------------------------------------
@pytest.mark.unit
class TestSetState:
    @pytest.mark.asyncio
    @patch("ia_investing.orchestration.activities.operations.session_scope")
    async def test_set_state_with_provided_session(self, mock_session_scope, mock_session):
        await _set_state(VALID_ID, session=mock_session, state="running")

        mock_session.execute.assert_awaited_once()
        call_args = mock_session.execute.call_args
        assert call_args[0][0].whereclause is not None

    @pytest.mark.asyncio
    @patch("ia_investing.orchestration.activities.operations.session_scope")
    async def test_set_state_creates_session_when_none(self, mock_session_scope, mock_session):
        ctx = AsyncMock()
        ctx.__aenter__ = AsyncMock(return_value=mock_session)
        ctx.__aexit__ = AsyncMock(return_value=False)
        mock_session_scope.return_value = ctx

        await _set_state(VALID_ID, state="running")

        mock_session_scope.assert_called_once()
        mock_session.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_set_state_invalid_uuid_raises(self, mock_session):
        with pytest.raises(ApplicationError, match="invalid operation ID") as exc_info:
            await _set_state("not-a-uuid", session=mock_session)
        assert exc_info.value.non_retryable is True

    @pytest.mark.asyncio
    async def test_set_state_rowcount_zero_raises(self, mock_session):
        mock_session.execute.return_value = MagicMock(rowcount=0)
        with pytest.raises(ApplicationError, match="operation not found"):
            await _set_state(VALID_ID, session=mock_session)


# ---------------------------------------------------------------------------
# Tests: activity functions
# ---------------------------------------------------------------------------
@pytest.mark.unit
class TestActivityFunctions:
    @pytest.mark.asyncio
    @patch("ia_investing.orchestration.activities.operations._set_state")
    async def test_set_operation_running(self, mock_set_state):
        mock_set_state.return_value = None
        await set_operation_running(VALID_ID)
        mock_set_state.assert_awaited_once_with(VALID_ID, state="running")

    @pytest.mark.asyncio
    @patch("ia_investing.orchestration.activities.operations._set_state")
    async def test_complete_operation(self, mock_set_state):
        mock_set_state.return_value = None
        result = {"agent_run_id": "run-123"}
        await complete_operation(VALID_ID, result)
        mock_set_state.assert_awaited_once_with(
            VALID_ID,
            state="succeeded",
            result_data=result,
            result_url="/api/v1/agent-runs/run-123",
            error_code=None,
            error_detail=None,
        )

    @pytest.mark.asyncio
    @patch("ia_investing.orchestration.activities.operations._set_state")
    async def test_fail_operation(self, mock_set_state):
        mock_set_state.return_value = None
        await fail_operation(VALID_ID, "TIMEOUT_ERROR")
        mock_set_state.assert_awaited_once_with(
            VALID_ID,
            state="failed",
            error_code="TIMEOUT_ERROR",
            error_detail="Agent execution failed. Inspect correlated traces for details.",
        )

    @pytest.mark.asyncio
    @patch("ia_investing.orchestration.activities.operations._set_state")
    async def test_fail_operation_truncates_error_code(self, mock_set_state):
        mock_set_state.return_value = None
        long_code = "X" * 200
        await fail_operation(VALID_ID, long_code)
        call_kwargs = mock_set_state.call_args[1]
        assert len(call_kwargs["error_code"]) == 100

    @pytest.mark.asyncio
    @patch("ia_investing.orchestration.activities.operations._set_state")
    async def test_cancel_operation_default_reason(self, mock_set_state):
        mock_set_state.return_value = None
        await cancel_operation(VALID_ID)
        mock_set_state.assert_awaited_once_with(
            VALID_ID,
            state="cancelled",
            error_code="workflow_cancelled",
            error_detail="cancelled",
        )

    @pytest.mark.asyncio
    @patch("ia_investing.orchestration.activities.operations._set_state")
    async def test_cancel_operation_custom_reason(self, mock_set_state):
        mock_set_state.return_value = None
        await cancel_operation(VALID_ID, reason="user requested stop")
        mock_set_state.assert_awaited_once_with(
            VALID_ID,
            state="cancelled",
            error_code="workflow_cancelled",
            error_detail="user requested stop",
        )

    @pytest.mark.asyncio
    @patch("ia_investing.orchestration.activities.operations._set_state")
    async def test_cancel_operation_truncates_reason(self, mock_set_state):
        mock_set_state.return_value = None
        long_reason = "R" * 300
        await cancel_operation(VALID_ID, reason=long_reason)
        call_kwargs = mock_set_state.call_args[1]
        assert len(call_kwargs["error_detail"]) == 200


# ---------------------------------------------------------------------------
# Tests: OPERATION_ACTIVITIES tuple
# ---------------------------------------------------------------------------
@pytest.mark.unit
class TestOperationActivitiesTuple:
    def test_tuple_contains_all_four(self):
        assert len(OPERATION_ACTIVITIES) == 4
        names = {fn.__name__ for fn in OPERATION_ACTIVITIES}
        assert names == {"set_operation_running", "complete_operation", "fail_operation", "cancel_operation"}
