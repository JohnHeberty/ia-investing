from __future__ import annotations

import time
from collections import defaultdict
from typing import Any

import structlog
from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/v1/events", tags=["events"])

logger = structlog.get_logger("events")

_rate_buckets: dict[str, list[float]] = defaultdict(list)
_RATE_LIMIT = 100
_RATE_WINDOW = 60.0


class TelemetryEvent(BaseModel):
    event: str
    target: str | None = None
    path: str
    timestamp: int
    metadata: dict[str, Any] | None = None


class EventBatch(BaseModel):
    events: list[TelemetryEvent] = Field(max_length=100)


@router.post("")
async def ingest_events(body: EventBatch, request: Request) -> dict[str, str]:
    ip = request.client.host if request.client else "unknown"
    now = time.monotonic()
    bucket = _rate_buckets[ip]
    bucket[:] = [t for t in bucket if now - t < _RATE_WINDOW]
    if len(bucket) >= _RATE_LIMIT:
        return {"status": "rate_limited", "count": "0"}
    bucket.append(now)

    for ev in body.events:
        logger.info(
            "telemetry_event",
            event_type=ev.event,
            target=ev.target,
            path=ev.path,
            timestamp=ev.timestamp,
        )
    return {"status": "accepted", "count": str(len(body.events))}
