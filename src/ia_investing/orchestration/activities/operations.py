from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import update
from temporalio import activity
from temporalio.exceptions import ApplicationError

from database.core import session_scope
from database.models.operations import Operation
from ia_investing.ai import ALL_AGENTS


async def _set_state(operation_id: str, **values: Any) -> None:
    try:
        operation_uuid = UUID(operation_id)
    except ValueError as exc:
        raise ApplicationError("invalid operation ID", type="DataValidationError", non_retryable=True) from exc
    values["updated_at"] = datetime.now(UTC)
    async with session_scope() as session:
        result = await session.execute(update(Operation).where(Operation.id == operation_uuid).values(**values))
        if result.rowcount != 1:
            raise ApplicationError("operation not found", type="DataValidationError", non_retryable=True)


@activity.defn(name="set_operation_running")
async def set_operation_running(operation_id: str) -> None:
    await _set_state(operation_id, state="running")


@activity.defn(name="run_configured_agent")
def run_configured_agent(agent_name: str, input_data: dict[str, Any]) -> dict[str, Any]:
    if agent_name not in ALL_AGENTS:
        raise ApplicationError("unknown agent", type="DataValidationError", non_retryable=True)
    run_id = str(uuid5(NAMESPACE_URL, f"ia-investing/mock/{agent_name}/{input_data!r}"))
    return {
        "agent_run_id": run_id,
        "agent_name": agent_name,
        "provider": "mock",
        "output": {"status": "mocked", "input_keys": sorted(input_data)},
    }


@activity.defn(name="complete_operation")
async def complete_operation(operation_id: str, result: dict[str, Any]) -> None:
    await _set_state(
        operation_id,
        state="succeeded",
        result_data=result,
        result_url=f"/api/v1/agent-runs/{result['agent_run_id']}",
        error_code=None,
        error_detail=None,
    )


@activity.defn(name="fail_operation")
async def fail_operation(operation_id: str, error_code: str) -> None:
    await _set_state(
        operation_id,
        state="failed",
        error_code=error_code[:100],
        error_detail="Agent execution failed. Inspect correlated traces for details.",
    )


OPERATION_ACTIVITIES = (
    set_operation_running,
    run_configured_agent,
    complete_operation,
    fail_operation,
)
