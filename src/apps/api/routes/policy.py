from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated
from uuid import UUID

import sqlalchemy as sa
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.security import AuthContext, get_auth_context
from database.core import get_async_session
from database.models.policy_intelligence import PolicyStageEvent, RegulatoryAction
from ia_investing.application._audit_mixin import AuditMixin
from ia_investing.application.macro import MacroSeriesService
from ia_investing.application.policy_intelligence import (
    PolicyAlertService,
    PolicyIngestionService,
    PolicyIntelligenceQueryService,
    PolicySourceService,
    ProbabilityForecastService,
)

router = APIRouter(prefix="/api/v1/policy", tags=["policy-intelligence"])
macro_router = APIRouter(prefix="/api/v1/macro", tags=["macro-intelligence"])
_audit = AuditMixin()


class MacroDefinitionInputV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: UUID
    series_code: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=200)
    unit: str = Field(min_length=1, max_length=50)
    frequency: str
    revision_policy: str = Field(min_length=1, max_length=100)
    transformation: dict[str, object]
    valid_from: datetime


class MacroDefinitionV1(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: UUID
    source_id: UUID
    series_code: str
    version: int
    name: str
    unit: str
    frequency: str
    revision_policy: str
    transformation: dict[str, object]
    content_sha256: str
    valid_from: datetime
    valid_to: datetime | None


class MacroObservationInputV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    effective_date: date
    value: Decimal | None = None
    value_status: str
    published_at: datetime
    knowledge_at: datetime
    source_object_version_id: UUID


class MacroObservationV1(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: UUID
    series_definition_id: UUID
    effective_date: date
    revision: int
    value: Decimal | None
    value_status: str
    published_at: datetime
    knowledge_at: datetime
    source_object_version_id: UUID


class MacroTransformedValueV1(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    effective_date: date
    value: Decimal | None
    value_status: str
    source_revision: int


class MacroSeriesValuesV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    definition: MacroDefinitionV1
    as_of: datetime
    values: list[MacroTransformedValueV1]


class PolicyObjectInputV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    authority: str = Field(min_length=1, max_length=100)
    object_type: str = Field(min_length=1, max_length=50)
    external_id: str = Field(min_length=1, max_length=150)
    title: str = Field(min_length=1)
    text_content: str
    metadata_payload: dict[str, object]
    published_at: datetime
    knowledge_at: datetime
    source_object_version_id: UUID


class PolicyObjectVersionV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    policy_object_id: UUID
    version_id: UUID
    version: int
    text_sha256: str
    metadata_sha256: str
    created: bool


class PolicyAlertV1(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    policy_object_id: UUID
    alert_type: str
    severity: str
    title: str
    description: str | None = None
    fired_at: datetime
    acknowledged_at: datetime | None = None
    acknowledged_by: str | None = None
    resolved_at: datetime | None = None
    resolved_by: str | None = None


class PolicyAlertResolveRequest(BaseModel):
    notes: str = Field(min_length=3, max_length=4000)


class PolicyForecastV1(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    policy_object_id: UUID
    target_outcome: str
    probability: Decimal
    interval_low: Decimal | None = None
    interval_high: Decimal | None = None


class PolicyStageEventV1(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    policy_object_id: UUID
    stage: str
    occurred_at: datetime
    knowledge_at: datetime


class RegulatoryActionV1(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    policy_object_id: UUID
    action_type: str
    title: str
    issued_at: datetime
    authority: str


class PolicySourceV1(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    authority: str = "camara"
    source_type: str | None = None
    url_pattern: str | None = None
    is_active: bool = True
    last_fetched_at: datetime | None = None
    last_fetch_error: str | None = None
    last_fetch_error_at: datetime | None = None


class PolicySourceCreateInput(BaseModel):
    name: str
    authority: str = "camara"
    source_type: str | None = None
    url_pattern: str | None = None


class PolicySourceUpdateInput(BaseModel):
    name: str | None = None
    authority: str | None = None
    source_type: str | None = None
    url_pattern: str | None = None
    is_active: bool | None = None


def require_policy_read(auth: AuthContext) -> None:
    if "policy:read" not in auth.permissions and "portfolio:read" not in auth.permissions:
        raise HTTPException(status_code=403, detail="permission required: policy:read")


@router.post("/objects", response_model=PolicyObjectVersionV1, status_code=201)
async def ingest_policy_object(
    body: PolicyObjectInputV1,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=255)],
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
) -> PolicyObjectVersionV1:
    try:
        obj, version, created = await PolicyIngestionService(session).ingest(
            **body.model_dump(mode="python"), permissions=auth.permissions
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return PolicyObjectVersionV1(
        policy_object_id=obj.id,
        version_id=version.id,
        version=version.version,
        text_sha256=version.text_sha256,
        metadata_sha256=version.metadata_sha256,
        created=created,
    )


@router.get("/events")
async def list_policy_events(
    as_of: datetime,
    authority: str | None = None,
    stage: str | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
) -> list[dict[str, object]]:
    require_policy_read(auth)
    try:
        return await PolicyIntelligenceQueryService(session).events(
            as_of=as_of, authority=authority, stage=stage, limit=limit
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/events/{policy_object_id}")
async def get_policy_event(
    policy_object_id: UUID,
    as_of: datetime,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, object]:
    require_policy_read(auth)
    try:
        return await PolicyIntelligenceQueryService(session).detail(policy_object_id, as_of=as_of)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/graph")
async def get_policy_graph(
    as_of: datetime,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, object]:
    require_policy_read(auth)
    if auth.organization_id is None:
        raise HTTPException(status_code=403, detail="institutional organization context is required")
    return await PolicyIntelligenceQueryService(session).graph(organization_id=auth.organization_id, as_of=as_of)


# ---------------------------------------------------------------------------
# Alerts
# ---------------------------------------------------------------------------


@router.get("/alerts", response_model=list[PolicyAlertV1])
async def list_alerts(
    policy_object_id: UUID | None = None,
    status: str = "active",
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
) -> list[PolicyAlertV1]:
    require_policy_read(auth)
    service = PolicyAlertService(session)
    alerts = await service.list_alerts(
        policy_object_id=policy_object_id,
        status=status,
    )
    return [PolicyAlertV1.model_validate(a) for a in alerts]


@router.post("/alerts/{alert_id}/acknowledge", response_model=PolicyAlertV1)
async def acknowledge_alert(
    alert_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
) -> PolicyAlertV1:
    service = PolicyAlertService(session)
    try:
        alert = await service.acknowledge(alert_id=alert_id, actor=auth.subject)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return PolicyAlertV1.model_validate(alert)


@router.post("/alerts/{alert_id}/resolve", response_model=PolicyAlertV1)
async def resolve_alert(
    alert_id: UUID,
    body: PolicyAlertResolveRequest,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
) -> PolicyAlertV1:
    service = PolicyAlertService(session)
    try:
        alert = await service.resolve(
            alert_id=alert_id,
            actor=auth.subject,
            notes=body.notes,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return PolicyAlertV1.model_validate(alert)


# ---------------------------------------------------------------------------
# Forecasts
# ---------------------------------------------------------------------------


@router.get("/forecasts", response_model=list[PolicyForecastV1])
async def list_forecasts(
    policy_object_id: UUID | None = None,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
) -> list[PolicyForecastV1]:
    require_policy_read(auth)
    service = ProbabilityForecastService(session)
    forecasts = await service.list_forecasts(policy_object_id=policy_object_id)
    return [PolicyForecastV1.model_validate(f) for f in forecasts]


# ---------------------------------------------------------------------------
# Stages
# ---------------------------------------------------------------------------


@router.get("/stages/{policy_object_id}", response_model=list[PolicyStageEventV1])
async def get_stages(
    policy_object_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
) -> list[PolicyStageEventV1]:
    require_policy_read(auth)
    stmt = (
        sa.select(PolicyStageEvent)
        .where(PolicyStageEvent.policy_object_id == policy_object_id)
        .order_by(PolicyStageEvent.occurred_at)
    )
    events = list((await session.execute(stmt)).scalars())
    return [PolicyStageEventV1.model_validate(e) for e in events]


# ---------------------------------------------------------------------------
# Regulatory Actions
# ---------------------------------------------------------------------------


@router.get("/regulatory-actions", response_model=list[RegulatoryActionV1])
async def list_regulatory_actions(
    policy_object_id: UUID | None = None,
    authority: str | None = None,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
) -> list[RegulatoryActionV1]:
    require_policy_read(auth)
    stmt = sa.select(RegulatoryAction)
    if policy_object_id is not None:
        stmt = stmt.where(RegulatoryAction.policy_object_id == policy_object_id)
    if authority is not None:
        stmt = stmt.where(RegulatoryAction.authority == authority)
    stmt = stmt.order_by(RegulatoryAction.issued_at.desc())
    actions = list((await session.execute(stmt)).scalars())
    return [RegulatoryActionV1.model_validate(a) for a in actions]


# ---------------------------------------------------------------------------
# Sources
# ---------------------------------------------------------------------------


@router.get("/sources", response_model=list[PolicySourceV1])
async def list_sources(
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
) -> list[PolicySourceV1]:
    require_policy_read(auth)
    service = PolicySourceService(session)
    sources = await service.list_sources()
    return [PolicySourceV1.model_validate(s) for s in sources]


@router.post("/sources", response_model=PolicySourceV1, status_code=201)
async def create_source(
    body: PolicySourceCreateInput,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
) -> PolicySourceV1:
    require_policy_read(auth)
    service = PolicySourceService(session)
    source = await service.create_source(
        name=body.name,
        authority=body.authority,
        source_type=body.source_type,
        url_pattern=body.url_pattern,
    )
    return PolicySourceV1.model_validate(source)


@router.put("/sources/{source_id}", response_model=PolicySourceV1)
async def update_source(
    source_id: UUID,
    body: PolicySourceUpdateInput,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
) -> PolicySourceV1:
    require_policy_read(auth)
    service = PolicySourceService(session)
    try:
        source = await service.update_source(
            source_id=source_id,
            name=body.name,
            authority=body.authority,
            source_type=body.source_type,
            url_pattern=body.url_pattern,
            is_active=body.is_active,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return PolicySourceV1.model_validate(source)


@router.delete("/sources/{source_id}", status_code=204)
async def delete_source(
    source_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
) -> None:
    require_policy_read(auth)
    service = PolicySourceService(session)
    try:
        await service.delete_source(source_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# Macro series
# ---------------------------------------------------------------------------


@macro_router.post("/series", response_model=MacroDefinitionV1, status_code=201)
async def register_macro_series(
    body: MacroDefinitionInputV1,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=255)],
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
) -> MacroDefinitionV1:
    try:
        definition = await MacroSeriesService(session).register_definition(
            **body.model_dump(mode="python"), permissions=auth.permissions
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return MacroDefinitionV1.model_validate(definition)


@macro_router.post("/series/{definition_id}/observations", response_model=MacroObservationV1, status_code=201)
async def ingest_macro_observation(
    definition_id: UUID,
    body: MacroObservationInputV1,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=255)],
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
) -> MacroObservationV1:
    try:
        observation = await MacroSeriesService(session).ingest_observation(
            definition_id=definition_id,
            **body.model_dump(mode="python"),
            permissions=auth.permissions,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return MacroObservationV1.model_validate(observation)


@macro_router.get("/series/{definition_id}", response_model=MacroSeriesValuesV1)
async def get_macro_series(
    definition_id: UUID,
    as_of: datetime,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
) -> MacroSeriesValuesV1:
    if "macro:read" not in auth.permissions and "portfolio:read" not in auth.permissions:
        raise HTTPException(status_code=403, detail="permission required: macro:read")
    try:
        payload = await MacroSeriesService(session).values(definition_id, as_of=as_of)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return MacroSeriesValuesV1.model_validate(payload)
