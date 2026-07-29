from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api._errors import map_error
from apps.api.security import AuthContext, require_permission
from database.core import get_async_session
from ia_investing.application.catalog import IssuerCatalogService

router = APIRouter(prefix="/api/v1/issuers", tags=["issuers"])


@router.get("/cnpj/{cnpj}", response_model=dict[str, Any])
async def get_issuer_by_cnpj(
    cnpj: str,
    auth: AuthContext = Depends(require_permission("issuers:read")),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    row = await IssuerCatalogService(session).get_by_cnpj(cnpj)
    if row is None:
        raise map_error(LookupError("Issuer not found"))
    return row


@router.get("/{issuer_id}", response_model=dict[str, Any])
async def get_issuer(
    issuer_id: uuid.UUID,
    auth: AuthContext = Depends(require_permission("issuers:read")),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    row = await IssuerCatalogService(session).get_by_id(issuer_id)
    if row is None:
        raise map_error(LookupError("Issuer not found"))
    return row


@router.get("", response_model=list[dict[str, Any]])
async def list_issuers(
    sector: str | None = Query(None, description="Filter by sector name (pt)"),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    auth: AuthContext = Depends(require_permission("issuers:read")),
    session: AsyncSession = Depends(get_async_session),
) -> list[dict[str, Any]]:
    return await IssuerCatalogService(session).list_active(sector=sector, offset=offset, limit=limit)
