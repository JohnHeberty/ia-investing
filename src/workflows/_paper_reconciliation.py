from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from ia_investing.orchestration.policies import DEFAULT_ACTIVITY_RETRY_POLICY
    from workflows._schedule_run import complete_schedule_run, fail_schedule_run, start_schedule_run


@dataclass(frozen=True, slots=True)
class PaperReconciliationInput:
    portfolio_id: str
    organization_id: str
    schedule_id: str = ""


@dataclass(frozen=True, slots=True)
class PaperReconciliationResult:
    portfolio_id: str
    as_of: str
    break_count: int
    blocking_count: int
    environment: str


@workflow.defn
class PaperReconciliationWorkflow:
    @workflow.run
    async def run(self, command: PaperReconciliationInput) -> PaperReconciliationResult:
        await start_schedule_run(command.schedule_id)
        try:
            result = await self._reconcile(command)
        except Exception as exc:
            await fail_schedule_run(command.schedule_id, exc)
            raise
        await complete_schedule_run(
            command.schedule_id,
            {
                "portfolio_id": command.portfolio_id,
                "break_count": result.break_count,
                "blocking_count": result.blocking_count,
            },
        )
        return result

    async def _reconcile(self, command: PaperReconciliationInput) -> PaperReconciliationResult:
        as_of = workflow.now().isoformat()
        result = await workflow.execute_activity(
            "reconcile_paper_portfolio",
            args=[command.portfolio_id, command.organization_id, as_of],
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=DEFAULT_ACTIVITY_RETRY_POLICY,
        )

        return PaperReconciliationResult(**result)
