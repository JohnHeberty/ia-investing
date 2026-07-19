from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from ia_investing.orchestration.policies import DEFAULT_ACTIVITY_RETRY_POLICY, EXTERNAL_IO_RETRY_POLICY


@dataclass(slots=True)
class RunAgentInput:
    operation_id: str
    agent_name: str
    input_data: dict[str, Any]


@workflow.defn
class RunAgentWorkflow:
    @workflow.run
    async def run(self, command: RunAgentInput) -> dict[str, Any]:
        await workflow.execute_activity(
            "set_operation_running",
            command.operation_id,
            start_to_close_timeout=timedelta(seconds=15),
            retry_policy=DEFAULT_ACTIVITY_RETRY_POLICY,
        )
        try:
            result = await workflow.execute_activity(
                "run_configured_agent",
                args=[command.agent_name, command.input_data],
                start_to_close_timeout=timedelta(minutes=5),
                retry_policy=EXTERNAL_IO_RETRY_POLICY,
            )
        except Exception as exc:
            await workflow.execute_activity(
                "fail_operation",
                args=[command.operation_id, type(exc).__name__],
                start_to_close_timeout=timedelta(seconds=15),
                retry_policy=DEFAULT_ACTIVITY_RETRY_POLICY,
            )
            raise
        await workflow.execute_activity(
            "complete_operation",
            args=[command.operation_id, result],
            start_to_close_timeout=timedelta(seconds=15),
            retry_policy=DEFAULT_ACTIVITY_RETRY_POLICY,
        )
        return result
