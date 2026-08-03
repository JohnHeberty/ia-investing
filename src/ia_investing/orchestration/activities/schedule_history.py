from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

from sqlalchemy import text
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
        started_at_str = params["started_at"]
        finished_at_str = params.get("finished_at")
        result_summary = params.get("result_summary")
        error_message = params.get("error_message")

        started = datetime.fromisoformat(started_at_str.replace("Z", "+00:00"))
        finished = (
            datetime.fromisoformat(finished_at_str.replace("Z", "+00:00"))
            if finished_at_str
            else None
        )
        result_json = json.dumps(result_summary) if result_summary else None

        async with session_scope() as session:
            await session.execute(
                text(
                    """
                    INSERT INTO schedule_run_history
                        (id, schedule_id, workflow_id, status,
                         started_at, finished_at, result_summary,
                         error_message, created_at)
                    VALUES
                        (gen_random_uuid(), :schedule_id, :workflow_id,
                         :status, :started_at, :finished_at,
                         :result_summary, :error_message, now())
                    """
                ),
                {
                    "schedule_id": schedule_id,
                    "workflow_id": workflow_id,
                    "status": status,
                    "started_at": started,
                    "finished_at": finished,
                    "result_summary": result_json,
                    "error_message": error_message,
                },
            )
        logger.info("Recorded schedule run: schedule=%s status=%s", schedule_id, status)
        return "recorded"


SCHEDULE_HISTORY_ACTIVITIES = (record_schedule_run,)
