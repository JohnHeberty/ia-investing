from __future__ import annotations

import uuid
from typing import Any

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.agents import AgentDefinition, AgentRun


class AgentRunQueryService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_runs(
        self,
        agent_name: str | None = None,
        status: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        stmt = sa.select(AgentRun)
        if status:
            stmt = stmt.where(AgentRun.status == status)
        if agent_name:
            stmt = stmt.join(AgentDefinition, AgentRun.agent_definition_id == AgentDefinition.id)
            stmt = stmt.where(AgentDefinition.name == agent_name)
        stmt = stmt.order_by(AgentRun.started_at.desc()).offset(offset).limit(limit)
        result = await self._session.execute(stmt)
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
                "started_at": r.started_at.isoformat() if r.started_at is not None else None,
                "finished_at": r.finished_at.isoformat() if r.finished_at is not None else None,
            }
            for r in rows
        ]

    async def get_run(self, run_id: uuid.UUID) -> dict[str, Any] | None:
        stmt = sa.select(AgentRun).where(AgentRun.id == run_id)
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return None
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
            "started_at": row.started_at.isoformat() if row.started_at is not None else None,
            "finished_at": row.finished_at.isoformat() if row.finished_at is not None else None,
        }
