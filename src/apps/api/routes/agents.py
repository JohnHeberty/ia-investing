from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.core import get_async_session
from database.models.agents import AgentDefinition, AgentRun

router = APIRouter(prefix="/api/v1/agents", tags=["agents"])


@router.get("/runs")
async def list_agent_runs(
    agent_name: str | None = Query(None),
    status: str | None = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_async_session),
) -> list[dict[str, Any]]:
    stmt = select(AgentRun)
    if status:
        stmt = stmt.where(AgentRun.status == status)
    if agent_name:
        stmt = stmt.join(AgentDefinition, AgentRun.agent_definition_id == AgentDefinition.id)
        stmt = stmt.where(AgentDefinition.name == agent_name)
    stmt = stmt.order_by(AgentRun.started_at.desc()).offset(offset).limit(limit)
    result = await session.execute(stmt)
    rows = result.scalars().all()
    return [
        {
            "id": str(r.id),
            "status": r.status,
            "model_used": r.model_used,
            "tokens_prompt": r.tokens_prompt,
            "tokens_completion": r.tokens_completion,
            "cost_usd": r.cost_usd,
            "error_message": r.error_message,
            "started_at": r.started_at.isoformat() if r.started_at else None,
            "finished_at": r.finished_at.isoformat() if r.finished_at else None,
        }
        for r in rows
    ]


@router.get("/runs/{run_id}")
async def get_agent_run(
    run_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    stmt = select(AgentRun).where(AgentRun.id == run_id)
    result = await session.execute(stmt)
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Agent run not found")
    return {
        "id": str(row.id),
        "status": row.status,
        "input_data": row.input_data,
        "output_data": row.output_data,
        "model_used": row.model_used,
        "tokens_prompt": row.tokens_prompt,
        "tokens_completion": row.tokens_completion,
        "cost_usd": row.cost_usd,
        "error_message": row.error_message,
        "started_at": row.started_at.isoformat() if row.started_at else None,
        "finished_at": row.finished_at.isoformat() if row.finished_at else None,
    }
