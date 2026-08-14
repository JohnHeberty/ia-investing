"""Workflow that collects policy data from all active DB-driven sources."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from ia_investing.orchestration.policies import EXTERNAL_IO_RETRY_POLICY
    from workflows._schedule_run import complete_schedule_run, fail_schedule_run, start_schedule_run


@dataclass(frozen=True, slots=True)
class PolicySourceCollectionInput:
    schedule_id: str = ""


@dataclass(frozen=True, slots=True)
class PolicySourceCollectionResult:
    sources_attempted: int = 0
    sources_succeeded: int = 0
    sources_failed: int = 0
    status: str = "completed"


@workflow.defn(name="PolicySourceCollectionWorkflow")
class PolicySourceCollectionWorkflow:
    @workflow.run
    async def run(self, command: PolicySourceCollectionInput) -> PolicySourceCollectionResult:
        await start_schedule_run(command.schedule_id)
        try:
            result = await self._collect_all(command)
        except Exception as exc:
            await fail_schedule_run(command.schedule_id, exc)
            raise
        await complete_schedule_run(command.schedule_id, result.__dict__)
        return result

    async def _collect_all(self, command: PolicySourceCollectionInput) -> PolicySourceCollectionResult:
        # List active sources from DB
        sources_result: dict[str, Any] = await workflow.execute_activity(
            "list_active_policy_sources",
            {},
            start_to_close_timeout=timedelta(minutes=1),
            retry_policy=EXTERNAL_IO_RETRY_POLICY,
        )

        sources = sources_result.get("sources", [])
        succeeded = 0
        failed = 0

        for source in sources:
            try:
                result: dict[str, Any] = await workflow.execute_activity(
                    "collect_from_policy_source",
                    {"source_id": source["id"], "since": source.get("last_fetched_at")},
                    start_to_close_timeout=timedelta(minutes=5),
                    retry_policy=EXTERNAL_IO_RETRY_POLICY,
                )
                if result.get("status") == "completed":
                    succeeded += 1
                else:
                    failed += 1
            except Exception:
                failed += 1

        return PolicySourceCollectionResult(
            sources_attempted=len(sources),
            sources_succeeded=succeeded,
            sources_failed=failed,
        )
