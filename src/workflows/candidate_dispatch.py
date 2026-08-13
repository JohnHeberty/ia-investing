"""Periodic recovery workflow for candidate-intelligence outbox events."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from workflows._schedule_run import complete_schedule_run, fail_schedule_run, start_schedule_run

_DISPATCH_RETRY = RetryPolicy(
    initial_interval=timedelta(seconds=5),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(minutes=2),
    maximum_attempts=5,
)


@workflow.defn(name="CandidateOutboxDispatchWorkflow")
class CandidateOutboxDispatchWorkflow:
    @workflow.run
    async def run(self, command: dict[str, Any] | None = None) -> dict[str, int]:
        schedule_id = str((command or {}).get("schedule_id", ""))
        await start_schedule_run(schedule_id)
        try:
            result: dict[str, int] = await workflow.execute_activity(
                "dispatch_candidate_intelligence_events",
                command or {"batch_size": 50},
                start_to_close_timeout=timedelta(minutes=3),
                retry_policy=_DISPATCH_RETRY,
            )
        except Exception as exc:
            await fail_schedule_run(schedule_id, exc)
            raise
        await complete_schedule_run(schedule_id, result)
        return result
