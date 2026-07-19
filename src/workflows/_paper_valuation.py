from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from ia_investing.orchestration.policies import DEFAULT_ACTIVITY_RETRY_POLICY


@dataclass(frozen=True, slots=True)
class PaperValuationInput:
    portfolio_id: str
    portfolio_version_id: str
    organization_id: str


@dataclass(frozen=True, slots=True)
class PaperValuationResult:
    portfolio_id: str
    portfolio_version_id: str
    nav_publication_id: str
    as_of: str
    revision: int
    input_sha256: str
    nav: str
    reconciled: bool
    environment: str


@workflow.defn
class PaperValuationWorkflow:
    """Reconcile paper books before publishing an immutable daily NAV revision."""

    @workflow.run
    async def run(self, command: PaperValuationInput) -> PaperValuationResult:
        as_of = workflow.now().isoformat()
        reconciliation = await workflow.execute_activity(
            "reconcile_paper_portfolio",
            args=[command.portfolio_id, command.organization_id, as_of],
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=DEFAULT_ACTIVITY_RETRY_POLICY,
        )
        if reconciliation["blocking_count"]:
            raise RuntimeError("blocking reconciliation break prevents NAV publication")
        publication = await workflow.execute_activity(
            "publish_paper_nav",
            args=[command.portfolio_version_id, command.organization_id, as_of],
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=DEFAULT_ACTIVITY_RETRY_POLICY,
        )
        return PaperValuationResult(**publication)
