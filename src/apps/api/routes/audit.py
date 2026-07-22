from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from apps.api.dependencies import get_audit_service
from apps.api.security import AuthContext, require_permission
from ia_investing.application.audit_service import AuditService

router = APIRouter(prefix="/api/v1/audit", tags=["audit"])


class AuditEntryV1(BaseModel):
    id: UUID
    tenant_id: UUID
    actor_id: UUID | None
    action: str
    resource_type: str
    resource_id: UUID | None
    changes: dict | None
    metadata: dict
    hash_prev: str | None
    hash: str
    timestamp: datetime
    created_at: datetime


class AuditLogQueryV1(BaseModel):
    items: list[AuditEntryV1]
    total: int
    limit: int
    offset: int


class ChainVerificationResultV1(BaseModel):
    tampered_entries: list[dict]
    verified: bool


@router.get("/logs", response_model=AuditLogQueryV1)
async def query_audit_logs(
    actor_id: UUID | None = Query(default=None),
    action: str | None = Query(default=None),
    resource_type: str | None = Query(default=None),
    resource_id: UUID | None = Query(default=None),
    from_time: datetime | None = Query(default=None),
    to_time: datetime | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    _auth: AuthContext = Depends(require_permission("audit:read")),
    service: AuditService = Depends(get_audit_service),
) -> AuditLogQueryV1:
    items, total = await service.query(
        actor_id=actor_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        from_time=from_time,
        to_time=to_time,
        limit=limit,
        offset=offset,
    )
    return AuditLogQueryV1(
        items=[AuditEntryV1.model_validate(e) for e in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/logs/{entry_id}", response_model=AuditEntryV1)
async def get_audit_entry(
    entry_id: UUID,
    _auth: AuthContext = Depends(require_permission("audit:read")),
    service: AuditService = Depends(get_audit_service),
) -> AuditEntryV1:
    entry = await service.get_by_id(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Audit entry not found")
    return AuditEntryV1.model_validate(entry)


@router.get("/verify", response_model=ChainVerificationResultV1)
async def verify_audit_chain(
    from_id: UUID | None = Query(default=None),
    to_id: UUID | None = Query(default=None),
    _auth: AuthContext = Depends(require_permission("audit:read")),
    service: AuditService = Depends(get_audit_service),
) -> ChainVerificationResultV1:
    tampered = await service.verify_chain(from_id=from_id, to_id=to_id)
    return ChainVerificationResultV1(tampered_entries=tampered, verified=len(tampered) == 0)
