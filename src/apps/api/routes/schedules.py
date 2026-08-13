from __future__ import annotations

import asyncio
import logging
import re
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession
from temporalio.api.enums.v1 import TaskQueueType
from temporalio.api.taskqueue.v1 import TaskQueue
from temporalio.api.workflowservice.v1 import DescribeTaskQueueRequest
from temporalio.client import (
    Client,
    RPCError,
    ScheduleIntervalSpec,
    ScheduleSpec,
    ScheduleUpdate,
)

from apps.api.dependencies import get_temporal_client
from apps.api.security import AuthContext, actor_uuid, require_permission
from apps.scheduler.policy import is_managed_schedule_id
from database.core import get_async_session
from database.models.schedule_history import ScheduleRunHistory
from ia_investing.application.audit_service import AuditService
from ia_investing.settings import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/schedules", tags=["schedules"])

_reconcile_lock = asyncio.Lock()

_SCHEDULE_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")
_SCHEDULE_ID_MAX_LEN = 200


_SCHEDULE_AUDIT_MAP: dict[str, str] = {
    "trigger": "execute",
    "pause": "execute",
    "resume": "execute",
    "delete": "delete",
    "update": "update",
    "create": "create",
}


async def _log_schedule_audit(
    session: AsyncSession,
    auth: AuthContext,
    action: str,
    schedule_id: str,
    meta: dict[str, Any] | None = None,
) -> None:
    tenant_id = auth.organization_id or UUID(int=0)
    audit_action = _SCHEDULE_AUDIT_MAP.get(action, "execute")
    await AuditService(session, tenant_id).log(
        actor_id=actor_uuid(auth),
        action=audit_action,
        resource_type="schedule",
        changes=meta or {},
        metadata={"schedule_id": schedule_id, "schedule_action": action},
    )


SCHEDULE_META: dict[str, dict[str, str]] = {
    "news-collection-": {"category": "news", "description": "Coleta de noticias RSS"},
    "news-dedup-cleanup": {"category": "news", "description": "Limpeza de eventos duplicados"},
    "operation-outbox-dispatch": {"category": "operations", "description": "Dispatch do outbox de operacoes"},
    "cvm-dfp-": {"category": "data", "description": "Ingestao de dados CVM"},
    "paper-reconciliation-": {"category": "portfolio", "description": "Reconciliacao diaria de paper trading"},
    "paper-valuation-": {"category": "portfolio", "description": "Publicacao diaria de NAV"},
    "paper-rebalance-": {"category": "portfolio", "description": "Rebalance semanal de paper trading"},
    "equity-exploration-": {"category": "research", "description": "Exploration periodica de acoes"},
}


def _enrich_schedule(data: dict[str, Any]) -> dict[str, Any]:
    sid = data["schedule_id"]
    for prefix, meta in SCHEDULE_META.items():
        if sid.startswith(prefix) or sid == prefix.rstrip("-"):
            data["category"] = meta["category"]
            data["description"] = meta["description"]
            break
    else:
        data["category"] = "other"
        data["description"] = sid
    data["is_default"] = is_managed_schedule_id(sid)
    return data


class ScheduleSummaryV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schedule_id: str
    status: str
    paused: bool
    category: str = "other"
    description: str = ""
    is_default: bool = False
    next_action_time: datetime | None = None
    spec: dict[str, Any] | None = None
    state: dict[str, Any] | None = None
    running_workflows: int = 0
    last_run_at: datetime | None = None


class ScheduleDetailV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schedule_id: str
    status: str
    paused: bool
    category: str = "other"
    description: str = ""
    is_default: bool = False
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
    message: str
    triggered_at: datetime | None = None


class DeleteScheduleResponseV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schedule_id: str
    message: str


class UpdateIntervalRequestV1(BaseModel):
    every_minutes: int | None = Field(default=None, ge=1, le=10080)
    every_hours: int | None = Field(default=None, ge=1, le=720)
    every_days: int | None = Field(default=None, ge=1, le=365)


