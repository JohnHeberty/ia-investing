"""Shared schedule-run history calls for Temporal workflows."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from temporalio import workflow


async def start_schedule_run(schedule_id: str) -> None:
    if not schedule_id:
        return
    await workflow.execute_activity(
        "record_schedule_run",
        {
            "schedule_id": schedule_id,
            "workflow_id": workflow.info().workflow_id,
            "status": "running",
            "started_at": workflow.info().start_time.isoformat(),
        },
        start_to_close_timeout=timedelta(seconds=10),
    )


async def complete_schedule_run(
    schedule_id: str,
    result_summary: dict[str, Any] | None = None,
    *,
    status: str = "completed",
    error_message: str | None = None,
) -> None:
    if not schedule_id:
        return
    await workflow.execute_activity(
        "record_schedule_run",
        {
            "schedule_id": schedule_id,
            "workflow_id": workflow.info().workflow_id,
            "status": status,
            "started_at": workflow.info().start_time.isoformat(),
            "finished_at": workflow.now().isoformat(),
            "result_summary": result_summary,
            "error_message": error_message,
        },
        start_to_close_timeout=timedelta(seconds=10),
    )


async def fail_schedule_run(schedule_id: str, exc: BaseException) -> None:
    await complete_schedule_run(
        schedule_id,
        status="failed",
        error_message=_format_error_chain(exc),
    )


def _format_error_chain(exc: BaseException) -> str:
    """Keep the actionable Temporal/activity cause instead of only its wrapper."""
    parts: list[str] = []
    current: BaseException | None = exc
    seen: set[int] = set()
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        parts.append(f"{type(current).__name__}: {current}")
        current = current.__cause__ or current.__context__
    return " <- ".join(parts)[:2000]
