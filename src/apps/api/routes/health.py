from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from sqlalchemy import text

from connectors.base import HttpClient
from database.core import get_async_session
from ia_investing.settings import get_settings

router = APIRouter(prefix="/api/v1/health", tags=["health"])


@router.get("")
async def deep_health() -> dict[str, Any]:
    checks: dict[str, str] = {}

    try:
        async for session in get_async_session():
            await session.execute(text("SELECT 1"))
            checks["database"] = "ok"
    except Exception as exc:
        checks["database"] = f"error: {exc}"

    settings = get_settings()
    try:
        client = HttpClient(timeout=5.0)
        await client.get_text(f"{settings.storage_endpoint}/minio/health/live")
        checks["s3"] = "ok"
    except Exception as exc:
        checks["s3"] = f"error: {exc}"

    healthy = all(v == "ok" for v in checks.values())
    return {"status": "healthy" if healthy else "degraded", "checks": checks}
