from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.security import AuthContext, require_permission
from database.core import get_async_session
from ia_investing.application.source_registry import SourceHealthV1, SourceRegistryService

router = APIRouter(prefix="/api/v1/sources", tags=["sources"])


@router.get("/health", response_model=list[SourceHealthV1])
async def list_source_health(
    _auth: AuthContext = Depends(require_permission("sources:read")),
    session: AsyncSession = Depends(get_async_session),
) -> list[SourceHealthV1]:
    return await SourceRegistryService(session).list_health()
