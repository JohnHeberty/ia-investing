from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict
from temporalio.client import Client

from apps.api.security import AuthContext, require_permission
from ia_investing.settings import get_settings

router = APIRouter(prefix="/api/v1/schedules", tags=["schedules"])


class ScheduleSummaryV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schedule_id: str
    status: str
    paused: bool
    next_action_time: datetime | None = None
    spec: dict[str, Any] | None = None
    state: dict[str, Any] | None = None


class ScheduleDetailV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schedule_id: str
    status: str
    paused: bool
    next_action_time: datetime | None = None
    spec: dict[str, Any] | None = None
    state: dict[str, Any] | None = None
    action: dict[str, Any] | None = None
    policy: dict[str, Any] | None = None
    created_at: datetime | None = None
    last_updated_at: datetime | None = None
    info: dict[str, Any] | None = None


class ScheduleActionResponseV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schedule_id: str
    paused: bool
    message: str


async def _get_temporal_client() -> Client:
    settings = get_settings()
    return await Client.connect(
        settings.temporal.address,
        namespace=settings.temporal.namespace,
    )


def _parse_schedule_description(description: Any) -> dict[str, Any]:
    spec_obj = description.schedule.spec
    state_obj = description.schedule.state
    action_obj = description.schedule.action
    policy_obj = description.schedule.policy
    info_obj = description.info

    result: dict[str, Any] = {
        "schedule_id": description.id,
        "status": description.status,
        "paused": description.schedule.state.paused if state_obj else False,
        "next_action_time": description.schedule_state.next_action_time if description.schedule_state else None,
        "spec": {
            "intervals": [
                {
                    "every": str(interval.every),
                    "offset": str(interval.offset) if interval.offset else None,
                }
                for interval in (spec_obj.intervals if spec_obj and spec_obj.intervals else [])
            ],
            "calendars": spec_obj.calendars if spec_obj and spec_obj.calendars else [],
            "cron_expressions": spec_obj.cron_expressions if spec_obj and spec_obj.cron_expressions else [],
        }
        if spec_obj
        else None,
        "state": {
            "paused": state_obj.paused if state_obj else False,
            "remaining_actions": state_obj.remaining_actions if state_obj else 0,
        }
        if state_obj
        else None,
        "action": {
            "type": type(action_obj).__name__ if action_obj else None,
            "workflow": {
                "workflow_type": action_obj.workflow if hasattr(action_obj, "workflow") else None,
                "task_queue": action_obj.task_queue if hasattr(action_obj, "task_queue") else None,
            }
            if action_obj
            else None,
        }
        if action_obj
        else None,
        "policy": {
            "overlap": str(policy_obj.overlap) if policy_obj and policy_obj.overlap else None,
            "catchup_window": str(policy_obj.catchup_window) if policy_obj and policy_obj.catchup_window else None,
            "pause_on_failure": policy_obj.pause_on_failure if policy_obj else None,
        }
        if policy_obj
        else None,
        "created_at": info_obj.created_at if info_obj else None,
        "last_updated_at": info_obj.last_updated_at if info_obj else None,
        "info": {
            "running_workflows": info_obj.running_workflows if info_obj else 0,
        }
        if info_obj
        else None,
    }
    return result


@router.get("", response_model=list[ScheduleSummaryV1])
async def list_schedules(
    _auth: AuthContext = Depends(require_permission("schedules:read")),
) -> list[ScheduleSummaryV1]:
    client = await _get_temporal_client()
    schedules: list[ScheduleSummaryV1] = []
    async for description in client.list_schedules():  # type: ignore[attr-defined]
        data = _parse_schedule_description(description)
        schedules.append(
            ScheduleSummaryV1(
                schedule_id=data["schedule_id"],
                status=data["status"],
                paused=data["paused"],
                next_action_time=data["next_action_time"],
                spec=data["spec"],
                state=data["state"],
            )
        )
    return schedules


@router.get("/{schedule_id}", response_model=ScheduleDetailV1)
async def get_schedule(
    schedule_id: str,
    _auth: AuthContext = Depends(require_permission("schedules:read")),
) -> ScheduleDetailV1:
    client = await _get_temporal_client()
    try:
        description = await client.describe_schedule(schedule_id)  # type: ignore[attr-defined]
    except Exception as exc:
        raise HTTPException(status_code=404, detail=f"Schedule not found: {schedule_id}") from exc
    data = _parse_schedule_description(description)
    return ScheduleDetailV1(**data)


@router.post("/{schedule_id}/pause", response_model=ScheduleActionResponseV1)
async def pause_schedule(
    schedule_id: str,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=200)],
    _auth: AuthContext = Depends(require_permission("schedules:manage")),
) -> ScheduleActionResponseV1:
    client = await _get_temporal_client()
    try:
        handle = client.get_schedule_handle(schedule_id)
        await handle.pause()
    except Exception as exc:
        raise HTTPException(status_code=404, detail=f"Schedule not found: {schedule_id}") from exc
    return ScheduleActionResponseV1(
        schedule_id=schedule_id,
        paused=True,
        message="Schedule paused successfully",
    )


@router.post("/{schedule_id}/resume", response_model=ScheduleActionResponseV1)
async def resume_schedule(
    schedule_id: str,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=200)],
    _auth: AuthContext = Depends(require_permission("schedules:manage")),
) -> ScheduleActionResponseV1:
    client = await _get_temporal_client()
    try:
        handle = client.get_schedule_handle(schedule_id)
        await handle.unpause()
    except Exception as exc:
        raise HTTPException(status_code=404, detail=f"Schedule not found: {schedule_id}") from exc
    return ScheduleActionResponseV1(
        schedule_id=schedule_id,
        paused=False,
        message="Schedule resumed successfully",
    )
