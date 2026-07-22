from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession
from temporalio.client import (
    Client,
    Schedule,
    ScheduleActionStartWorkflow,
    ScheduleIntervalSpec,
    ScheduleOverlapPolicy,
    SchedulePolicy,
    ScheduleSpec,
    ScheduleState,
)

from apps.api.security import AuthContext, get_auth_context
from database.core import get_async_session
from ia_investing.application.investment_candidates import (
    CandidateConcurrencyError,
    CandidateDetail,
    CandidateDuplicateError,
    CandidateIdempotencyConflictError,
    ExplorationDetail,
    InvestmentCandidateApplicationService,
)
from ia_investing.candidate_intelligence.bootstrap import candidate_intelligence_enabled
from ia_investing.candidate_intelligence.contracts import (
    CandidateCreateRequest,
    CandidateGapResolveRequest,
    CandidateReanalysisRequest,
    CandidateSourceCreateRequest,
    ExplorationCreateRequest,
)
from ia_investing.candidate_intelligence.enums import CandidateStatus, RequirementLevel
from ia_investing.candidate_intelligence.readiness import DEFAULT_SOURCE_REQUIREMENTS
from ia_investing.settings import get_settings


def require_candidate_intelligence() -> None:
    if not candidate_intelligence_enabled():
        raise HTTPException(
            status_code=503,
            detail="candidate intelligence is disabled; enable and configure its worker runtime first",
        )


router = APIRouter(
    prefix="/api/v1/investment-candidates",
    tags=["investment-candidates"],
    dependencies=[Depends(require_candidate_intelligence)],
)
exploration_router = APIRouter(
    prefix="/api/v1/exploration-runs",
    tags=["equity-exploration"],
    dependencies=[Depends(require_candidate_intelligence)],
)


