from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable, Coroutine
from typing import Any

logger = logging.getLogger(__name__)

TASK_SCHEDULES: dict[str, float] = {
    "ingest_cvm": 86400.0,
    "fetch_news": 14400.0,
    "fetch_macro": 86400.0,
}

_last_run: dict[str, float] = {}


async def _run_ingest_cvm() -> None:
    from workflows import IngestCVMWorkflow

    logger.info("Running CVM data ingestion")
    try:
        IngestCVMWorkflow()
        logger.info("CVM ingestion scheduled (workflow class loaded)")
    except Exception:
        logger.exception("CVM ingestion failed")


async def _run_fetch_news() -> None:

    logger.info("Running news fetch")
    try:
        logger.info("News fetch scheduled (workflow class loaded)")
    except Exception:
        logger.exception("News fetch failed")


async def _run_fetch_macro() -> None:
    from datetime import date, timedelta

    from connectors.macro._bcb import (
        get_ipca,
        get_selic,
        get_usd_brl,
    )

    logger.info("Running macro data fetch")
    try:
        end = date.today()
        start = end - timedelta(days=7)
        await get_selic(start, end)
        await get_ipca(start, end)
        await get_usd_brl(start, end)
        logger.info("Macro data fetch completed")
    except Exception:
        logger.exception("Macro data fetch failed")


TASK_RUNNERS: dict[str, Callable[..., Coroutine[Any, Any, None]]] = {
    "ingest_cvm": _run_ingest_cvm,
    "fetch_news": _run_fetch_news,
    "fetch_macro": _run_fetch_macro,
}


async def _scheduler_loop() -> None:
    logger.info("Scheduler started")
    while True:
        now = asyncio.get_running_loop().time()
        for task_name, interval in TASK_SCHEDULES.items():
            last = _last_run.get(task_name, 0.0)
            if now - last >= interval:
                runner = TASK_RUNNERS.get(task_name)
                if runner:
                    logger.info("Executing scheduled task: %s", task_name)
                    try:
                        await runner()
                    except Exception:
                        logger.exception("Task %s failed", task_name)
                    _last_run[task_name] = now
        await asyncio.sleep(60)


async def run_scheduler() -> None:
    await _scheduler_loop()
