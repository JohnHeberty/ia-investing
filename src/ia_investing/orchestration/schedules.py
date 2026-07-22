from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from temporalio.client import (
    Schedule,
    ScheduleActionStartWorkflow,
    ScheduleIntervalSpec,
    ScheduleOverlapPolicy,
    SchedulePolicy,
    ScheduleSpec,
    ScheduleState,
)

from ia_investing.candidate_intelligence.bootstrap import candidate_intelligence_enabled


@dataclass(frozen=True, slots=True)
class ScheduleDefinition:
    schedule_id: str
    workflow: str
    task_queue: str
    interval: timedelta
    input_payload: dict[str, Any]
    paused: bool = False

    def temporal_schedule(self) -> Schedule:
        return Schedule(
            action=ScheduleActionStartWorkflow(
                self.workflow,
                self.input_payload,
                id=f"{self.schedule_id}-workflow",
                task_queue=self.task_queue,
            ),
            spec=ScheduleSpec(intervals=[ScheduleIntervalSpec(every=self.interval)]),
            policy=SchedulePolicy(
                overlap=ScheduleOverlapPolicy.SKIP,
                catchup_window=timedelta(hours=2),
                pause_on_failure=True,
            ),
            state=ScheduleState(paused=self.paused),
        )


def default_schedules(settings: Any) -> list[ScheduleDefinition]:
    schedules: list[ScheduleDefinition] = [
        ScheduleDefinition(
            schedule_id="operation-outbox-dispatch",
            workflow="DispatchOperationsWorkflow",
            task_queue="research-agents",
            interval=timedelta(minutes=1),
            input_payload={"batch_size": 50},
        )
    ]
    scheduler = settings.scheduler
    if scheduler.cvm_cnpj and scheduler.cvm_issuer_id:
        schedules.append(
            ScheduleDefinition(
                schedule_id="cvm-filing-discovery",
                workflow="IngestCVMWorkflow",
                task_queue="data-ingestion",
                interval=timedelta(minutes=20),
                input_payload={
                    "cnpj": scheduler.cvm_cnpj,
                    "issuer_id": scheduler.cvm_issuer_id,
                    "year": scheduler.cvm_year,
                    "statement_type": scheduler.cvm_statement_type,
                },
            )
        )
    if scheduler.paper_portfolio_id and scheduler.paper_portfolio_version_id:
        schedules.extend(
            [
                ScheduleDefinition(
                    schedule_id="paper-portfolio-valuation",
                    workflow="PaperValuationWorkflow",
                    task_queue="portfolio-risk",
                    interval=timedelta(hours=24),
                    input_payload={
                        "portfolio_id": scheduler.paper_portfolio_id,
                        "portfolio_version_id": scheduler.paper_portfolio_version_id,
                        "organization_id": scheduler.paper_organization_id,
                    },
                ),
                ScheduleDefinition(
                    schedule_id="paper-portfolio-reconciliation",
                    workflow="PaperReconciliationWorkflow",
                    task_queue="portfolio-risk",
                    interval=timedelta(hours=24),
                    input_payload={
                        "portfolio_id": scheduler.paper_portfolio_id,
                        "organization_id": scheduler.paper_organization_id,
                    },
                ),
            ]
        )
    if candidate_intelligence_enabled():
        schedules.append(
            ScheduleDefinition(
                schedule_id="candidate-intelligence-outbox-dispatch",
                workflow="CandidateOutboxDispatchWorkflow",
                task_queue="research-agents",
                interval=timedelta(minutes=1),
                input_payload={"batch_size": 50},
            )
        )
    return schedules