class ScheduleRunV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    schedule_id: str
    workflow_id: str | None = None
    status: str
    started_at: datetime
    finished_at: datetime | None = None
    result_summary: dict[str, Any] | None = None
    error_message: str | None = None


def _safe_get(obj: Any, attr: str, default: Any = None) -> Any:
    try:
        return getattr(obj, attr, default) if obj else default
    except AttributeError:
        return default


def _safe_str(obj: Any, attr: str) -> str | None:
    val = _safe_get(obj, attr)
    return str(val) if val else None


def _parse_schedule_description(description: Any) -> dict[str, Any]:
    sched = description.schedule
    spec_obj = _safe_get(sched, "spec")
    state_obj = _safe_get(sched, "state")
    action_obj = _safe_get(sched, "action")
    policy_obj = _safe_get(sched, "policy")
    info_obj = _safe_get(description, "info")

    paused = _safe_get(state_obj, "paused", False) if state_obj else False

    next_action_time = None
    schedule_state = _safe_get(description, "schedule_state")
    if schedule_state and _safe_get(schedule_state, "next_action_time"):
        next_action_time = schedule_state.next_action_time
    elif info_obj and _safe_get(info_obj, "next_action_times"):
        next_action_time = info_obj.next_action_times[0] if info_obj.next_action_times else None

    intervals = []
    raw_intervals = _safe_get(spec_obj, "intervals") if spec_obj else None
    if raw_intervals:
        for interval in raw_intervals:
            intervals.append(
                {
                    "every": str(interval.every),
                    "offset": str(interval.offset) if interval.offset else None,
                }
            )

    result: dict[str, Any] = {
        "schedule_id": description.id,
        "status": _safe_get(description, "status", "running"),
        "paused": paused,
        "next_action_time": next_action_time,
        "spec": {
            "intervals": intervals,
            "calendars": list(_safe_get(spec_obj, "calendars", []) or []),
            "cron_expressions": list(_safe_get(spec_obj, "cron_expressions", []) or []),
        }
        if spec_obj
        else None,
        "state": {
            "paused": paused,
            "remaining_actions": _safe_get(state_obj, "remaining_actions", 0),
        }
        if state_obj
        else None,
        "action": {
            "type": type(action_obj).__name__ if action_obj else None,
            "workflow": {
                "workflow_type": _safe_get(action_obj, "workflow"),
                "task_queue": _safe_get(action_obj, "task_queue"),
            }
            if action_obj
            else None,
        }
        if action_obj
        else None,
        "policy": {
            "overlap": _safe_str(policy_obj, "overlap"),
            "catchup_window": _safe_str(policy_obj, "catchup_window"),
            "pause_on_failure": _safe_get(policy_obj, "pause_on_failure"),
        }
        if policy_obj
        else None,
        "created_at": _safe_get(info_obj, "created_at"),
        "last_updated_at": _safe_get(info_obj, "last_updated_at"),
        "last_run_at": None,
        "info": {"running_workflows": len(_safe_get(info_obj, "running_actions", []) or [])} if info_obj else None,
    }

    recent_actions = _safe_get(info_obj, "recent_actions", []) if info_obj else []
    if recent_actions:
        last_action = recent_actions[-1]
        result["last_run_at"] = _safe_get(last_action, "started_at")

    return result


def _validate_schedule_id(schedule_id: str) -> str:
    if not schedule_id or len(schedule_id) > _SCHEDULE_ID_MAX_LEN:
        raise HTTPException(status_code=422, detail="Invalid schedule_id length")
    if not _SCHEDULE_ID_PATTERN.match(schedule_id):
        raise HTTPException(status_code=422, detail="schedule_id must match [a-zA-Z0-9_-]+")
    return schedule_id


