from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agents import ALL_AGENTS, AgentRunner
from agents._config import AgentConfig
from database.core import get_async_session
from database.models.agents import AgentDefinition, AgentRun

router = APIRouter(prefix="/api/v1/agents", tags=["agents"])


class AgentRunRequest(BaseModel):
    agent_name: str
    input_data: dict[str, Any]


def _get_agent_config(agent_name: str) -> AgentConfig:
    if agent_name not in ALL_AGENTS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown agent '{agent_name}'. Available: {list(ALL_AGENTS.keys())}",
        )
    return ALL_AGENTS[agent_name]


@router.post("/runs", status_code=201)
async def run_agent(
    body: AgentRunRequest,
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    config = _get_agent_config(body.agent_name)
    runner = AgentRunner(config)

    agent_def = (await session.execute(
        select(AgentDefinition).where(AgentDefinition.name == body.agent_name)
    )).scalar_one_or_none()
    if agent_def is None:
        raise HTTPException(status_code=404, detail=f"AgentDefinition '{body.agent_name}' not found in DB")

    agent_run = AgentRun(
        agent_definition_id=agent_def.id,
        input_data=body.input_data,
        status="running",
    )
    session.add(agent_run)
    await session.flush()

    try:
        result = await runner.run(body.input_data)
    except Exception as exc:
        agent_run.status = "failed"
        agent_run.error_message = str(exc)
        await session.flush()
        raise

    agent_run.status = result.status
    agent_run.output_data = result.output_data if isinstance(result.output_data, dict) else {"raw": result.output_data}
    agent_run.model_used = result.model_used
    agent_run.tokens_prompt = result.tokens_prompt
    agent_run.tokens_completion = result.tokens_completion
    agent_run.cost_usd = result.cost_usd
    agent_run.error_message = result.error_message
    await session.flush()

    return {
        "id": str(agent_run.id),
        "agent_name": body.agent_name,
        "status": result.status,
        "output_data": agent_run.output_data,
        "model_used": result.model_used,
        "tokens_prompt": result.tokens_prompt,
        "tokens_completion": result.tokens_completion,
        "cost_usd": result.cost_usd,
        "duration_ms": result.duration_ms,
    }


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
