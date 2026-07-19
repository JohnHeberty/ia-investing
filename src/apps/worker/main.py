from __future__ import annotations

import logging
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from temporalio.client import Client
from temporalio.contrib.opentelemetry import TracingInterceptor
from temporalio.worker import Worker

from ia_investing.orchestration import TASK_QUEUES, Capability
from ia_investing.orchestration.activities import (
    DATA_INGESTION_ACTIVITIES,
    NOTIFICATION_ACTIVITIES,
    OPERATION_ACTIVITIES,
    PAPER_OPERATION_ACTIVITIES,
    RESEARCH_MOCK_ACTIVITIES,
)
from ia_investing.settings import get_settings
from observability import setup_telemetry
from workflows import (
    AnalyzeFilingWorkflow,
    AnalyzeNewsWorkflow,
    ApprovalGateWorkflow,
    DiscoverStocksWorkflow,
    IngestCVMWorkflow,
    PaperRebalanceWorkflow,
    PaperReconciliationWorkflow,
    PaperValuationWorkflow,
    PolicyEventWorkflow,
    PortfolioConstructionWorkflow,
    PortfolioOptimizationWorkflow,
    RunAgentWorkflow,
)

logger = logging.getLogger(__name__)

WORKFLOWS_BY_CAPABILITY: dict[Capability, Sequence[type[Any]]] = {
    Capability.DATA_INGESTION: (IngestCVMWorkflow,),
    Capability.DOCUMENT_PROCESSING: (),
    Capability.RESEARCH_AGENTS: (
        AnalyzeFilingWorkflow,
        AnalyzeNewsWorkflow,
        ApprovalGateWorkflow,
        PolicyEventWorkflow,
        DiscoverStocksWorkflow,
        RunAgentWorkflow,
    ),
    Capability.PORTFOLIO_RISK: (
        PortfolioConstructionWorkflow,
        PortfolioOptimizationWorkflow,
        PaperRebalanceWorkflow,
        PaperReconciliationWorkflow,
        PaperValuationWorkflow,
    ),
    Capability.NOTIFICATIONS: (),
}

ACTIVITIES_BY_CAPABILITY: dict[Capability, Sequence[Any]] = {
    Capability.DATA_INGESTION: (*DATA_INGESTION_ACTIVITIES, *NOTIFICATION_ACTIVITIES),
    Capability.DOCUMENT_PROCESSING: (),
    Capability.RESEARCH_AGENTS: (*RESEARCH_MOCK_ACTIVITIES, *OPERATION_ACTIVITIES, *NOTIFICATION_ACTIVITIES),
    Capability.PORTFOLIO_RISK: PAPER_OPERATION_ACTIVITIES,
    Capability.NOTIFICATIONS: NOTIFICATION_ACTIVITIES,
}


async def start_worker() -> None:
    settings = get_settings()
    if settings.telemetry.enabled:
        setup_telemetry(f"ia-investing-worker-{settings.worker.capability}", settings.telemetry.otlp_endpoint)
    capability = Capability(settings.worker.capability)
    client = await Client.connect(
        settings.temporal.address,
        namespace=settings.temporal.namespace,
        interceptors=[TracingInterceptor()] if settings.telemetry.enabled else [],
    )

    workflows = WORKFLOWS_BY_CAPABILITY[capability]
    activities = ACTIVITIES_BY_CAPABILITY[capability]
    if capability is Capability.RESEARCH_AGENTS and settings.ai.provider != "mock":
        raise RuntimeError("only AI__PROVIDER=mock is implemented for the phase-1 research worker")
    if not workflows and not activities:
        raise RuntimeError(f"capability {capability} has no registered workflows or activities")
    with ThreadPoolExecutor(
        max_workers=settings.worker.activity_threads,
        thread_name_prefix=f"temporal-{capability.value}",
    ) as activity_executor:
        worker = Worker(
            client,
            task_queue=TASK_QUEUES[capability],
            workflows=workflows,
            activities=activities,
            activity_executor=activity_executor,
        )

        logger.info(
            "Starting Temporal worker capability=%s queue=%s workflows=%s activities=%s",
            capability,
            TASK_QUEUES[capability],
            [workflow.__name__ for workflow in workflows],
            [activity.__name__ for activity in activities],
        )
        await worker.run()
