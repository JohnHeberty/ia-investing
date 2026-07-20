from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.security import AuthContext, get_auth_context, require_permission
from database.core import get_async_session
from database.models.research import ResearchCase
from ia_investing.application.evidence import EvidenceReferenceV1, EvidenceRepository
from ia_investing.application.research import (
    ClaimService,
    CreateResearchCase,
    ResearchCaseService,
    ResearchConcurrencyError,
    ResearchIdempotencyConflictError,
)
from ia_investing.application.reviews import ResearchReviewService
from ia_investing.application.theses import ThesisService, ThesisSnapshot
from ia_investing.application.valuations import (
    AssumptionInput,
    RelativeInput,
    ReverseDCFInput,
    ScenarioInput,
    ValuationCommand,
    ValuationExecution,
    ValuationService,
)
from ia_investing.domain.valuation import DCFInput

router = APIRouter(prefix="/api/v1/research", tags=["research"])


class CreateResearchCaseV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_type: str = Field(min_length=1, max_length=50)
    title: str = Field(min_length=1, max_length=300)
    priority: str
    issuer_id: UUID
    instrument_id: UUID | None = None
    data_as_of: datetime
    due_at: datetime | None = None
    questions: list[str] = Field(min_length=1)


class ResearchCaseV1(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: UUID
    case_type: str
    title: str
    priority: str
    state: str
    issuer_id: UUID
    instrument_id: UUID | None
    data_as_of: datetime
    due_at: datetime | None
    created_by: str
    lock_version: int
    created_at: datetime
    updated_at: datetime


class CaseTransitionV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target: str
    reason: str = Field(min_length=1, max_length=1000)


class VerifyClaimV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cutoff: datetime


class ClaimV1(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: UUID
    research_case_id: UUID
    claim_type: str
    text: str
    is_material: bool
    status: str
    confidence: Decimal
    valid_from: datetime
    valid_until: datetime | None


class AssessmentInputV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assessment_type: str = Field(min_length=1, max_length=50)
    author_type: str
    schema_name: str = Field(min_length=1, max_length=100)
    schema_version: str = Field(min_length=1, max_length=50)
    result: dict[str, object]
    data_as_of: datetime
    expires_at: datetime


class AssessmentV1(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: UUID
    research_case_id: UUID
    assessment_type: str
    author_type: str
    author_id: str
    schema_name: str
    schema_version: str
    result: dict[str, object]
    result_sha256: str
    data_as_of: datetime
    expires_at: datetime
    created_at: datetime


class ReviewRequestInputV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reviewer_role: str = Field(min_length=1, max_length=100)
    due_at: datetime | None = None


class ReviewRequestV1(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: UUID
    assessment_id: UUID
    required_reviewer_role: str
    status: str
    requested_by: str
    requested_at: datetime
    due_at: datetime | None


class ReviewDecisionInputV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: str
    comment: str = Field(min_length=1)
    reason: str = Field(min_length=1)


class ReviewDecisionV1(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: UUID
    review_request_id: UUID
    reviewer_id: str
    decision: str
    comment: str
    reason: str
    before_hash: str
    after_hash: str
    correlation_id: UUID
    decided_at: datetime


class ThesisSnapshotV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str = Field(min_length=1)
    assumptions: list[dict[str, object]]
    catalysts: list[dict[str, object]]
    risks: list[dict[str, object]]
    invalidation_criteria: list[dict[str, object]]
    recommendation: str
    recommendation_confidence: Decimal = Field(ge=0, le=1)
    data_as_of: datetime
    expires_at: datetime

    def to_domain(self) -> ThesisSnapshot:
        return ThesisSnapshot(**self.model_dump(mode="python"))


class CreateThesisV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    issuer_id: UUID
    instrument_id: UUID | None = None
    snapshot: ThesisSnapshotV1
    evidence_ids: list[UUID] = Field(min_length=1)
    claim_ids: list[UUID] = Field(min_length=1)


class ReviseThesisV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    snapshot: ThesisSnapshotV1
    evidence_ids: list[UUID] = Field(min_length=1)
    claim_ids: list[UUID] = Field(min_length=1)


class ActivateThesisV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    review_decision_id: UUID


class ThesisV1(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: UUID
    issuer_id: UUID
    instrument_id: UUID | None
    status: str
    lock_version: int
    created_by: str
    created_at: datetime


class ThesisVersionV1(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: UUID
    thesis_id: UUID
    version_number: int
    parent_version_id: UUID | None
    status: str
    summary: str
    recommendation: str
    recommendation_confidence: Decimal
    data_as_of: datetime
    expires_at: datetime
    valid_from: datetime | None
    valid_to: datetime | None
    content_sha256: str
    change_set: dict[str, object]
    created_by: str
    approved_by: str | None
    approved_at: datetime | None


class ThesisCreatedV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    thesis: ThesisV1
    version: ThesisVersionV1


class ValuationAssumptionInputV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=100)
    value: Decimal
    unit: str = Field(min_length=1, max_length=30)
    horizon: str = Field(min_length=1, max_length=50)
    source_type: str
    source_id: UUID
    source_version: str = Field(min_length=1, max_length=100)
    approved_by: str = Field(min_length=1, max_length=255)
    sensitivity_low: Decimal | None = None
    sensitivity_high: Decimal | None = None

    def to_domain(self) -> AssumptionInput:
        return AssumptionInput(**self.model_dump(mode="python"))


class DCFScenarioInputV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    probability: Decimal = Field(ge=0, le=1)
    free_cash_flows: list[Decimal] = Field(min_length=1)
    discount_rate: Decimal
    terminal_growth: Decimal
    net_debt: Decimal
    shares_outstanding: Decimal

    def to_domain(self) -> ScenarioInput:
        return ScenarioInput(
            name=self.name,
            probability=self.probability,
            inputs=DCFInput(
                free_cash_flows=tuple(self.free_cash_flows),
                discount_rate=self.discount_rate,
                terminal_growth=self.terminal_growth,
                net_debt=self.net_debt,
                shares_outstanding=self.shares_outstanding,
            ),
        )


class RelativeInputV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metric: Decimal
    selected_multiple: Decimal
    net_debt: Decimal
    shares_outstanding: Decimal


class ReverseDCFInputV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    market_enterprise_value: Decimal
    starting_cash_flow: Decimal
    discount_rate: Decimal
    years: int = Field(default=5, ge=1, le=50)


class CreateValuationV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    thesis_version_id: UUID
    code_version: str = Field(min_length=1, max_length=100)
    data_as_of: datetime
    assumptions: list[ValuationAssumptionInputV1] = Field(min_length=1)
    scenarios: list[DCFScenarioInputV1] = Field(min_length=3, max_length=3)
    relative: RelativeInputV1
    reverse_dcf: ReverseDCFInputV1


class ValuationResultV1(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    scenario: str
    equity_value: Decimal
    value_per_share: Decimal
    probability: Decimal | None
    result_payload: dict[str, object]


class ValuationRunV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    thesis_version_id: UUID
    model_type: str
    code_version: str
    input_sha256: str
    result_sha256: str
    input_payload: dict[str, object]
    data_as_of: datetime
    status: str
    created_by: str
    created_at: datetime
    replayed: bool
    results: list[ValuationResultV1]

    @classmethod
    def from_execution(cls, execution: ValuationExecution) -> ValuationRunV1:
        run = execution.run
        return cls(
            id=run.id,
            thesis_version_id=run.thesis_version_id,
            model_type=run.model_type,
            code_version=run.code_version,
            input_sha256=run.input_sha256,
            result_sha256=run.result_sha256,
            input_payload=run.input_payload,
            data_as_of=run.data_as_of,
            status=run.status,
            created_by=run.created_by,
            created_at=run.created_at,
            replayed=execution.replayed,
            results=[ValuationResultV1.model_validate(item) for item in execution.results],
        )


def parse_etag(value: str) -> int:
    normalized = value.strip().removeprefix("W/").strip('"')
    try:
        return int(normalized)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="If-Match must contain a numeric case version") from exc


def case_response(case: ResearchCase, response: Response) -> ResearchCaseV1:
    response.headers["ETag"] = f'"{case.lock_version}"'
    return ResearchCaseV1.model_validate(case)


def require_research_read(auth: AuthContext) -> None:
    if "research:read" not in auth.permissions and "research_cases:read" not in auth.permissions:
        raise HTTPException(status_code=403, detail="permission required: research:read")


@router.get("/cases", response_model=list[ResearchCaseV1])
async def list_cases(
    response: Response,
    state: str | None = None,
    as_of: datetime | None = None,
    after: UUID | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
) -> list[ResearchCaseV1]:
    require_research_read(auth)
    svc = ResearchCaseService(session)
    try:
        rows = await svc.list_cases(state=state, as_of=as_of, after=after, limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if len(rows) > limit:
        response.headers["X-Next-Cursor"] = str(rows[limit - 1].id)
        rows = rows[:limit]
    return [ResearchCaseV1.model_validate(item) for item in rows]


@router.get("/cases/{case_id}", response_model=ResearchCaseV1)
async def get_case(
    case_id: UUID,
    response: Response,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
) -> ResearchCaseV1:
    require_research_read(auth)
    case = await ResearchCaseService(session).get_case(case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="research case not found")
    return case_response(case, response)


@router.post("/cases", response_model=ResearchCaseV1, status_code=201)
async def create_case(
    body: CreateResearchCaseV1,
    response: Response,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=255)],
    auth: AuthContext = Depends(require_permission("research_cases:create")),
    correlation_id: UUID | None = Header(default=None, alias="X-Correlation-ID"),
    session: AsyncSession = Depends(get_async_session),
) -> ResearchCaseV1:
    try:
        case, created = await ResearchCaseService(session).create(
            CreateResearchCase(
                case_type=body.case_type,
                title=body.title,
                priority=body.priority,
                issuer_id=body.issuer_id,
                instrument_id=body.instrument_id,
                data_as_of=body.data_as_of,
                due_at=body.due_at,
                questions=tuple(body.questions),
            ),
            auth.subject,
            auth.permissions,
            idempotency_key,
            correlation_id or uuid4(),
        )
    except ResearchIdempotencyConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not created:
        response.status_code = 200
    return case_response(case, response)


@router.post("/cases/{case_id}/transitions", response_model=ResearchCaseV1)
async def transition_case(
    case_id: UUID,
    body: CaseTransitionV1,
    response: Response,
    if_match: Annotated[str, Header(alias="If-Match")],
    auth: AuthContext = Depends(get_auth_context),
    correlation_id: UUID | None = Header(default=None, alias="X-Correlation-ID"),
    session: AsyncSession = Depends(get_async_session),
) -> ResearchCaseV1:
    try:
        case = await ResearchCaseService(session).transition(
            case_id,
            body.target,
            parse_etag(if_match),
            auth.subject,
            auth.permissions,
            correlation_id or uuid4(),
            body.reason,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ResearchConcurrencyError as exc:
        raise HTTPException(status_code=412, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return case_response(case, response)


@router.get("/evidence/search", response_model=list[EvidenceReferenceV1])
async def search_evidence(
    query: str = Query(min_length=1),
    as_of: datetime = Query(),
    embedding: list[float] | None = Query(default=None),
    minimum_score: float = Query(default=0.05, ge=0, le=1),
    limit: int = Query(default=20, ge=1, le=100),
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
) -> list[EvidenceReferenceV1]:
    require_research_read(auth)
    try:
        return await EvidenceRepository(session).search(
            query, as_of, embedding=embedding, minimum_score=minimum_score, limit=limit
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/claims/{claim_id}/verification", response_model=ClaimV1)
async def verify_claim(
    claim_id: UUID,
    body: VerifyClaimV1,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=255)],
    auth: AuthContext = Depends(get_auth_context),
    correlation_id: UUID | None = Header(default=None, alias="X-Correlation-ID"),
    session: AsyncSession = Depends(get_async_session),
) -> ClaimV1:
    try:
        claim = await ClaimService(session).verify(
            claim_id, body.cutoff, auth.subject, auth.permissions, correlation_id or uuid4()
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return ClaimV1.model_validate(claim)


@router.post("/cases/{case_id}/assessments", response_model=AssessmentV1, status_code=201)
async def create_assessment(
    case_id: UUID,
    body: AssessmentInputV1,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=255)],
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
) -> AssessmentV1:
    try:
        row = await ResearchReviewService(session).create_assessment(
            research_case_id=case_id,
            author_id=auth.subject,
            permissions=auth.permissions,
            **body.model_dump(mode="python"),
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return AssessmentV1.model_validate(row)


@router.post("/assessments/{assessment_id}/reviews", response_model=ReviewRequestV1, status_code=201)
async def request_review(
    assessment_id: UUID,
    body: ReviewRequestInputV1,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=255)],
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
) -> ReviewRequestV1:
    try:
        row = await ResearchReviewService(session).request_review(
            assessment_id,
            body.reviewer_role,
            auth.subject,
            body.due_at,
            auth.permissions,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return ReviewRequestV1.model_validate(row)


@router.post("/reviews/{review_request_id}/decision", response_model=ReviewDecisionV1)
async def decide_review(
    review_request_id: UUID,
    body: ReviewDecisionInputV1,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=255)],
    auth: AuthContext = Depends(get_auth_context),
    correlation_id: UUID | None = Header(default=None, alias="X-Correlation-ID"),
    session: AsyncSession = Depends(get_async_session),
) -> ReviewDecisionV1:
    roles = frozenset(value.removeprefix("role:") for value in auth.permissions if value.startswith("role:"))
    try:
        row = await ResearchReviewService(session).decide(
            review_request_id,
            body.decision,
            auth.subject,
            roles,
            auth.permissions,
            body.comment,
            body.reason,
            correlation_id or uuid4(),
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return ReviewDecisionV1.model_validate(row)


@router.post("/theses", response_model=ThesisCreatedV1, status_code=201)
async def create_thesis(
    body: CreateThesisV1,
    response: Response,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=255)],
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
) -> ThesisCreatedV1:
    try:
        thesis, version = await ThesisService(session).create_draft(
            body.issuer_id,
            body.instrument_id,
            body.snapshot.to_domain(),
            auth.subject,
            auth.permissions,
            body.evidence_ids,
            body.claim_ids,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    response.headers["ETag"] = f'"{thesis.lock_version}"'
    return ThesisCreatedV1(thesis=ThesisV1.model_validate(thesis), version=ThesisVersionV1.model_validate(version))


@router.post("/theses/{thesis_id}/versions", response_model=ThesisVersionV1, status_code=201)
async def revise_thesis(
    thesis_id: UUID,
    body: ReviseThesisV1,
    if_match: Annotated[str, Header(alias="If-Match")],
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
) -> ThesisVersionV1:
    try:
        version = await ThesisService(session).revise(
            thesis_id,
            parse_etag(if_match),
            body.snapshot.to_domain(),
            auth.subject,
            auth.permissions,
            body.evidence_ids,
            body.claim_ids,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ResearchConcurrencyError as exc:
        raise HTTPException(status_code=412, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return ThesisVersionV1.model_validate(version)


@router.post("/thesis-versions/{version_id}/activation", response_model=ThesisVersionV1)
async def activate_thesis(
    version_id: UUID,
    body: ActivateThesisV1,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=255)],
    auth: AuthContext = Depends(get_auth_context),
    correlation_id: UUID | None = Header(default=None, alias="X-Correlation-ID"),
    session: AsyncSession = Depends(get_async_session),
) -> ThesisVersionV1:
    try:
        version = await ThesisService(session).activate(
            version_id,
            body.review_decision_id,
            auth.subject,
            auth.permissions,
            correlation_id or uuid4(),
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return ThesisVersionV1.model_validate(version)


@router.get("/theses/{thesis_id}", response_model=ThesisVersionV1)
async def get_thesis_as_of(
    thesis_id: UUID,
    as_of: datetime,
    response: Response,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
) -> ThesisVersionV1:
    require_research_read(auth)
    try:
        version = await ThesisService(session).active_as_of(thesis_id, as_of)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if version is None:
        raise HTTPException(status_code=404, detail="active thesis version not found at cutoff")
    lock_version = await ThesisService(session).get_lock_version(thesis_id)
    if lock_version is not None:
        response.headers["ETag"] = f'"{lock_version}"'
    return ThesisVersionV1.model_validate(version)


@router.post("/valuations", response_model=ValuationRunV1, status_code=201)
async def create_valuation(
    body: CreateValuationV1,
    response: Response,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=255)],
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
) -> ValuationRunV1:
    command = ValuationCommand(
        thesis_version_id=body.thesis_version_id,
        code_version=body.code_version,
        data_as_of=body.data_as_of,
        assumptions=tuple(item.to_domain() for item in body.assumptions),
        scenarios=tuple(item.to_domain() for item in body.scenarios),
        relative=RelativeInput(**body.relative.model_dump(mode="python")),
        reverse_dcf=ReverseDCFInput(**body.reverse_dcf.model_dump(mode="python")),
    )
    try:
        execution = await ValuationService(session).execute(command, auth.subject, auth.permissions)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if execution.replayed:
        response.status_code = 200
    response.headers["ETag"] = f'"{execution.run.input_sha256}"'
    return ValuationRunV1.from_execution(execution)


@router.get("/valuations/{run_id}", response_model=ValuationRunV1)
async def get_valuation(
    run_id: UUID,
    response: Response,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
) -> ValuationRunV1:
    try:
        execution = await ValuationService(session).get(run_id, auth.permissions)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    response.headers["ETag"] = f'"{execution.run.input_sha256}"'
    return ValuationRunV1.from_execution(execution)