def _handle_temporal_error(exc: Exception, schedule_id: str) -> None:
    if isinstance(exc, RPCError):
        from temporalio.service import RPCStatusCode

        status = exc.status
        status_name = getattr(status, "name", str(status)).lower()
        if status == RPCStatusCode.NOT_FOUND or status_name == "not_found":
            raise HTTPException(status_code=404, detail=f"Schedule not found: {schedule_id}") from exc
        if status == RPCStatusCode.ALREADY_EXISTS or status_name == "already_exists":
            raise HTTPException(status_code=409, detail=f"Schedule already exists: {schedule_id}") from exc
        if status in (RPCStatusCode.DEADLINE_EXCEEDED, RPCStatusCode.UNAVAILABLE) or status_name in {
            "deadline_exceeded",
            "unavailable",
        }:
            raise HTTPException(status_code=503, detail=f"Temporal unavailable: {exc.status}") from exc
        raise HTTPException(status_code=502, detail=f"Temporal RPC error: {exc.status}") from exc
    logger.exception("Unexpected error for schedule %s", schedule_id)
    raise HTTPException(status_code=500, detail="Internal server error") from exc


@router.get("", response_model=list[ScheduleSummaryV1])
async def list_schedules(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    _auth: AuthContext = Depends(require_permission("schedules:read")),
    client: Client = Depends(get_temporal_client),
) -> list[ScheduleSummaryV1]:
    all_schedules: list[ScheduleSummaryV1] = []
    all_raw: list[dict[str, Any]] = []
    iterator = await client.list_schedules()
    async for description in iterator:
        data = _enrich_schedule(_parse_schedule_description(description))
        all_raw.append(data)
        summary = ScheduleSummaryV1(
            schedule_id=data["schedule_id"],
            status=data["status"],
            paused=data["paused"],
            category=data["category"],
            description=data["description"],
            is_default=data["is_default"],
            next_action_time=data.get("next_action_time"),
            spec=data.get("spec"),
            state=data.get("state"),
            running_workflows=data.get("info", {}).get("running_workflows", 0) if data.get("info") else 0,
            last_run_at=data.get("last_run_at"),
        )
        all_schedules.append(summary)
    all_schedules.sort(key=lambda s: (s.category, s.schedule_id))
    total = len(all_schedules)
    sliced = all_schedules[offset : offset + limit]
    logger.info("Listed %d schedules (offset=%d, limit=%d, total=%d)", len(sliced), offset, limit, total)
    return sliced


class ReconcileResponseV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    created: list[str]
    updated: list[str]
    deleted: list[str]
    total: int


@router.post("/reconcile", response_model=ReconcileResponseV1)
async def reconcile_schedules_endpoint(
    auth: AuthContext = Depends(require_permission("schedules:manage")),
    client: Client = Depends(get_temporal_client),
    session: AsyncSession = Depends(get_async_session),
) -> ReconcileResponseV1:
    if _reconcile_lock.locked():
        raise HTTPException(status_code=409, detail="Reconcile already in progress")

    async with _reconcile_lock:
        from apps.scheduler.temporal_schedules import reconcile_configured_schedules

        results = await reconcile_configured_schedules(client=client, settings=get_settings())

    await _log_schedule_audit(session, auth, "update", "managed-schedules", {"results": results})
    await session.commit()

    created = [k for k, v in results.items() if v == "created"]
    updated = [k for k, v in results.items() if v == "updated"]
    deleted = [k for k, v in results.items() if v == "deleted"]
    logger.info("Reconciled schedules: %d created, %d updated, %d deleted", len(created), len(updated), len(deleted))
    return ReconcileResponseV1(created=created, updated=updated, deleted=deleted, total=len(results))


