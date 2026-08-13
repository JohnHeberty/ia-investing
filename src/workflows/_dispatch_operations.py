"""Periodic recovery workflow for the transactional operation outbox."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from ia_investing.orchestration.policies import EXTERNAL_IO_RETRY_POLICY
    from workflows._schedule_run import complete_schedule_run, fail_schedule_run, start_schedule_run


@workflow.defn(name="DispatchOperationsWorkflow")
class DispatchOperationsWorkflow:
    @workflow.run
    async def run(self, command: dict[str, Any] | None = None) -> dict[str, int]:
        schedule_id = str((command or {}).get("schedule_id", ""))
        await start_schedule_run(schedule_id)
        try:
            result: dict[str, int] = await workflow.execute_activity(
                "dispatch_pending_operations",
                command or {"batch_size": 50},
                start_to_close_timeout=timedelta(minutes=2),
                retry_policy=EXTERNAL_IO_RETRY_POLICY,
            )
        except Exception as exc:
            await fail_schedule_run(schedule_id, exc)
            raise

        await complete_schedule_run(schedule_id, result)
        return result
