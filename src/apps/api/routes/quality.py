from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.security import AuthContext, require_permission
from database.core import get_async_session
from ia_investing.application.data_quality import QualityGovernanceService, QualityIncidentV1

router = APIRouter(prefix="/api/v1/quality", tags=["data-quality"])


class IncidentTransitionV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target: Literal["open", "acknowledged", "resolved", "waived"]
    reason: str | None = None
    waiver_expires_at: datetime | None = None


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
    return QualityIncidentV1.model_validate(incident)
