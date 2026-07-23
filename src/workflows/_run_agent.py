"""Durable governed agent execution workflow."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import timedelta
from typing import Any

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from ia_investing.orchestration.policies import EXTERNAL_IO_RETRY_POLICY


@dataclass(frozen=True, slots=True)
class RunAgentInput:
    operation_id: str
    organization_id: str
    capability: str
    case_id: str | None
    input_payload: dict[str, Any]
    data_as_of: str
    knowledge_cutoff: str
    requested_by: str
    idempotency_key: str


@workflow.defn(name="RunAgentWorkflow")
class RunAgentWorkflow:
    @workflow.run
    async def run(self, command: RunAgentInput) -> dict[str, Any]:
        payload = asdict(command)
        payload["workflow_id"] = workflow.info().workflow_id
        result: dict[str, Any] = await workflow.execute_activity(
            "create_and_execute_agent_run",
            payload,
            start_to_close_timeout=timedelta(minutes=8),
            retry_policy=EXTERNAL_IO_RETRY_POLICY,
        )
        return result
