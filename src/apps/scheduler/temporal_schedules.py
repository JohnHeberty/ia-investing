from __future__ import annotations

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

from ia_investing.orchestration.workflows import (  # type: ignore[attr-defined]
    DispatchOperationsWorkflow,
    ExtractNewsInput,
    ExtractNewsWorkflow,
    IngestCVMInput,
    IngestCVMWorkflow,
    PaperRebalanceInput,
    PaperRebalanceWorkflow,
    PaperReconciliationInput,
    PaperReconciliationWorkflow,
    PaperValuationInput,
    PaperValuationWorkflow,
)
from ia_investing.settings import get_settings
from observability import setup_telemetry

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
    schedule_id = f"cvm-dfp-{issuer_id}-{year}-{statement_type}".lower()
    workflow_input = IngestCVMInput(
        cnpj=cnpj,
        issuer_id=issuer_id,
        year=year,
        statement_type=statement_type,
        schedule_id=schedule_id,
    )
    return ScheduleDefinition(
        schedule_id=schedule_id,
        schedule=Schedule(
            action=ScheduleActionStartWorkflow(
                IngestCVMWorkflow.run,
                workflow_input,
                id=schedule_id,
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
    schedule_id = f"paper-reconciliation-{portfolio_id}".lower()
    return ScheduleDefinition(
        schedule_id=schedule_id,
        schedule=Schedule(
            action=ScheduleActionStartWorkflow(
                PaperReconciliationWorkflow.run,
                PaperReconciliationInput(portfolio_id, organization_id, schedule_id=schedule_id),
                id=schedule_id,
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
    schedule_id = f"paper-valuation-{portfolio_id}".lower()
    return ScheduleDefinition(
        schedule_id=schedule_id,
        schedule=Schedule(
            action=ScheduleActionStartWorkflow(
                PaperValuationWorkflow.run,
                PaperValuationInput(portfolio_id, portfolio_version_id, organization_id, schedule_id=schedule_id),
                id=schedule_id,
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


def news_collection_schedule_definition(
    *,
    issuer_id: str,
    every: timedelta = timedelta(hours=4),
    max_results: int = 20,
    analyze_limit: int = 10,
    task_queue: str = "research-agents",
) -> ScheduleDefinition:
    schedule_id = f"news-collection-{issuer_id}".lower()
    return ScheduleDefinition(
        schedule_id=schedule_id,
        schedule=Schedule(
            action=ScheduleActionStartWorkflow(
                ExtractNewsWorkflow.run,
                ExtractNewsInput(
                    issuer_id=issuer_id,
                    max_results=max_results,
                    analyze_limit=analyze_limit,
                    schedule_id=schedule_id,
                ),
                id=schedule_id,
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


def news_dedup_schedule_definition(
    *,
    every: timedelta = timedelta(hours=24),
    task_queue: str = "research-agents",
) -> ScheduleDefinition:
    schedule_id = "news-dedup-cleanup"
    return ScheduleDefinition(
        schedule_id=schedule_id,
        schedule=Schedule(
            action=ScheduleActionStartWorkflow(
                DispatchOperationsWorkflow.run,
                {"batch_size": 50, "schedule_id": schedule_id},
                id=schedule_id,
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


def outbox_recovery_schedule_definition(
    *,
    every: timedelta = timedelta(minutes=30),
    task_queue: str = "research-agents",
) -> ScheduleDefinition:
    schedule_id = "outbox-dispatch-recovery"
    return ScheduleDefinition(
        schedule_id=schedule_id,
        schedule=Schedule(
            action=ScheduleActionStartWorkflow(
                DispatchOperationsWorkflow.run,
                {"batch_size": 50, "schedule_id": schedule_id},
                id=schedule_id,
                task_queue=task_queue,
            ),
            spec=ScheduleSpec(intervals=[ScheduleIntervalSpec(every=every)]),
            policy=SchedulePolicy(
                overlap=ScheduleOverlapPolicy.SKIP,
                catchup_window=timedelta(minutes=15),
                pause_on_failure=True,
            ),
        ),
    )


_PRESERVE_PREFIXES = ("equity-exploration-",)


async def reconcile_schedules(
    client: Client,
    definitions: list[ScheduleDefinition],
    preserve_prefixes: tuple[str, ...] = _PRESERVE_PREFIXES,
) -> dict[str, str]:
    results: dict[str, str] = {}
    known_ids: set[str] = set()

    for definition in definitions:
        known_ids.add(definition.schedule_id)
        try:
            await client.create_schedule(definition.schedule_id, definition.schedule)
            results[definition.schedule_id] = "created"
        except ScheduleAlreadyRunningError:
            handle = client.get_schedule_handle(definition.schedule_id)

            async def _updater(_input: object, _schedule: Schedule = definition.schedule) -> ScheduleUpdate:
                return ScheduleUpdate(_schedule)

            await handle.update(_updater)
            results[definition.schedule_id] = "updated"

    # Delete stale schedules not in definitions (preserving externally managed prefixes)
    try:
        iterator = await client.list_schedules()  # type: ignore[attr-defined]
        async for desc in iterator:
            if desc.id in known_ids:
                continue
            if any(desc.id.startswith(p) for p in preserve_prefixes):
                continue
            try:
                handle = client.get_schedule_handle(desc.id)
                await handle.delete()
                results[desc.id] = "deleted"
            except Exception:
                logger.warning("Failed to delete stale schedule %s", desc.id)
    except Exception:
        logger.warning("Failed to list schedules for stale cleanup")

    return results


async def reconcile_configured_schedules(client: Client | None = None) -> dict[str, str]:
    settings = get_settings()
    if client is None:
        if settings.telemetry.enabled:
            setup_telemetry("ia-investing-scheduler", settings.telemetry.otlp_endpoint)
        client = await Client.connect(
            settings.temporal.address,
            namespace=settings.temporal.namespace,
            interceptors=[TracingInterceptor()] if settings.telemetry.enabled else [],
        )
    definitions: list[ScheduleDefinition] = []

    # --- Default schedules (always created) ---
    definitions.append(
        news_dedup_schedule_definition(
            every=timedelta(hours=settings.scheduler.news_dedup_interval_hours),
        )
    )
    definitions.append(
        outbox_recovery_schedule_definition(
            every=timedelta(minutes=settings.scheduler.outbox_recovery_interval_minutes),
        )
    )

    # --- News collection per issuer ---
    import sqlalchemy as sa

    from database.core import session_scope
    from database.models.catalog import Ticker

    async with session_scope() as session:
        issuer_ids = (
            await session.execute(
                sa.select(Ticker.issuer_id).where(Ticker.issuer_id.is_not(None)).distinct()
            )
        ).scalars().all()

    for issuer_id in issuer_ids:
        definitions.append(
            news_collection_schedule_definition(
                issuer_id=str(issuer_id),
                every=timedelta(hours=settings.scheduler.news_collection_interval_hours),
            )
        )

    # --- Conditional schedules (require env vars) ---
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

    return await reconcile_schedules(client, definitions)
