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


@router.get("")
async def readiness_check() -> dict[str, object]:
    return {"status": "ready", "version": "0.1.0"}


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


class FindingV1(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: UUID
    organization_id: UUID
    domain: str
    finding_key: str
    severity: str
    description: str
    status: str
    owner_role: str
    remediation: str | None
    exception_expires_at: datetime | None
    opened_at: datetime
    closed_at: datetime | None


class CreateFindingV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    domain: str = Field(min_length=1, max_length=30)
    finding_key: str = Field(min_length=1, max_length=120)
    severity: str = Field(pattern=r"^(low|medium|high|critical)$")
    description: str = Field(min_length=1)
    owner_role: str = Field(min_length=1, max_length=100)


class UpdateFindingV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str | None = Field(default=None, pattern=r"^(open|remediating|closed|risk_accepted)$")
    remediation: str | None = None
    exception_expires_at: datetime | None = None
    retest_evidence_id: UUID | None = None


class ControlV1(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: UUID
    organization_id: UUID
    control_key: str
    version: int
    domain: str
    description: str
    control_type: str
    owner_role: str
    frequency: str
    status: str


@router.post("/evidence", response_model=EvidenceV1, status_code=201)
async def register_evidence(
    body: RegisterEvidenceV1,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=255)],
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
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=255)],
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
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=255)],
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
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=255)],
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
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=255)],
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


@router.get("/evidence", response_model=list[EvidenceV1])
async def list_evidence(
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
) -> list[EvidenceV1]:
    rows = await ReadinessService(session).list_evidence(context_from(auth))
    return [EvidenceV1.model_validate(r) for r in rows]


@router.get("/findings", response_model=list[FindingV1])
async def list_findings(
    status: str | None = None,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
) -> list[FindingV1]:
    rows = await ReadinessService(session).list_findings(context_from(auth), status=status)
    return [FindingV1.model_validate(r) for r in rows]


@router.post("/findings", response_model=FindingV1, status_code=201)
async def create_finding(
    body: CreateFindingV1,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=255)],
    correlation_id: Annotated[UUID | None, Header(alias="X-Correlation-ID")] = None,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
) -> FindingV1:
    try:
        row = await ReadinessService(session).create_finding(
            body.model_dump(mode="python"), context_from(auth), correlation_id or uuid4()
        )
    except (PermissionError, ValueError) as exc:
        raise map_error(exc) from exc
    return FindingV1.model_validate(row)


@router.patch("/findings/{finding_id}", response_model=FindingV1)
async def update_finding(
    finding_id: UUID,
    body: UpdateFindingV1,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=255)],
    correlation_id: Annotated[UUID | None, Header(alias="X-Correlation-ID")] = None,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
) -> FindingV1:
    try:
        row = await ReadinessService(session).update_finding(
            finding_id,
            **body.model_dump(exclude_unset=True),
            context=context_from(auth),
            correlation_id=correlation_id or uuid4(),
        )
    except (LookupError, PermissionError, ValueError) as exc:
        raise map_error(exc) from exc
    return FindingV1.model_validate(row)


@router.get("/decision-packs", response_model=list[DecisionPackV1])
async def list_decision_packs(
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
) -> list[DecisionPackV1]:
    rows = await ReadinessService(session).list_decision_packs(context_from(auth))
    return [DecisionPackV1.model_validate(r) for r in rows]


@router.get("/decisions", response_model=list[DecisionV1])
async def list_decisions(
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
) -> list[DecisionV1]:
    rows = await ReadinessService(session).list_decisions(context_from(auth))
    return [DecisionV1.model_validate(r) for r in rows]


@router.get("/controls", response_model=list[ControlV1])
async def list_controls(
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
) -> list[ControlV1]:
    rows = await ReadinessService(session).list_controls(context_from(auth))
    return [ControlV1.model_validate(r) for r in rows]
