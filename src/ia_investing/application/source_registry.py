from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import UUID

import sqlalchemy as sa
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.agents import AuditLog
from database.models.data_foundation import DataSource, SourceLicense, SourceSLA


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

    async def register_source(
        self,
        code: str,
        name: str,
        owner_role: str,
        license_code: str,
        license_name: str,
        rate_limit_per_minute: int,
        expected_frequency_minutes: int,
        freshness_grace_minutes: int,
        correlation_id: UUID,
        *,
        terms_url: str | None = None,
        schema_version: str = "1.0",
        credential_reference: str | None = None,
    ) -> DataSource:
        license_obj = SourceLicense(
            code=license_code,
            name=license_name,
            terms_url=terms_url or "",
            permits_redistribution=False,
            retention_days=365,
        )
        self.session.add(license_obj)
        await self.session.flush()

        source = DataSource(
            code=code,
            name=name,
            schema_version=schema_version,
            owner_role=owner_role,
            base_url="",
            rate_limit_per_minute=rate_limit_per_minute,
            is_active=True,
            license_id=license_obj.id,
            credential_reference=credential_reference,
        )
        self.session.add(source)
        await self.session.flush()

        sla = SourceSLA(
            source_id=source.id,
            expected_frequency_minutes=expected_frequency_minutes,
            freshness_grace_minutes=freshness_grace_minutes,
        )
        self.session.add(sla)
        self.session.add(
            AuditLog(
                actor_type="system",
                actor_id="source-registry",
                action="source.registered",
                entity_type="data_source",
                entity_id=source.id,
                correlation_id=correlation_id,
                details={"code": code, "owner_role": owner_role, "license": license_code},
            )
        )
        await self.session.flush()
        return source

    async def update_health(
        self,
        code: str,
        *,
        last_success_at: datetime | None = None,
        last_error_code: str | None = None,
        correlation_id: UUID | None = None,
    ) -> None:
        source = (await self.session.execute(sa.select(DataSource).where(DataSource.code == code))).scalar_one_or_none()
        if source is None:
            raise LookupError(f"data source not found: {code}")
        sla = (
            await self.session.execute(sa.select(SourceSLA).where(SourceSLA.source_id == source.id))
        ).scalar_one_or_none()
        if sla is None:
            raise LookupError(f"SLA not found for source: {code}")
        now = datetime.now(UTC)
        if last_success_at is not None:
            sla.last_success_at = last_success_at
        if last_error_code is not None:
            sla.last_failure_at = now
            sla.last_error_code = last_error_code
        if correlation_id is not None:
            self.session.add(
                AuditLog(
                    actor_type="system",
                    actor_id="source-registry",
                    action="source.health_updated",
                    entity_type="data_source",
                    entity_id=source.id,
                    correlation_id=correlation_id,
                    details={
                        "code": code,
                        "last_success_at": str(last_success_at) if last_success_at else None,
                        "last_error_code": last_error_code,
                    },
                )
            )
        await self.session.flush()

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
