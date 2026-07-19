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
        return PaperReconciliationResult(**result)
