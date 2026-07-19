from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.core import get_async_session
from database.models.catalog import Issuer, Sector

router = APIRouter(prefix="/api/v1/issuers", tags=["issuers"])


def _issuer_to_dict(row: Issuer) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "name_pt": row.name_pt,
        "cnpj": row.cnpj,
        "cvm_code": row.cvm_code,
        "industry_id": str(row.industry_id) if row.industry_id else None,
        "website_ri_url": row.website_ri_url,
        "is_active": row.is_active,
    }


@router.get("/cnpj/{cnpj}")
async def get_issuer_by_cnpj(
    cnpj: str,
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    stmt = select(Issuer).where(Issuer.cnpj == cnpj)
    result = await session.execute(stmt)
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Issuer not found")
    return _issuer_to_dict(row)


@router.get("/{issuer_id}")
async def get_issuer(
    issuer_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    stmt = select(Issuer).where(Issuer.id == issuer_id)
    result = await session.execute(stmt)
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Issuer not found")
    return _issuer_to_dict(row)


@router.get("")
async def list_issuers(
    sector: str | None = Query(None, description="Filter by sector name (pt)"),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_async_session),
) -> list[dict[str, Any]]:
    stmt = select(Issuer).where(Issuer.is_active.is_(True))
    if sector:
        stmt = (
            stmt.join(Issuer.industry)
            .join(Sector)
            .where(Sector.name_pt.ilike(f"%{sector}%"))
        )
    stmt = stmt.order_by(Issuer.name_pt).offset(offset).limit(limit)
    result = await session.execute(stmt)
    rows = result.scalars().all()
    return [
        {
            "id": str(r.id),
            "name_pt": r.name_pt,
            "cnpj": r.cnpj,
            "cvm_code": r.cvm_code,
            "website_ri_url": r.website_ri_url,
        }
        for r in rows
    ]
