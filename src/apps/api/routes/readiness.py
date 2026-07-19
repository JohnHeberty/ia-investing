from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.security import AuthContext, get_auth_context
from database.core import get_async_session
from ia_investing.application.readiness import ReadinessService
from ia_investing.domain.identity import InstitutionalAccessContext

router = APIRouter(prefix="/api/v1/readiness", tags=["readiness"])


def context_from(auth: AuthContext) -> InstitutionalAccessContext:
    if auth.organization_id is None:
        raise HTTPException(status_code=403, detail="institutional organization context is required")
    return InstitutionalAccessContext(auth.subject, auth.organization_id, auth.team_ids, auth.permissions, "paper")


def map_error(exc: Exception) -> HTTPException:
    if isinstance(exc, LookupError):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, PermissionError):
        return HTTPException(status_code=403, detail=str(exc))
    return HTTPException(status_code=409, detail=str(exc))


class RegisterEvidenceV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_type: str
    title: str = Field(min_length=1, max_length=250)
    artifact_uri: str = Field(min_length=1)
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    issued_by: str = Field(min_length=1)
    independent: bool
    issued_at: datetime
    expires_at: datetime | None = None
    metadata_payload: dict[str, object] = Field(default_factory=dict)


class EvidenceV1(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: UUID
    organization_id: UUID
    evidence_type: str
    title: str
    artifact_uri: str
    content_sha256: str
    issued_by: str
    independent: bool
    status: str
    issued_at: datetime
    expires_at: datetime | None
    verified_by: str | None
    verified_at: datetime | None


class VerifyEvidenceV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    accepted: bool


class FreezePackV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    manifest: dict[str, object]
    expires_at: datetime


class DecisionPackV1(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: UUID
    organization_id: UUID
    version: int
    content_sha256: str
    manifest: dict[str, object]
    frozen_by: str
    frozen_at: datetime
    expires_at: datetime


class VoteInputV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: str
    vote: str = Field(pattern=r"^(go|conditional_go|no_go)$")
    rationale: str = Field(min_length=1)
    conflicts: list[str]


class VoteV1(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: UUID
    decision_pack_id: UUID
    voter_subject: str
    voter_role: str
    vote: str
    rationale: str
    conflicts: list[str]
    signed_at: datetime


class DecisionV1(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: UUID
    decision_pack_id: UUID
    result: str
    authorized_scope: str
    blockers: list[dict[str, object]]
    conditions: list[dict[str, object]]
    dissent: list[dict[str, object]]
    decided_by: str
    decided_at: datetime
    expires_at: datetime


@router.post("/evidence", response_model=EvidenceV1, status_code=201)
async def register_evidence(
    body: RegisterEvidenceV1,
    correlation_id: Annotated[UUID | None, Header(alias="X-Correlation-ID")] = None,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
) -> EvidenceV1:
    try:
        row = await ReadinessService(session).register_evidence(
            body.model_dump(mode="python"), context_from(auth), correlation_id or uuid4()
        )
    except (PermissionError, ValueError) as exc:
        raise map_error(exc) from exc
    return EvidenceV1.model_validate(row)


@router.post("/evidence/{evidence_id}/verification", response_model=EvidenceV1)
async def verify_evidence(
    evidence_id: UUID,
    body: VerifyEvidenceV1,
    correlation_id: Annotated[UUID | None, Header(alias="X-Correlation-ID")] = None,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
) -> EvidenceV1:
    try:
        row = await ReadinessService(session).verify_evidence(
            evidence_id,
            accepted=body.accepted,
            context=context_from(auth),
            correlation_id=correlation_id or uuid4(),
        )
    except (LookupError, PermissionError, ValueError) as exc:
        raise map_error(exc) from exc
    return EvidenceV1.model_validate(row)


@router.post("/decision-packs", response_model=DecisionPackV1, status_code=201)
async def freeze_decision_pack(
    body: FreezePackV1,
    correlation_id: Annotated[UUID | None, Header(alias="X-Correlation-ID")] = None,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
) -> DecisionPackV1:
    try:
        row = await ReadinessService(session).freeze_pack(
            **body.model_dump(mode="python"),
            context=context_from(auth),
            correlation_id=correlation_id or uuid4(),
        )
    except (PermissionError, ValueError) as exc:
        raise map_error(exc) from exc
    return DecisionPackV1.model_validate(row)


@router.post("/decision-packs/{pack_id}/votes", response_model=VoteV1, status_code=201)
async def sign_readiness_vote(
    pack_id: UUID,
    body: VoteInputV1,
    correlation_id: Annotated[UUID | None, Header(alias="X-Correlation-ID")] = None,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
) -> VoteV1:
    try:
        row = await ReadinessService(session).vote(
            pack_id,
            **body.model_dump(),
            context=context_from(auth),
            correlation_id=correlation_id or uuid4(),
        )
    except (LookupError, PermissionError, ValueError) as exc:
        raise map_error(exc) from exc
    return VoteV1.model_validate(row)


@router.post("/decision-packs/{pack_id}/decision", response_model=DecisionV1)
async def record_readiness_decision(
    pack_id: UUID,
    correlation_id: Annotated[UUID | None, Header(alias="X-Correlation-ID")] = None,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
) -> DecisionV1:
    try:
        row = await ReadinessService(session).decide(
            pack_id, context=context_from(auth), correlation_id=correlation_id or uuid4()
        )
    except (LookupError, PermissionError, ValueError) as exc:
        raise map_error(exc) from exc
    return DecisionV1.model_validate(row)
