from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.security import AuthContext, require_permission
from database.core import get_async_session
from ia_investing.application.instruments import (
    AmbiguousInstrumentError,
    InstrumentMasterService,
    InstrumentResolutionV1,
)

router = APIRouter(prefix="/api/v1/instruments", tags=["instruments"])


@router.get("/resolve", response_model=InstrumentResolutionV1)
async def resolve_instrument(
    query: str = Query(min_length=1, max_length=300),
    as_of: date = Query(),
    _auth: AuthContext = Depends(require_permission("instruments:read")),
    session: AsyncSession = Depends(get_async_session),
) -> InstrumentResolutionV1:
    try:
        result = await InstrumentMasterService(session).resolve(query, as_of)
    except AmbiguousInstrumentError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=404, detail="Instrument or issuer not found")
    return result
