from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from database.core import get_async_session
from ia_investing.application.financial_statements import FinancialStatementService

router = APIRouter(prefix="/api/v1/financials", tags=["financials"])


@router.get("/metrics")
async def get_metrics(
    issuer_id: uuid.UUID,
    metric_name: str | None = Query(None),
    period: str | None = Query(None, description="YYYY-MM-DD"),
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    session: AsyncSession = Depends(get_async_session),
) -> list[dict[str, Any]]:
    return await FinancialStatementService(session).list_metrics(
        issuer_id=issuer_id,
        metric_name=metric_name,
        period=period,
        offset=offset,
        limit=limit,
    )


@router.get("/statements")
async def get_statements(
    issuer_id: uuid.UUID,
    statement_type: str | None = Query(None, description="DRE, BALANCE_SHEET, CASH_FLOW"),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_async_session),
) -> list[dict[str, Any]]:
    return await FinancialStatementService(session).list_statements(
        issuer_id=issuer_id,
        statement_type=statement_type,
        offset=offset,
        limit=limit,
    )
