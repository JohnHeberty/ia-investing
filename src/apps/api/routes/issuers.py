from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from database.core import get_async_session
from ia_investing.application.catalog import IssuerCatalogService

router = APIRouter(prefix="/api/v1/issuers", tags=["issuers"])


@router.get("/cnpj/{cnpj}")
async def get_issuer_by_cnpj(
    cnpj: str,
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    row = await IssuerCatalogService(session).get_by_cnpj(cnpj)
    if row is None:
        raise HTTPException(status_code=404, detail="Issuer not found")
    return row


@router.get("/{issuer_id}")
async def get_issuer(
    issuer_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    row = await IssuerCatalogService(session).get_by_id(issuer_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Issuer not found")
    return row


@router.get("")
async def list_issuers(
    sector: str | None = Query(None, description="Filter by sector name (pt)"),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_async_session),
) -> list[dict[str, Any]]:
    return await IssuerCatalogService(session).list_active(sector=sector, offset=offset, limit=limit)