@router.get("/{schedule_id}", response_model=ScheduleDetailV1)
async def get_schedule(
    schedule_id: str,
    _auth: AuthContext = Depends(require_permission("schedules:read")),
    client: Client = Depends(get_temporal_client),
) -> ScheduleDetailV1:
    _validate_schedule_id(schedule_id)
    description = None
    try:
        handle = client.get_schedule_handle(schedule_id)
        description = await handle.describe()
    except Exception as exc:
        _handle_temporal_error(exc, schedule_id)
    if description is None:
        raise HTTPException(status_code=404, detail="schedule not found")
    data = _enrich_schedule(_parse_schedule_description(description))
    return ScheduleDetailV1(**data)


@router.post("/{schedule_id}/pause", response_model=ScheduleActionResponseV1)
async def pause_schedule(
    schedule_id: str,
    _auth: AuthContext = Depends(require_permission("schedules:manage")),
    client: Client = Depends(get_temporal_client),
    session: AsyncSession = Depends(get_async_session),
) -> ScheduleActionResponseV1:
    _validate_schedule_id(schedule_id)
    try:
        handle = client.get_schedule_handle(schedule_id)
        await handle.pause()
    except Exception as exc:
        _handle_temporal_error(exc, schedule_id)
    await _log_schedule_audit(session, _auth, "pause", schedule_id)
    await session.commit()
    logger.info("Paused schedule %s", schedule_id)
    return ScheduleActionResponseV1(schedule_id=schedule_id, message="Schedule paused successfully")


@router.post("/{schedule_id}/resume", response_model=ScheduleActionResponseV1)
async def resume_schedule(
    schedule_id: str,
    _auth: AuthContext = Depends(require_permission("schedules:manage")),
    client: Client = Depends(get_temporal_client),
    session: AsyncSession = Depends(get_async_session),
) -> ScheduleActionResponseV1:
    _validate_schedule_id(schedule_id)
    try:
        handle = client.get_schedule_handle(schedule_id)
        await handle.unpause()
    except Exception as exc:
        _handle_temporal_error(exc, schedule_id)
    await _log_schedule_audit(session, _auth, "resume", schedule_id)
    await session.commit()
    logger.info("Resumed schedule %s", schedule_id)
    return ScheduleActionResponseV1(schedule_id=schedule_id, message="Schedule resumed successfully")


@router.put("/{schedule_id}/update-interval", response_model=ScheduleActionResponseV1)
async def update_schedule_interval(
    schedule_id: str,
    body: UpdateIntervalRequestV1,
    _auth: AuthContext = Depends(require_permission("schedules:manage")),
    client: Client = Depends(get_temporal_client),
    session: AsyncSession = Depends(get_async_session),
) -> ScheduleActionResponseV1:
    _validate_schedule_id(schedule_id)
    if is_managed_schedule_id(schedule_id):
        raise HTTPException(status_code=409, detail="Managed schedule interval is controlled by configuration")
    if body.every_minutes is not None:
        every = timedelta(minutes=body.every_minutes)
    elif body.every_hours is not None:
        every = timedelta(hours=body.every_hours)
    elif body.every_days is not None:
        every = timedelta(days=body.every_days)
    else:
        raise HTTPException(status_code=400, detail="Provide every_minutes, every_hours, or every_days")

    try:
        handle = client.get_schedule_handle(schedule_id)

        async def _updater(_input: Any) -> ScheduleUpdate:
            sched = _input.description.schedule
            old_spec = sched.spec
            new_intervals = [ScheduleIntervalSpec(every=every)]
            sched.spec = ScheduleSpec(
                intervals=new_intervals,
                calendars=list(getattr(old_spec, "calendars", []) or []) if old_spec else [],
                cron_expressions=list(getattr(old_spec, "cron_expressions", []) or []) if old_spec else [],
            )
            return ScheduleUpdate(sched)

        await handle.update(_updater)
    except Exception as exc:
        _handle_temporal_error(exc, schedule_id)
    await _log_schedule_audit(session, _auth, "update", schedule_id, {"interval": str(every)})
    await session.commit()
    logger.info("Updated interval for schedule %s to %s", schedule_id, every)
    return ScheduleActionResponseV1(schedule_id=schedule_id, message=f"Interval updated to {every}")


