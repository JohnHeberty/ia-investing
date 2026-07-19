from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.security import AuthContext, require_permission
from database.core import get_async_session
from ia_investing.application.metrics import MetricBundleV1, MetricService

router = APIRouter(prefix="/api/v1/metrics", tags=["metrics"])


@router.get("/{metric_name}", response_model=MetricBundleV1)
async def calculate_metric(
    metric_name: str,
    issuer_id: UUID = Query(),
    reporting_period_id: UUID = Query(),
    as_of: datetime = Query(),
    _auth: AuthContext = Depends(require_permission("metrics:read")),
    session: AsyncSession = Depends(get_async_session),
) -> MetricBundleV1:
    try:
        return await MetricService(session).calculate(metric_name, issuer_id, reporting_period_id, as_of)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
