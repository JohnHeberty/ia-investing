from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.dialects.postgresql import insert as pg_insert
from temporalio import activity

from ia_investing.orchestration.activities._telemetry import activity_span

logger = logging.getLogger(__name__)


@activity.defn(name="record_schedule_run")
async def record_schedule_run(params: dict[str, Any]) -> str:
    with activity_span("record_schedule_run"):
        from database.core import session_scope

        schedule_id = params["schedule_id"]
        workflow_id = params["workflow_id"]
        status = params.get("status", "completed")
        if status not in {"running", "completed", "failed"}:
            raise ValueError("invalid schedule run status")
        started_at_str = params["started_at"]
        finished_at_str = params.get("finished_at")
        result_summary = params.get("result_summary")
        error_message = params.get("error_message")

        started = datetime.fromisoformat(started_at_str.replace("Z", "+00:00"))
        finished = datetime.fromisoformat(finished_at_str.replace("Z", "+00:00")) if finished_at_str else None
        if status != "running" and finished is None:
            finished = datetime.now(UTC)

        async with session_scope() as session:
            from database.models.schedule_history import ScheduleRunHistory

            statement = pg_insert(ScheduleRunHistory).values(
                schedule_id=schedule_id,
                workflow_id=workflow_id,
                status=status,
                started_at=started,
                finished_at=finished,
                result_summary=result_summary,
                error_message=error_message,
            )
            statement = statement.on_conflict_do_update(
                index_elements=[ScheduleRunHistory.schedule_id, ScheduleRunHistory.workflow_id],
                set_={
                    "status": statement.excluded.status,
                    "finished_at": statement.excluded.finished_at,
                    "result_summary": statement.excluded.result_summary,
                    "error_message": statement.excluded.error_message,
                },
            )
            await session.execute(statement)
        logger.info("Recorded schedule run: schedule=%s status=%s", schedule_id, status)
        return "recorded"


SCHEDULE_HISTORY_ACTIVITIES = (record_schedule_run,)
