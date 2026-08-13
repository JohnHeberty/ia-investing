from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from ia_investing.application.audit_service import AuditService
from ia_investing.logging_config import get_log_context


class AuditMixin:
    async def _audit(
        self,
        session: AsyncSession,
        tenant_id: UUID | None,
        actor_id: UUID | None,
        action: str,
        resource_type: str,
        resource_id: UUID | None = None,
        changes: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        if tenant_id is None:
            raise ValueError("organization context is required for audit logging")
        ctx = get_log_context()
        merged_meta: dict[str, Any] = {**(metadata or {})}
        for key in ("request_id", "trace_id", "ip", "user_agent", "http_method", "http_path", "duration_ms"):
            if ctx.get(key) is not None:
                merged_meta[key] = ctx[key]

        svc = AuditService(session, tenant_id)
        await svc.log(
            actor_id=actor_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            changes=changes,
            metadata=merged_meta,
        )
