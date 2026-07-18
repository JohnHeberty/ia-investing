from __future__ import annotations

import logging

from temporalio.client import Client
from temporalio.worker import Worker

from database.config import get_settings
from workflows import (
    AnalyzeFilingWorkflow,
    AnalyzeNewsWorkflow,
    DiscoverStocksWorkflow,
    IngestCVMWorkflow,
)

logger = logging.getLogger(__name__)

WORKFLOWS = [
    IngestCVMWorkflow,
    AnalyzeFilingWorkflow,
    AnalyzeNewsWorkflow,
    DiscoverStocksWorkflow,
]


async def start_worker() -> None:
    settings = get_settings()
    client = await Client.connect(
        settings.temporal_address,
        namespace=settings.temporal_namespace,
    )

    worker = Worker(
        client,
        task_queue=settings.temporal_task_queue,
        workflows=WORKFLOWS,
    )

    logger.info(
        "Starting Temporal worker on queue=%s with workflows=%s",
        settings.temporal_task_queue,
        [w.__name__ for w in WORKFLOWS],
    )
    try:
        await worker.run()
    finally:
        await client.close()
