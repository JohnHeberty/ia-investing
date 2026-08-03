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
    schedule_id: str = ""


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
            if command.schedule_id:
                await workflow.execute_activity(
                    "record_schedule_run",
                    {
                        "schedule_id": command.schedule_id,
                        "workflow_id": workflow.info().workflow_id,
                        "status": "failed",
                        "started_at": workflow.info().start_time.isoformat(),
                        "error_message": "blocking reconciliation break prevents NAV publication",
                    },
                    start_to_close_timeout=timedelta(seconds=10),
                )
            raise RuntimeError("blocking reconciliation break prevents NAV publication")

        publication = await workflow.execute_activity(
            "publish_paper_nav",
            args=[command.portfolio_version_id, command.organization_id, as_of],
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
                        "nav": publication.get("nav", ""),
                        "revision": publication.get("revision", 0),
                    },
                },
                start_to_close_timeout=timedelta(seconds=10),
            )

        return PaperValuationResult(**publication)
