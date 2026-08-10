from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.security import AuthContext, require_permission, safe_uuid
from database.core import get_async_session
from database.models.data_governance import QualityIncident
from ia_investing.application._audit_mixin import AuditMixin
from ia_investing.application.data_quality import QualityGovernanceService, QualityIncidentV1

router = APIRouter(prefix="/api/v1/quality", tags=["data-quality"])
_audit = AuditMixin()


class IncidentTransitionV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target: Literal["open", "acknowledged", "resolved", "waived"]
    reason: str | None = None
    waiver_expires_at: datetime | None = None


@router.get("/incidents", response_model=list[QualityIncidentV1])
async def list_incidents(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    status: str | None = Query(default=None),
    auth: AuthContext = Depends(require_permission("quality_incidents:manage")),
    session: AsyncSession = Depends(get_async_session),
) -> list[QualityIncidentV1]:
    stmt = select(QualityIncident).order_by(QualityIncident.created_at.desc())
    if auth.organization_id:
        stmt = stmt.where(QualityIncident.organization_id == auth.organization_id)
    if status:
        stmt = stmt.where(QualityIncident.status == status)
    stmt = stmt.limit(limit).offset(offset)
    rows = (await session.execute(stmt)).scalars().all()
    return [QualityIncidentV1.model_validate(row) for row in rows]


@router.post("/incidents/{incident_id}/transitions", response_model=QualityIncidentV1)
async def transition_incident(
    incident_id: UUID,
    body: IncidentTransitionV1,
    auth: AuthContext = Depends(require_permission("quality_incidents:manage")),
    correlation_id: UUID | None = Header(default=None, alias="X-Correlation-ID"),
    session: AsyncSession = Depends(get_async_session),
) -> QualityIncidentV1:
    try:
        incident = await QualityGovernanceService(session).transition(
            incident_id=incident_id,
            target=body.target,
            actor_subject=auth.subject,
            permissions=auth.permissions,
            correlation_id=correlation_id or uuid4(),
            reason=body.reason,
            waiver_expires_at=body.waiver_expires_at,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if auth.organization_id:
        await _audit._audit(
            session=session,
            tenant_id=auth.organization_id,
            actor_id=safe_uuid(auth.subject),
            action="update",
            resource_type="quality_incident",
            resource_id=incident_id,
            changes={"target": body.target},
        )
    return QualityIncidentV1.model_validate(incident)
