from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.core import get_async_session
from database.models.financials import FinancialMetric, FinancialStatement

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
    stmt = select(FinancialMetric).where(FinancialMetric.issuer_id == issuer_id)
    if metric_name:
        stmt = stmt.where(FinancialMetric.metric_name == metric_name)
    if period:
        stmt = stmt.where(FinancialMetric.reporting_period_end == date.fromisoformat(period))
    stmt = stmt.order_by(FinancialMetric.reporting_period_end.desc()).offset(offset).limit(limit)
    result = await session.execute(stmt)
    rows = result.scalars().all()
    return [
        {
            "id": str(r.id),
            "issuer_id": str(r.issuer_id),
            "metric_name": r.metric_name,
            "category": r.category,
            "value": float(r.value) if r.value is not None else None,
            "unit": r.unit,
            "reporting_period_end": str(r.reporting_period_end),
            "previous_value": float(r.previous_value) if r.previous_value is not None else None,
            "change_percent": float(r.change_percent) if r.change_percent is not None else None,
        }
        for r in rows
    ]


@router.get("/statements")
async def get_statements(
    issuer_id: uuid.UUID,
    statement_type: str | None = Query(None, description="DRE, BALANCE_SHEET, CASH_FLOW"),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_async_session),
) -> list[dict[str, Any]]:
    stmt = select(FinancialStatement).where(FinancialStatement.issuer_id == issuer_id)
    if statement_type:
        stmt = stmt.where(FinancialStatement.statement_type == statement_type)
    stmt = stmt.order_by(FinancialStatement.reporting_period_end.desc()).offset(offset).limit(limit)
    result = await session.execute(stmt)
    rows = result.scalars().all()
    return [
        {
            "id": str(r.id),
            "issuer_id": str(r.issuer_id),
            "statement_type": r.statement_type,
            "reporting_period_start": str(r.reporting_period_start),
            "reporting_period_end": str(r.reporting_period_end),
            "currency_code": r.currency_code,
            "scale_factor": r.scale_factor,
            "is_audited": r.is_audited,
            "line_items": r.line_items,
        }
        for r in rows
    ]
