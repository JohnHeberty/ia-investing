from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.security import AuthContext, get_auth_context
from database.core import get_async_session
from ia_investing.application.macro import MacroSeriesService
from ia_investing.application.policy_intelligence import PolicyIngestionService, PolicyIntelligenceQueryService

router = APIRouter(prefix="/api/v1/policy", tags=["policy-intelligence"])
macro_router = APIRouter(prefix="/api/v1/macro", tags=["macro-intelligence"])


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


def require_policy_read(auth: AuthContext) -> None:
    if "policy:read" not in auth.permissions and "portfolio:read" not in auth.permissions:
        raise HTTPException(status_code=403, detail="permission required: policy:read")


@router.post("/objects", response_model=PolicyObjectVersionV1, status_code=201)
async def ingest_policy_object(
    body: PolicyObjectInputV1,
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


@macro_router.post("/series", response_model=MacroDefinitionV1, status_code=201)
async def register_macro_series(
    body: MacroDefinitionInputV1,
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
