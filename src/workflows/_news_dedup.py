"""Scheduled workflow for idempotent news-event deduplication."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from ia_investing.orchestration.policies import DEFAULT_ACTIVITY_RETRY_POLICY
    from workflows._schedule_run import complete_schedule_run, fail_schedule_run, start_schedule_run


@dataclass(frozen=True, slots=True)
class NewsDedupInput:
    schedule_id: str
    lookback_hours: int = 24
    batch_size: int = 500


@workflow.defn(name="NewsDedupWorkflow")
class NewsDedupWorkflow:
    @workflow.run
    async def run(self, command: NewsDedupInput) -> dict[str, int]:
        await start_schedule_run(command.schedule_id)
        try:
            result: dict[str, int] = await workflow.execute_activity(
                "deduplicate_recent_events",
                {"lookback_hours": command.lookback_hours, "batch_size": command.batch_size},
                start_to_close_timeout=timedelta(minutes=10),
                retry_policy=DEFAULT_ACTIVITY_RETRY_POLICY,
            )
        except Exception as exc:
            await fail_schedule_run(command.schedule_id, exc)
            raise

        await complete_schedule_run(command.schedule_id, result)
        return result
