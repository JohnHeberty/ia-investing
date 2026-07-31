from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict
from sqlalchemy import text

from connectors.base import HttpClient
from database.core import session_scope
from ia_investing.market_data import get_cache_stats
from ia_investing.settings import get_settings

router = APIRouter(prefix="/api/v1/health", tags=["health"])


class HealthCheckResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: str
    checks: dict[str, str]


@router.get("", response_model=HealthCheckResponse)
async def deep_health() -> HealthCheckResponse:
    checks: dict[str, str] = {}

    try:
        async with session_scope() as session:
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
    return HealthCheckResponse(status="healthy" if healthy else "degraded", checks=checks)


@router.get("/cache")
async def cache_stats() -> dict[str, dict[str, Any]]:
    """Return market data cache statistics."""
    return get_cache_stats()
