from __future__ import annotations

import json
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.audit import AuditLogEntry


class AuditService:
    def __init__(self, session: AsyncSession, tenant_id: UUID) -> None:
        self._session = session
        self._tenant_id = tenant_id

    async def log(
        self,
        actor_id: UUID | None,
        action: str,
        resource_type: str,
        resource_id: UUID | None = None,
        changes: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AuditLogEntry:
        await self._session.execute(
            sa.text("SELECT pg_advisory_xact_lock(hashtext(:tid))"), {"tid": str(self._tenant_id)}
        )
        await self._session.flush()
        prev_hash = await self._get_latest_hash()
        now = datetime.now(UTC)

        meta = metadata or {}
        raw = (
            str(prev_hash or "")
            + now.isoformat()
            + str(actor_id or "")
            + action
            + resource_type
            + str(resource_id or "")
            + json.dumps(changes or {}, sort_keys=True)
            + json.dumps(meta, sort_keys=True)
        )
        entry_hash = sha256(raw.encode("utf-8")).hexdigest()

        entry = AuditLogEntry(
            tenant_id=self._tenant_id,
            actor_id=actor_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            changes=changes,
            meta_data=meta,
            hash_prev=prev_hash,
            hash=entry_hash,
            timestamp=now,
            created_at=now,
        )
        self._session.add(entry)
        return entry

    async def _get_latest_hash(self) -> str | None:
        result = await self._session.execute(
            sa.select(AuditLogEntry.hash)
            .where(AuditLogEntry.tenant_id == self._tenant_id)
            .order_by(AuditLogEntry.timestamp.desc(), AuditLogEntry.id.desc())
            .limit(1)
        )
        row = result.scalar_one_or_none()
        return row

    async def query(
        self,
        *,
        actor_id: UUID | None = None,
        action: str | None = None,
        resource_type: str | None = None,
        resource_id: UUID | None = None,
        from_time: datetime | None = None,
        to_time: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[AuditLogEntry], int]:
        stmt = sa.select(AuditLogEntry).where(AuditLogEntry.tenant_id == self._tenant_id)

        if actor_id is not None:
            stmt = stmt.where(AuditLogEntry.actor_id == actor_id)
        if action is not None:
            stmt = stmt.where(AuditLogEntry.action == action)
        if resource_type is not None:
            stmt = stmt.where(AuditLogEntry.resource_type == resource_type)
        if resource_id is not None:
            stmt = stmt.where(AuditLogEntry.resource_id == resource_id)
        if from_time is not None:
            stmt = stmt.where(AuditLogEntry.timestamp >= from_time)
        if to_time is not None:
            stmt = stmt.where(AuditLogEntry.timestamp <= to_time)

        count_stmt = sa.select(sa.func.count()).select_from(stmt.subquery())
        total = await self._session.scalar(count_stmt) or 0

        stmt = stmt.order_by(AuditLogEntry.timestamp.desc()).offset(offset).limit(limit)
        result = await self._session.execute(stmt)
        rows = list(result.scalars().all())
        return rows, total

    async def get_by_id(self, entry_id: UUID) -> AuditLogEntry | None:
        stmt = sa.select(AuditLogEntry).where(
            AuditLogEntry.id == entry_id,
            AuditLogEntry.tenant_id == self._tenant_id,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def verify_chain(
        self,
        from_id: UUID | None = None,
        to_id: UUID | None = None,
    ) -> list[dict[str, Any]]:
        stmt = (
            sa.select(AuditLogEntry)
            .where(AuditLogEntry.tenant_id == self._tenant_id)
            .order_by(AuditLogEntry.timestamp.asc(), AuditLogEntry.id.asc())
        )
        if from_id is not None:
            stmt = stmt.where(AuditLogEntry.id >= from_id)
        if to_id is not None:
            stmt = stmt.where(AuditLogEntry.id <= to_id)

        result = await self._session.execute(stmt)
        entries = list(result.scalars().all())

        tampered: list[dict[str, Any]] = []
        for i, entry in enumerate(entries):
            expected_hash = self._compute_entry_hash(entry, entries[i - 1] if i > 0 else None)
            if entry.hash != expected_hash:
                tampered.append(
                    {
                        "id": str(entry.id),
                        "expected_hash": expected_hash,
                        "stored_hash": entry.hash,
                        "reason": "hash_mismatch",
                    }
                )
            if i > 0 and entry.hash_prev != entries[i - 1].hash:
                tampered.append(
                    {
                        "id": str(entry.id),
                        "expected_hash_prev": entries[i - 1].hash,
                        "stored_hash_prev": entry.hash_prev,
                        "reason": "broken_link",
                    }
                )

        return tampered

    async def get_tamper_evidence(self) -> list[dict[str, Any]]:
        return await self.verify_chain()

    def _compute_entry_hash(self, entry: AuditLogEntry, prev: AuditLogEntry | None) -> str:
        raw = (
            str(prev.hash if prev else "")
            + entry.timestamp.isoformat()
            + str(entry.actor_id or "")
            + entry.action
            + entry.resource_type
            + str(entry.resource_id or "")
            + json.dumps(entry.changes or {}, sort_keys=True)
            + json.dumps(entry.meta_data or {}, sort_keys=True)
        )
        return sha256(raw.encode("utf-8")).hexdigest()
