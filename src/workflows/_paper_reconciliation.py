from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from ia_investing.orchestration.policies import DEFAULT_ACTIVITY_RETRY_POLICY


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
        as_of = workflow.now().isoformat()
        result = await workflow.execute_activity(
            "reconcile_paper_portfolio",
            args=[command.portfolio_id, command.organization_id, as_of],
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=DEFAULT_ACTIVITY_RETRY_POLICY,
        )

        if command.schedule_id:
            await workflow.execute_activity(
                "record_schedule_run",
                {
                    "schedule_id": command.schedule_id,
                    "workflow_id": workflow.info().workflow_id,
                    "status": "completed",
                    "started_at": workflow.info().start_time.isoformat(),
                    "result_summary": {
                        "portfolio_id": command.portfolio_id,
                        "break_count": result.get("break_count", 0),
                        "blocking_count": result.get("blocking_count", 0),
                    },
                },
                start_to_close_timeout=timedelta(seconds=10),
            )

        return PaperReconciliationResult(**result)
