from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import timedelta

from temporalio.client import (
    Client,
    Schedule,
    ScheduleActionStartWorkflow,
    ScheduleAlreadyRunningError,
    ScheduleIntervalSpec,
    ScheduleOverlapPolicy,
    SchedulePolicy,
    ScheduleSpec,
    ScheduleUpdate,
)
from temporalio.contrib.opentelemetry import TracingInterceptor

from ia_investing.settings import get_settings
from observability import setup_telemetry
from workflows import (
    IngestCVMInput,
    IngestCVMWorkflow,
    PaperRebalanceInput,
    PaperRebalanceWorkflow,
    PaperReconciliationInput,
    PaperReconciliationWorkflow,
    PaperValuationInput,
    PaperValuationWorkflow,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ScheduleDefinition:
    schedule_id: str
    schedule: Schedule


def cvm_schedule_definition(
    *,
    cnpj: str,
    issuer_id: str,
    year: int,
    statement_type: str = "DRE_con",
    every: timedelta = timedelta(days=1),
    task_queue: str = "data-ingestion",
) -> ScheduleDefinition:
    workflow_input = IngestCVMInput(
        cnpj=cnpj,
        issuer_id=issuer_id,
        year=year,
        statement_type=statement_type,
    )
    return ScheduleDefinition(
        schedule_id=f"cvm-dfp-{issuer_id}-{year}-{statement_type}".lower(),
        schedule=Schedule(
            action=ScheduleActionStartWorkflow(
                IngestCVMWorkflow.run,
                workflow_input,
                id=f"cvm-dfp-{issuer_id}-{year}-{statement_type}",
                task_queue=task_queue,
            ),
            spec=ScheduleSpec(intervals=[ScheduleIntervalSpec(every=every)]),
            policy=SchedulePolicy(
                overlap=ScheduleOverlapPolicy.SKIP,
                catchup_window=timedelta(hours=1),
                pause_on_failure=True,
            ),
        ),
    )


def paper_reconciliation_schedule_definition(
    *,
    portfolio_id: str,
    organization_id: str,
    every: timedelta = timedelta(days=1),
    task_queue: str = "portfolio-risk",
) -> ScheduleDefinition:
    if not portfolio_id or not organization_id:
        raise ValueError("portfolio and organization IDs are required")
    return ScheduleDefinition(
        schedule_id=f"paper-reconciliation-{portfolio_id}".lower(),
        schedule=Schedule(
            action=ScheduleActionStartWorkflow(
                PaperReconciliationWorkflow.run,
                PaperReconciliationInput(portfolio_id, organization_id),
                id=f"paper-reconciliation-{portfolio_id}",
                task_queue=task_queue,
            ),
            spec=ScheduleSpec(intervals=[ScheduleIntervalSpec(every=every)]),
            policy=SchedulePolicy(
                overlap=ScheduleOverlapPolicy.SKIP,
                catchup_window=timedelta(hours=1),
                pause_on_failure=True,
            ),
        ),
    )


def paper_valuation_schedule_definition(
    *,
    portfolio_id: str,
    portfolio_version_id: str,
    organization_id: str,
    every: timedelta = timedelta(days=1),
    task_queue: str = "portfolio-risk",
) -> ScheduleDefinition:
    if not portfolio_id or not portfolio_version_id or not organization_id:
        raise ValueError("portfolio, version, and organization IDs are required")
    return ScheduleDefinition(
        schedule_id=f"paper-valuation-{portfolio_id}".lower(),
        schedule=Schedule(
            action=ScheduleActionStartWorkflow(
                PaperValuationWorkflow.run,
                PaperValuationInput(portfolio_id, portfolio_version_id, organization_id),
                id=f"paper-valuation-{portfolio_id}",
                task_queue=task_queue,
            ),
            spec=ScheduleSpec(intervals=[ScheduleIntervalSpec(every=every)]),
            policy=SchedulePolicy(
                overlap=ScheduleOverlapPolicy.SKIP,
                catchup_window=timedelta(hours=1),
                pause_on_failure=True,
            ),
        ),
    )


def paper_rebalance_schedule_definition(
    *,
    portfolio_id: str,
    portfolio_version_id: str,
    input_sha256: str,
    approval_timeout_seconds: int = 604_800,
    every: timedelta = timedelta(days=7),
    task_queue: str = "portfolio-risk",
) -> ScheduleDefinition:
    if not portfolio_id or not portfolio_version_id or len(input_sha256) != 64:
        raise ValueError("portfolio, version, and a SHA-256 input hash are required")
    return ScheduleDefinition(
        schedule_id=f"paper-rebalance-{portfolio_id}".lower(),
        schedule=Schedule(
            action=ScheduleActionStartWorkflow(
                PaperRebalanceWorkflow.run,
                PaperRebalanceInput(portfolio_id, portfolio_version_id, input_sha256, approval_timeout_seconds),
                id=f"paper-rebalance-{portfolio_id}",
                task_queue=task_queue,
            ),
            spec=ScheduleSpec(intervals=[ScheduleIntervalSpec(every=every)]),
            policy=SchedulePolicy(
                overlap=ScheduleOverlapPolicy.SKIP,
                catchup_window=timedelta(hours=1),
                pause_on_failure=True,
            ),
        ),
    )


async def reconcile_schedules(client: Client, definitions: list[ScheduleDefinition]) -> dict[str, str]:
    """Create or update schedules without spawning an in-memory scheduler loop."""
    results: dict[str, str] = {}
    for definition in definitions:
        try:
            await client.create_schedule(definition.schedule_id, definition.schedule)
            results[definition.schedule_id] = "created"
        except ScheduleAlreadyRunningError:
            handle = client.get_schedule_handle(definition.schedule_id)
            schedule = definition.schedule
            await handle.update(lambda _, schedule=schedule: ScheduleUpdate(schedule))
            results[definition.schedule_id] = "updated"
    return results


async def reconcile_configured_schedules() -> dict[str, str]:
    settings = get_settings()
    if settings.telemetry.enabled:
        setup_telemetry("ia-investing-scheduler", settings.telemetry.otlp_endpoint)
    client = await Client.connect(
        settings.temporal.address,
        namespace=settings.temporal.namespace,
        interceptors=[TracingInterceptor()] if settings.telemetry.enabled else [],
    )
    definitions: list[ScheduleDefinition] = []
    if settings.scheduler.cvm_cnpj and settings.scheduler.cvm_issuer_id:
        definitions.append(
            cvm_schedule_definition(
                cnpj=settings.scheduler.cvm_cnpj,
                issuer_id=settings.scheduler.cvm_issuer_id,
                year=settings.scheduler.cvm_year,
                statement_type=settings.scheduler.cvm_statement_type,
            )
        )
    paper_values = (settings.scheduler.paper_portfolio_id, settings.scheduler.paper_organization_id)
    if any(paper_values) and not all(paper_values):
        raise ValueError("paper reconciliation schedule requires portfolio and organization IDs")
    if all(paper_values):
        definitions.append(
            paper_reconciliation_schedule_definition(
                portfolio_id=settings.scheduler.paper_portfolio_id or "",
                organization_id=settings.scheduler.paper_organization_id or "",
            )
        )
    paper_automation_values = (
        settings.scheduler.paper_portfolio_version_id,
        settings.scheduler.paper_rebalance_input_sha256,
    )
    if any(paper_automation_values) and not all((*paper_values, *paper_automation_values)):
        raise ValueError("paper valuation/rebalance schedules require portfolio, organization, version, and input hash")
    if all((*paper_values, *paper_automation_values)):
        definitions.extend(
            [
                paper_valuation_schedule_definition(
                    portfolio_id=settings.scheduler.paper_portfolio_id or "",
                    portfolio_version_id=settings.scheduler.paper_portfolio_version_id or "",
                    organization_id=settings.scheduler.paper_organization_id or "",
                ),
                paper_rebalance_schedule_definition(
                    portfolio_id=settings.scheduler.paper_portfolio_id or "",
                    portfolio_version_id=settings.scheduler.paper_portfolio_version_id or "",
                    input_sha256=settings.scheduler.paper_rebalance_input_sha256 or "",
                ),
            ]
        )
    if not definitions:
        raise ValueError("at least one scheduler definition must be configured")
    return await reconcile_schedules(client, definitions)


def main() -> None:
    results = asyncio.run(reconcile_configured_schedules())
    for schedule_id, result in results.items():
        logger.info("schedule=%s result=%s", schedule_id, result)


if __name__ == "__main__":
    main()