@router.post("/{schedule_id}/trigger", response_model=ScheduleActionResponseV1)
async def trigger_schedule(
    schedule_id: str,
    _auth: AuthContext = Depends(require_permission("schedules:manage")),
    client: Client = Depends(get_temporal_client),
    session: AsyncSession = Depends(get_async_session),
) -> ScheduleActionResponseV1:
    _validate_schedule_id(schedule_id)
    triggered_at = datetime.now(UTC)
    try:
        handle = client.get_schedule_handle(schedule_id)
        description = await handle.describe()
        running_actions = _safe_get(_safe_get(description, "info"), "running_actions", []) or []
        if running_actions:
            raise HTTPException(
                status_code=409,
                detail=f"Schedule already has a running workflow: {schedule_id}",
            )

        action = _safe_get(_safe_get(description, "schedule"), "action")
        task_queue = _safe_get(action, "task_queue")
        if task_queue:
            pollers = await client.workflow_service.describe_task_queue(
                DescribeTaskQueueRequest(
                    namespace=client.namespace,
                    task_queue=TaskQueue(name=task_queue),
                    task_queue_type=TaskQueueType.TASK_QUEUE_TYPE_WORKFLOW,
                )
            )
            if not pollers.pollers:
                raise HTTPException(
                    status_code=503,
                    detail=f"No worker is polling task queue: {task_queue}",
                )
        await handle.trigger()
    except HTTPException:
        raise
    except Exception as exc:
        _handle_temporal_error(exc, schedule_id)
    await _log_schedule_audit(session, _auth, "trigger", schedule_id)
    await session.commit()
    logger.info("Triggered schedule %s", schedule_id)
    return ScheduleActionResponseV1(
        schedule_id=schedule_id,
        message="Schedule triggered successfully",
        triggered_at=triggered_at,
    )


@router.delete("/{schedule_id}", response_model=DeleteScheduleResponseV1)
async def delete_schedule(
    schedule_id: str,
    _auth: AuthContext = Depends(require_permission("schedules:manage")),
    client: Client = Depends(get_temporal_client),
    session: AsyncSession = Depends(get_async_session),
) -> DeleteScheduleResponseV1:
    _validate_schedule_id(schedule_id)
    if is_managed_schedule_id(schedule_id):
        raise HTTPException(status_code=409, detail="Managed schedules cannot be deleted")
    try:
        handle = client.get_schedule_handle(schedule_id)
        await handle.delete()
    except Exception as exc:
        _handle_temporal_error(exc, schedule_id)
    await _log_schedule_audit(session, _auth, "delete", schedule_id)
    await session.commit()
    logger.info("Deleted schedule %s", schedule_id)
    return DeleteScheduleResponseV1(schedule_id=schedule_id, message="Schedule deleted successfully")


@router.get("/{schedule_id}/runs", response_model=list[ScheduleRunV1])
async def get_schedule_runs(
    schedule_id: str,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    _auth: AuthContext = Depends(require_permission("schedules:read")),
    session: AsyncSession = Depends(get_async_session),
) -> list[ScheduleRunV1]:
    _validate_schedule_id(schedule_id)
    result = await session.execute(
        sa.select(ScheduleRunHistory)
        .where(ScheduleRunHistory.schedule_id == schedule_id)
        .order_by(ScheduleRunHistory.started_at.desc())
        .offset(offset)
        .limit(limit)
    )
    return [
        ScheduleRunV1(
            id=str(run.id),
            schedule_id=run.schedule_id,
            workflow_id=run.workflow_id,
            status=run.status,
            started_at=run.started_at,
            finished_at=run.finished_at,
            result_summary=run.result_summary,
            error_message=run.error_message,
        )
        for run in result.scalars()
    ]
