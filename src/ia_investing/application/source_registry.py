from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Literal

import sqlalchemy as sa
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.data_foundation import DataSource, SourceSLA


class SourceHealthV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    code: str
    name: str
    source_schema_version: str
    owner_role: str
    status: Literal["healthy", "stale", "never_succeeded", "inactive"]
    last_success_at: datetime | None
    last_failure_at: datetime | None
    freshness_due_at: datetime | None
    last_error_code: str | None


class SourceRegistryService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_health(self, now: datetime | None = None) -> list[SourceHealthV1]:
        effective_now = now or datetime.now(UTC)
        rows = (
            await self.session.execute(
                sa.select(DataSource, SourceSLA).outerjoin(SourceSLA, SourceSLA.source_id == DataSource.id)
            )
        ).all()
        result: list[SourceHealthV1] = []
        for source, sla in rows:
            due_at = None
            if sla and sla.last_success_at:
                due_at = sla.last_success_at + timedelta(
                    minutes=sla.expected_frequency_minutes + sla.freshness_grace_minutes
                )
            if not source.is_active:
                status = "inactive"
            elif not sla or not sla.last_success_at:
                status = "never_succeeded"
            elif due_at and due_at < effective_now:
                status = "stale"
            else:
                status = "healthy"
            result.append(
                SourceHealthV1(
                    code=source.code,
                    name=source.name,
                    source_schema_version=source.schema_version,
                    owner_role=source.owner_role,
                    status=status,
                    last_success_at=sla.last_success_at if sla else None,
                    last_failure_at=sla.last_failure_at if sla else None,
                    freshness_due_at=due_at,
                    last_error_code=sla.last_error_code if sla else None,
                )
            )
        return result
