from __future__ import annotations

import logging
import re
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
    ScheduleState,
    ScheduleUpdate,
)
from temporalio.contrib.opentelemetry import TracingInterceptor

from apps.scheduler.policy import is_managed_schedule_id
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
    PolicyCollectionInput,
    PolicyCollectionWorkflow,
)
from ia_investing.settings import Settings, get_settings
from observability import setup_telemetry
from workflows._news_dedup import NewsDedupInput, NewsDedupWorkflow

logger = logging.getLogger(__name__)

_SHA256_PATTERN = re.compile(r"^[0-9a-fA-F]{64}$")


@dataclass(frozen=True, slots=True)
class ScheduleDefinition:
    schedule_id: str
    schedule: Schedule


def _validate_interval(every: timedelta) -> None:
    if every <= timedelta(0):
        raise ValueError("schedule interval must be positive")


def cvm_schedule_definition(
    *,
    cnpj: str,
    issuer_id: str,
    year: int,
    statement_type: str = "DRE_con",
    every: timedelta = timedelta(days=1),
    task_queue: str = "data-ingestion",
) -> ScheduleDefinition:
    _validate_interval(every)
    if not cnpj or not issuer_id:
        raise ValueError("CNPJ and issuer ID are required")
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
            state=ScheduleState(paused=False),
        ),
    )


def paper_reconciliation_schedule_definition(
    *,
    portfolio_id: str,
    organization_id: str,
    every: timedelta = timedelta(days=1),
    task_queue: str = "portfolio-risk",
) -> ScheduleDefinition:
    _validate_interval(every)
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
            state=ScheduleState(paused=False),
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
    _validate_interval(every)
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
            state=ScheduleState(paused=False),
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
    _validate_interval(every)
    if not portfolio_id or not portfolio_version_id or not _SHA256_PATTERN.fullmatch(input_sha256):
        raise ValueError("portfolio, version, and a SHA-256 input hash are required")
    schedule_id = f"paper-rebalance-{portfolio_id}".lower()
    return ScheduleDefinition(
        schedule_id=schedule_id,
        schedule=Schedule(
            action=ScheduleActionStartWorkflow(
                PaperRebalanceWorkflow.run,
                PaperRebalanceInput(
                    portfolio_id,
                    portfolio_version_id,
                    input_sha256,
                    approval_timeout_seconds,
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
            state=ScheduleState(paused=False),
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
    _validate_interval(every)
    if not issuer_id:
        raise ValueError("issuer ID is required")
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
                pause_on_failure=False,
            ),
            state=ScheduleState(paused=False),
        ),
    )


def news_dedup_schedule_definition(
    *,
    every: timedelta = timedelta(hours=24),
    lookback_hours: int = 24,
    batch_size: int = 500,
    task_queue: str = "research-agents",
) -> ScheduleDefinition:
    _validate_interval(every)
    if lookback_hours < 1 or batch_size < 1:
        raise ValueError("news dedup lookback and batch size must be positive")
    schedule_id = "news-dedup-cleanup"
    return ScheduleDefinition(
        schedule_id=schedule_id,
        schedule=Schedule(
            action=ScheduleActionStartWorkflow(
                NewsDedupWorkflow.run,
                NewsDedupInput(
                    schedule_id=schedule_id,
                    lookback_hours=lookback_hours,
                    batch_size=batch_size,
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
            state=ScheduleState(paused=False),
        ),
    )


def outbox_recovery_schedule_definition(
    *,
    every: timedelta = timedelta(minutes=1),
    task_queue: str = "research-agents",
) -> ScheduleDefinition:
    _validate_interval(every)
    schedule_id = "operation-outbox-dispatch"
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
            state=ScheduleState(paused=False),
        ),
    )


def policy_collection_schedule_definition(
    *,
    authority: str,
    every: timedelta = timedelta(hours=6),
    task_queue: str = "research-agents",
) -> ScheduleDefinition:
    _validate_interval(every)
    if not authority:
        raise ValueError("authority is required")
    schedule_id = f"policy-collection-{authority}".lower()
    return ScheduleDefinition(
        schedule_id=schedule_id,
        schedule=Schedule(
            action=ScheduleActionStartWorkflow(
                PolicyCollectionWorkflow.run,
                PolicyCollectionInput(authority=authority, schedule_id=schedule_id),
                id=schedule_id,
                task_queue=task_queue,
            ),
            spec=ScheduleSpec(intervals=[ScheduleIntervalSpec(every=every)]),
            policy=SchedulePolicy(
                overlap=ScheduleOverlapPolicy.SKIP,
                catchup_window=timedelta(hours=2),
                pause_on_failure=True,
            ),
            state=ScheduleState(paused=False),
        ),
    )


async def reconcile_schedules(
    client: Client,
    definitions: list[ScheduleDefinition],
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

    # Only declaratively managed schedules may be removed. External, legacy, and
    # organization-owned equity-exploration schedules are deliberately preserved.
    iterator = await client.list_schedules()
    async for desc in iterator:
        if desc.id in known_ids or not is_managed_schedule_id(desc.id):
            continue
        handle = client.get_schedule_handle(desc.id)
        await handle.delete()
        results[desc.id] = "deleted"

    return results


async def reconcile_configured_schedules(
    client: Client | None = None,
    settings: Settings | None = None,
) -> dict[str, str]:
    settings = settings or get_settings()
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
            (await session.execute(sa.select(Ticker.issuer_id).where(Ticker.issuer_id.is_not(None)).distinct()))
            .scalars()
            .all()
        )

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

    # --- Policy collection per authority ---
    for authority in settings.scheduler.policy_authorities:
        definitions.append(
            policy_collection_schedule_definition(
                authority=authority,
                every=timedelta(hours=settings.scheduler.policy_collection_interval_hours),
            )
        )

    return await reconcile_schedules(client, definitions)
