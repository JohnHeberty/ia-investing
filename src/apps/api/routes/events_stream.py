"""Server-Sent Events endpoint for real-time notifications."""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncGenerator
from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from apps.api.security import AuthContext, get_auth_context

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/events-stream", tags=["events-stream"])


async def event_generator() -> AsyncGenerator[str, None]:
    """Generate SSE events."""
    while True:
        yield (f"data: {json.dumps({'type': 'heartbeat', 'timestamp': datetime.now(UTC).isoformat()})}\n\n")
        await asyncio.sleep(30)


@router.get("/stream")
async def stream_events(
    _auth: AuthContext = Depends(get_auth_context),
) -> StreamingResponse:
    """Stream real-time events via SSE."""
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
