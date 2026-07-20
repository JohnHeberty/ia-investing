from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from database.core import get_async_session
from ia_investing.application.agent_queries import AgentRunQueryService

router = APIRouter(prefix="/api/v1/agents", tags=["agents"])


@router.get("/runs")
async def list_agent_runs(
    agent_name: str | None = Query(None),
    status: str | None = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_async_session),
) -> list[dict[str, Any]]:
    return await AgentRunQueryService(session).list_runs(
        agent_name=agent_name, status=status, offset=offset, limit=limit
    )


@router.get("/runs/{run_id}")
async def get_agent_run(
    run_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    row = await AgentRunQueryService(session).get_run(run_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Agent run not found")
    return row