class CandidateV1(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: UUID
    organization_id: UUID
    origin: str
    status: str
    ticker: str
    exchange: str
    legal_name: str | None
    trading_name: str | None
    cnpj: str | None
    cvm_code: str | None
    issuer_id: UUID | None
    instrument_id: UUID | None
    rationale: str | None
    final_decision: str | None
    final_decision_reason: str | None
    approved_portfolio_eligible: bool
    created_by: str
    created_at: datetime
    updated_at: datetime
    lock_version: int


class CandidateSourceV1(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: UUID
    candidate_id: UUID
    kind: str
    url: str
    status: str
    verification_method: str
    confidence: Decimal
    official: bool
    discovered_by: str
    notes: str | None
    evidence: dict[str, object]
    created_at: datetime
    verified_at: datetime | None
    last_checked_at: datetime | None


class CandidateGapV1(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: UUID
    candidate_id: UUID
    code: str
    title: str
    description: str
    source_kind: str | None
    level: str
    status: str
    requested_user_action: str
    created_at: datetime
    resolved_at: datetime | None
    resolved_by: str | None
    resolution_notes: str | None


class CandidateRunV1(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: UUID
    candidate_id: UUID
    run_number: int
    trigger: str
    status: str
    requested_by: str
    requested_at: datetime
    data_as_of: datetime
    workflow_id: str | None
    started_at: datetime | None
    completed_at: datetime | None
    decision: str | None
    summary: str | None
    blocker_codes: list[str]
    research_case_id: UUID | None
    thesis_version_id: UUID | None
    committee_decision_id: UUID | None
    error_code: str | None
    error_detail: str | None


class CandidateEventV1(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: UUID
    candidate_id: UUID
    event_type: str
    actor_type: str
    actor_id: str
    occurred_at: datetime
    aggregate_version: int
    payload: dict[str, object]


class CandidateDetailV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate: CandidateV1
    sources: list[CandidateSourceV1]
    gaps: list[CandidateGapV1]
    analysis_runs: list[CandidateRunV1]
    timeline: list[CandidateEventV1]
    readiness_score: Decimal
    blocking_gap_codes: list[str]


class CandidateCreatedV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate: CandidateV1
    analysis_run: CandidateRunV1
    replayed: bool


class OperationAcceptedV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation_id: UUID
    resource_id: UUID
    status: str = "accepted"


class ExplorationRunV1(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: UUID
    organization_id: UUID
    status: str
    strategy_codes: list[str]
    requested_by: str
    created_at: datetime
    data_as_of: datetime
    minimum_liquidity: Decimal
    maximum_suggestions: int
    started_at: datetime | None
    completed_at: datetime | None
    workflow_id: str | None
    universe_size: int
    eligible_size: int
    error_detail: str | None


class ExplorationSuggestionV1(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: UUID
    exploration_run_id: UUID
    organization_id: UUID
    instrument_id: UUID
    issuer_id: UUID
    ticker: str
    exchange: str
    status: str
    quantitative_score: Decimal
    data_coverage_score: Decimal
    source_discovery_score: Decimal
    rationale: str
    signals: list[str]
    risks: list[str]
    source_snapshot: list[dict[str, object]]
    created_at: datetime
    expires_at: datetime | None
    promoted_candidate_id: UUID | None
    dismissed_at: datetime | None
    dismissed_by: str | None
    dismissal_reason: str | None


class ExplorationDetailV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run: ExplorationRunV1
    suggestions: list[ExplorationSuggestionV1]


class SuggestionDismissV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=3, max_length=2_000)


class ExplorationScheduleCreateV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=3, max_length=60, pattern=r"^[a-z0-9][a-z0-9-]+$")
    strategy_codes: list[str] = Field(min_length=1, max_length=10)
    minimum_liquidity: Decimal = Field(ge=0)
    maximum_suggestions: int = Field(ge=1, le=100)
    interval_hours: int = Field(default=168, ge=24, le=720)
    paused: bool = False


class ExplorationScheduleV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schedule_id: str
    interval_hours: int
    paused: bool


def exploration_detail_response(detail: ExplorationDetail) -> ExplorationDetailV1:
    return ExplorationDetailV1(
        run=ExplorationRunV1.model_validate(detail.run),
        suggestions=[ExplorationSuggestionV1.model_validate(item) for item in detail.suggestions],
    )


def parse_etag(value: str) -> int:
    normalized = value.strip().removeprefix("W/").strip('"')
    try:
        return int(normalized)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="If-Match must contain a numeric candidate version") from exc


def organization_id(auth: AuthContext) -> UUID:
    if auth.organization_id is None:
        raise HTTPException(status_code=403, detail="organization context is required")
    return auth.organization_id


def detail_response(detail: CandidateDetail, response: Response) -> CandidateDetailV1:
    candidate = detail.candidate
    response.headers["ETag"] = f'"{candidate.lock_version}"'

    verified_sources = {
        source.kind: source for source in detail.sources if source.status == "verified" and source.official
    }
    blocking = sorted(gap.code for gap in detail.gaps if gap.status == "open" and gap.level == "blocking")

    weighted_total = Decimal("0")
    weight_sum = Decimal("0")
    identity_resolved = bool(candidate.issuer_id and candidate.instrument_id)
    identity_weight = Decimal("2")
    weight_sum += identity_weight
    weighted_total += identity_weight if identity_resolved else Decimal("0")

    for requirement in DEFAULT_SOURCE_REQUIREMENTS:
        weight = (
            Decimal("2")
            if requirement.level is RequirementLevel.BLOCKING
            else Decimal("1.5")
            if requirement.level is RequirementLevel.REQUIRED
            else Decimal("1")
        )
        source = verified_sources.get(requirement.kind.value)
        satisfied = bool(
            source
            and source.confidence >= requirement.minimum_confidence
            and (source.official or not requirement.must_be_official)
        )
        weight_sum += weight
        if satisfied:
            weighted_total += weight

    stage_rank = {
        CandidateStatus.SUGGESTED.value: 0,
        CandidateStatus.IDENTITY_RESOLUTION.value: 0,
        CandidateStatus.SOURCE_DISCOVERY.value: 1,
        CandidateStatus.AWAITING_USER_INPUT.value: 1,
        CandidateStatus.SOURCE_VALIDATION.value: 1,
        CandidateStatus.DOCUMENT_COLLECTION.value: 2,
        CandidateStatus.DATA_QUALITY.value: 3,
        CandidateStatus.FUNDAMENTAL_ANALYSIS.value: 4,
        CandidateStatus.RISK_ANALYSIS.value: 5,
        CandidateStatus.COMMITTEE_REVIEW.value: 6,
        CandidateStatus.APPROVED.value: 7,
        CandidateStatus.REJECTED.value: 7,
        CandidateStatus.WATCHLIST.value: 7,
        CandidateStatus.CANCELLED.value: 0,
    }.get(candidate.status, 0)
    for threshold in (3, 4, 5, 6, 7):
        weight_sum += Decimal("1")
        if stage_rank >= threshold:
            weighted_total += Decimal("1")

    readiness = (weighted_total / weight_sum).quantize(Decimal("0.0001")) if weight_sum else Decimal("0")
    return CandidateDetailV1(
        candidate=CandidateV1.model_validate(candidate),
        sources=[CandidateSourceV1.model_validate(item) for item in detail.sources],
        gaps=[CandidateGapV1.model_validate(item) for item in detail.gaps],
        analysis_runs=[CandidateRunV1.model_validate(item) for item in detail.runs],
        timeline=[CandidateEventV1.model_validate(item) for item in detail.events],
        readiness_score=readiness,
        blocking_gap_codes=blocking,
    )


@router.get("", response_model=list[CandidateV1])
async def list_candidates(
    response: Response,
    status: str | None = None,
    after: UUID | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
) -> list[CandidateV1]:
    try:
        rows = await InvestmentCandidateApplicationService(session).list_candidates(
            organization_id=organization_id(auth),
            permissions=auth.permissions,
            status=status,
            after=after,
            limit=limit,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    if len(rows) > limit:
        response.headers["X-Next-Cursor"] = str(rows[limit - 1].id)
        rows = rows[:limit]
    return [CandidateV1.model_validate(item) for item in rows]


@router.post("", response_model=CandidateCreatedV1, status_code=202)
async def create_candidate(
    body: CandidateCreateRequest,
    response: Response,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=255)],
    data_as_of: datetime = Query(),
    correlation_id: UUID | None = Header(default=None, alias="X-Correlation-ID"),
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
) -> CandidateCreatedV1:
    try:
        candidate, run, created = await InvestmentCandidateApplicationService(session).create_manual(
            organization_id=organization_id(auth),
            actor_id=auth.subject,
            permissions=auth.permissions,
            request=body,
            data_as_of=data_as_of,
            idempotency_key=idempotency_key,
            correlation_id=correlation_id or uuid4(),
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except CandidateIdempotencyConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except CandidateDuplicateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not created:
        response.status_code = 200
    response.headers["ETag"] = f'"{candidate.lock_version}"'
    response.headers["Location"] = f"/api/v1/investment-candidates/{candidate.id}"
    return CandidateCreatedV1(
        candidate=CandidateV1.model_validate(candidate),
        analysis_run=CandidateRunV1.model_validate(run),
        replayed=not created,
    )


@router.get("/{candidate_id}", response_model=CandidateDetailV1)
async def get_candidate(
    candidate_id: UUID,
    response: Response,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
) -> CandidateDetailV1:
    try:
        detail = await InvestmentCandidateApplicationService(session).get_detail(
            candidate_id=candidate_id,
            organization_id=organization_id(auth),
            permissions=auth.permissions,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    if detail is None:
        raise HTTPException(status_code=404, detail="investment candidate not found")
    return detail_response(detail, response)


@router.post("/{candidate_id}/sources", response_model=CandidateSourceV1, status_code=202)
async def add_candidate_source(
    candidate_id: UUID,
    body: CandidateSourceCreateRequest,
    if_match: Annotated[str, Header(alias="If-Match")],
    auth: AuthContext = Depends(get_auth_context),
    correlation_id: UUID | None = Header(default=None, alias="X-Correlation-ID"),
    session: AsyncSession = Depends(get_async_session),
) -> CandidateSourceV1:
    try:
        source = await InvestmentCandidateApplicationService(session).add_source(
            candidate_id=candidate_id,
            organization_id=organization_id(auth),
            actor_id=auth.subject,
            permissions=auth.permissions,
            request=body,
            expected_version=parse_etag(if_match),
            correlation_id=correlation_id or uuid4(),
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except CandidateConcurrencyError as exc:
        raise HTTPException(status_code=412, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return CandidateSourceV1.model_validate(source)


@router.post("/{candidate_id}/gaps/{gap_id}/resolution", response_model=CandidateGapV1)
async def resolve_candidate_gap(
    candidate_id: UUID,
    gap_id: UUID,
    body: CandidateGapResolveRequest,
    if_match: Annotated[str, Header(alias="If-Match")],
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
) -> CandidateGapV1:
    if body.source is not None:
        raise HTTPException(
            status_code=409,
            detail="add and validate the source first; then resolve the blocking gap",
        )
    try:
        gap = await InvestmentCandidateApplicationService(session).resolve_gap(
            candidate_id=candidate_id,
            gap_id=gap_id,
            organization_id=organization_id(auth),
            actor_id=auth.subject,
            permissions=auth.permissions,
            notes=body.notes,
            expected_version=parse_etag(if_match),
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except CandidateConcurrencyError as exc:
        raise HTTPException(status_code=412, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return CandidateGapV1.model_validate(gap)


@router.post("/{candidate_id}/reanalysis", response_model=OperationAcceptedV1, status_code=202)
async def reanalyze_candidate(
    candidate_id: UUID,
    body: CandidateReanalysisRequest,
    if_match: Annotated[str, Header(alias="If-Match")],
    auth: AuthContext = Depends(get_auth_context),
    correlation_id: UUID | None = Header(default=None, alias="X-Correlation-ID"),
    session: AsyncSession = Depends(get_async_session),
) -> OperationAcceptedV1:
    try:
        run = await InvestmentCandidateApplicationService(session).request_reanalysis(
            candidate_id=candidate_id,
            organization_id=organization_id(auth),
            actor_id=auth.subject,
            permissions=auth.permissions,
            request=body,
            expected_version=parse_etag(if_match),
            correlation_id=correlation_id or uuid4(),
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except CandidateConcurrencyError as exc:
        raise HTTPException(status_code=412, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return OperationAcceptedV1(operation_id=run.id, resource_id=candidate_id)


@exploration_router.get("", response_model=list[ExplorationRunV1])
async def list_exploration_runs(
    status: str | None = None,
    limit: int = Query(default=25, ge=1, le=100),
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
) -> list[ExplorationRunV1]:
    try:
        rows = await InvestmentCandidateApplicationService(session).list_exploration_runs(
            organization_id=organization_id(auth),
            permissions=auth.permissions,
            status=status,
            limit=limit,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return [ExplorationRunV1.model_validate(item) for item in rows]


@exploration_router.post("/schedules", response_model=ExplorationScheduleV1, status_code=201)
async def create_exploration_schedule(
    body: ExplorationScheduleCreateV1,
    auth: AuthContext = Depends(get_auth_context),
) -> ExplorationScheduleV1:
    if not ({"schedules:manage", "exploration:schedule"} & set(auth.permissions)):
        raise HTTPException(status_code=403, detail="permission required: schedules:manage or exploration:schedule")
    org_id = organization_id(auth)
    schedule_id = f"equity-exploration-{org_id}-{body.name}"
    settings = get_settings()
    client = await Client.connect(settings.temporal.address, namespace=settings.temporal.namespace)
    schedule = Schedule(
        action=ScheduleActionStartWorkflow(
            "ScheduledEquityExplorationWorkflow",
            {
                "organization_id": str(org_id),
                "strategy_codes": body.strategy_codes,
                "minimum_liquidity": str(body.minimum_liquidity),
                "maximum_suggestions": body.maximum_suggestions,
                "requested_by": f"schedule:{body.name}",
            },
            id=f"{schedule_id}-workflow",
            task_queue="research-agents",
        ),
        spec=ScheduleSpec(intervals=[ScheduleIntervalSpec(every=timedelta(hours=body.interval_hours))]),
        policy=SchedulePolicy(
            overlap=ScheduleOverlapPolicy.SKIP,
            catchup_window=timedelta(hours=2),
            pause_on_failure=True,
        ),
        state=ScheduleState(paused=body.paused),
    )
    try:
        await client.create_schedule(schedule_id, schedule)
    except Exception as exc:
        if "already" in str(exc).lower():
            raise HTTPException(status_code=409, detail="exploration schedule already exists") from exc
        raise HTTPException(status_code=503, detail="could not create Temporal exploration schedule") from exc
    return ExplorationScheduleV1(
        schedule_id=schedule_id,
        interval_hours=body.interval_hours,
        paused=body.paused,
    )


@exploration_router.get("/{exploration_run_id}", response_model=ExplorationDetailV1)
async def get_exploration_run(
    exploration_run_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
) -> ExplorationDetailV1:
    try:
        detail = await InvestmentCandidateApplicationService(session).get_exploration_detail(
            exploration_run_id=exploration_run_id,
            organization_id=organization_id(auth),
            permissions=auth.permissions,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    if detail is None:
        raise HTTPException(status_code=404, detail="exploration run not found")
    return exploration_detail_response(detail)


@exploration_router.post("", response_model=ExplorationRunV1, status_code=202)
async def create_exploration_run(
    body: ExplorationCreateRequest,
    auth: AuthContext = Depends(get_auth_context),
    correlation_id: UUID | None = Header(default=None, alias="X-Correlation-ID"),
    session: AsyncSession = Depends(get_async_session),
) -> ExplorationRunV1:
    try:
        run = await InvestmentCandidateApplicationService(session).create_exploration_run(
            organization_id=organization_id(auth),
            actor_id=auth.subject,
            permissions=auth.permissions,
            request=body,
            correlation_id=correlation_id or uuid4(),
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return ExplorationRunV1.model_validate(run)


@exploration_router.post(
    "/suggestions/{suggestion_id}/dismissal",
    response_model=ExplorationSuggestionV1,
)
async def dismiss_exploration_suggestion(
    suggestion_id: UUID,
    body: SuggestionDismissV1,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
) -> ExplorationSuggestionV1:
    try:
        suggestion = await InvestmentCandidateApplicationService(session).dismiss_suggestion(
            suggestion_id=suggestion_id,
            organization_id=organization_id(auth),
            actor_id=auth.subject,
            permissions=auth.permissions,
            reason=body.reason,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return ExplorationSuggestionV1.model_validate(suggestion)


@exploration_router.post(
    "/suggestions/{suggestion_id}/promotion",
    response_model=CandidateV1,
    status_code=202,
)
async def promote_exploration_suggestion(
    suggestion_id: UUID,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=255)],
    auth: AuthContext = Depends(get_auth_context),
    correlation_id: UUID | None = Header(default=None, alias="X-Correlation-ID"),
    session: AsyncSession = Depends(get_async_session),
) -> CandidateV1:
    try:
        candidate = await InvestmentCandidateApplicationService(session).promote_suggestion(
            suggestion_id=suggestion_id,
            organization_id=organization_id(auth),
            actor_id=auth.subject,
            permissions=auth.permissions,
            idempotency_key=idempotency_key,
            correlation_id=correlation_id or uuid4(),
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return CandidateV1.model_validate(candidate)
