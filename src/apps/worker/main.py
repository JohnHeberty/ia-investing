from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor

from temporalio.client import Client
from temporalio.contrib.opentelemetry import TracingInterceptor
from temporalio.worker import Worker

from ia_investing.candidate_intelligence.bootstrap import (
    configure_candidate_runtime_from_environment,
)
from ia_investing.orchestration.registry import definitions_for
from ia_investing.settings import get_settings
from observability import setup_telemetry

logger = logging.getLogger(__name__)


async def start_worker() -> None:
    settings = get_settings()
    capability = settings.worker.capability
    if settings.telemetry.enabled:
        setup_telemetry(
            f"ia-investing-worker-{capability}",
            settings.telemetry.otlp_endpoint,
        )

    task_queue, workflows, activities = definitions_for(capability)
    if capability == "research-agents":
        await configure_candidate_runtime_from_environment()
    if not workflows and not activities:
        raise RuntimeError(f"capability {capability!r} has no registered workflows or activities")

    client = await Client.connect(
        settings.temporal.address,
        namespace=settings.temporal.namespace,
        interceptors=[TracingInterceptor()] if settings.telemetry.enabled else [],
    )
    with ThreadPoolExecutor(
        max_workers=settings.worker.activity_threads,
        thread_name_prefix=f"temporal-{capability}",
    ) as activity_executor:
        worker = Worker(
            client,
            task_queue=task_queue,
            workflows=workflows,
            activities=activities,
            activity_executor=activity_executor,
        )
        logger.info(
            "Starting Temporal worker capability=%s queue=%s workflows=%s activities=%s",
            capability,
            task_queue,
            [workflow.__name__ for workflow in workflows],
            [activity.__name__ for activity in activities],
        )
        await worker.run()
