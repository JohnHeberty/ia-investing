from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.security import AuthContext, get_auth_context
from database.core import get_async_session
from ia_investing.application.paper_execution import PaperExecutionService
from ia_investing.domain.identity import InstitutionalAccessContext

router = APIRouter(prefix="/api/v1/paper", tags=["paper-execution"])


def context_from(auth: AuthContext) -> InstitutionalAccessContext:
    if auth.organization_id is None:
        raise HTTPException(status_code=403, detail="institutional organization context is required")
    return InstitutionalAccessContext(auth.subject, auth.organization_id, auth.team_ids, auth.permissions, "paper")


class CreateTradeIntentV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    portfolio_version_id: UUID
    instrument_id: UUID
    side: str = Field(pattern=r"^(buy|sell)$")
    quantity: Decimal = Field(gt=0)
    order_type: str = Field(pattern=r"^(market|limit)$")
    limit_price: Decimal | None = Field(default=None, gt=0)
    earliest_execution_at: datetime
    expires_at: datetime
    reason: str = Field(min_length=1, max_length=2_000)


class DecideTradeIntentV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    approved: bool
    rationale: str = Field(min_length=1, max_length=2_000)


class CancelTradeIntentV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=1, max_length=2_000)


class SimulateOrderV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    execution_model_version_id: UUID
    seed: int


class TradeIntentV1(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: UUID
    organization_id: UUID
    portfolio_id: UUID
    portfolio_version_id: UUID
    instrument_id: UUID
    side: str
    quantity: Decimal
    order_type: str
    limit_price: Decimal | None
    earliest_execution_at: datetime
    expires_at: datetime
    reason: str
    status: str
    environment: str
    created_by: str
    approved_by: str | None
    created_at: datetime
    updated_at: datetime


class PaperFillV1(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: UUID
    order_id: UUID
    sequence: int
    quantity: Decimal
    price: Decimal
    gross_value: Decimal
    fee_value: Decimal
    tax_value: Decimal
    slippage_bps: Decimal
    market_timestamp: datetime
    filled_at: datetime
    environment: str


class PaperOrderV1(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: UUID
    trade_intent_id: UUID
    execution_model_version_id: UUID
    status: str
    requested_quantity: Decimal
    filled_quantity: Decimal
    input_sha256: str
    seed: int
    environment: str
    accepted_at: datetime | None
    completed_at: datetime | None
    created_at: datetime


class SimulationResponseV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    order: PaperOrderV1
    fills: list[PaperFillV1]


class ReconciliationBreakV1(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: UUID
    organization_id: UUID
    portfolio_id: UUID
    as_of: datetime
    rule: str
    resource_key: str
    expected: dict[str, object]
    actual: dict[str, object]
    severity: str
    owner_role: str
    status: str
    blocking: bool
    resolution: dict[str, object] | None
    detected_at: datetime
    resolved_at: datetime | None


class ResolveBreakV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    method: str = Field(min_length=1)
    evidence: str = Field(min_length=1)
    compensating_reference: str | None = None


class OperationalAlertV1(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: UUID
    organization_id: UUID
    portfolio_id: UUID | None
    deduplication_key: str
    alert_type: str
    severity: str
    rule_version: str
    route: str
    status: str
    payload: dict[str, object]
    acknowledged_by: str | None
    created_at: datetime
    acknowledged_at: datetime | None


class KillSwitchInputV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    portfolio_id: UUID | None = None
    reason: str = Field(min_length=1, max_length=2_000)


class KillSwitchV1(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: UUID
    organization_id: UUID
    portfolio_id: UUID | None
    active: bool
    reason: str
    activated_by: str
    activated_at: datetime
    released_by: str | None
    released_at: datetime | None


class PostMortemInputV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    period_start: datetime
    period_end: datetime
    expected: dict[str, object]
    realized: dict[str, object]
    attribution: dict[str, object]
    findings: list[dict[str, object]]
    dissent: list[dict[str, object]] = Field(default_factory=list)


class PostMortemV1(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: UUID
    organization_id: UUID
    portfolio_id: UUID
    version: int
    period_start: datetime
    period_end: datetime
    expected: dict[str, object]
    realized: dict[str, object]
    attribution: dict[str, object]
    findings: list[dict[str, object]]
    dissent: list[dict[str, object]]
    content_sha256: str
    created_by: str
    created_at: datetime


class ChallengerInputV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    champion_portfolio_id: UUID
    challenger_portfolio_id: UUID
    window_start: datetime
    window_end: datetime
    methodology_version: str
    comparison_config: dict[str, object]
    metrics: dict[str, object]
    evidence: dict[str, object]


class ChallengerDecisionInputV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: str = Field(pattern=r"^(retained|promoted|rejected)$")


class ChallengerV1(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: UUID
    mandate_id: UUID
    champion_portfolio_id: UUID
    challenger_portfolio_id: UUID
    window_start: datetime
    window_end: datetime
    methodology_version: str
    comparison_sha256: str
    comparison_config: dict[str, object]
    metrics: dict[str, object]
    evidence: dict[str, object]
    decision: str
    created_by: str
    decided_by: str | None
    decided_at: datetime | None


def map_error(exc: Exception) -> HTTPException:
    if isinstance(exc, LookupError):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, PermissionError):
        return HTTPException(status_code=403, detail=str(exc))
    return HTTPException(status_code=409, detail=str(exc))


@router.post("/trade-intents", response_model=TradeIntentV1, status_code=201)
async def create_trade_intent(
    body: CreateTradeIntentV1,
    response: Response,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=200)],
    correlation_id: Annotated[UUID | None, Header(alias="X-Correlation-ID")] = None,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
) -> TradeIntentV1:
    try:
        intent, created = await PaperExecutionService(session).create_intent(
            **body.model_dump(mode="python"),
            idempotency_key=idempotency_key,
            context=context_from(auth),
            correlation_id=correlation_id or uuid4(),
        )
    except (LookupError, PermissionError, ValueError) as exc:
        raise map_error(exc) from exc
    if not created:
        response.status_code = 200
    response.headers["X-Execution-Environment"] = "paper"
    return TradeIntentV1.model_validate(intent)


@router.post("/trade-intents/{intent_id}/decision", response_model=TradeIntentV1)
async def decide_trade_intent(
    intent_id: UUID,
    body: DecideTradeIntentV1,
    correlation_id: Annotated[UUID | None, Header(alias="X-Correlation-ID")] = None,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
) -> TradeIntentV1:
    try:
        intent = await PaperExecutionService(session).decide_intent(
            intent_id,
            **body.model_dump(),
            context=context_from(auth),
            correlation_id=correlation_id or uuid4(),
        )
    except (LookupError, PermissionError, ValueError) as exc:
        raise map_error(exc) from exc
    return TradeIntentV1.model_validate(intent)


@router.post("/trade-intents/{intent_id}/cancel", response_model=TradeIntentV1)
async def cancel_trade_intent(
    intent_id: UUID,
    body: CancelTradeIntentV1,
    correlation_id: Annotated[UUID | None, Header(alias="X-Correlation-ID")] = None,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
) -> TradeIntentV1:
    try:
        intent = await PaperExecutionService(session).cancel_intent(
            intent_id,
            reason=body.reason,
            context=context_from(auth),
            correlation_id=correlation_id or uuid4(),
        )
    except (LookupError, PermissionError, ValueError) as exc:
        raise map_error(exc) from exc
    return TradeIntentV1.model_validate(intent)


@router.post("/trade-intents/{intent_id}/simulate", response_model=SimulationResponseV1)
async def simulate_trade_intent(
    intent_id: UUID,
    body: SimulateOrderV1,
    correlation_id: Annotated[UUID | None, Header(alias="X-Correlation-ID")] = None,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
) -> SimulationResponseV1:
    try:
        order, fills = await PaperExecutionService(session).simulate(
            intent_id,
            **body.model_dump(),
            context=context_from(auth),
            correlation_id=correlation_id or uuid4(),
        )
    except (LookupError, PermissionError, ValueError, KeyError) as exc:
        raise map_error(exc) from exc
    return SimulationResponseV1(
        order=PaperOrderV1.model_validate(order),
        fills=[PaperFillV1.model_validate(fill) for fill in fills],
    )


@router.get("/trade-intents", response_model=list[TradeIntentV1])
async def list_trade_intents(
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
) -> list[TradeIntentV1]:
    context = context_from(auth)
    if "portfolio:read" not in context.permissions:
        raise HTTPException(status_code=403, detail="permission required: portfolio:read")
    rows = await PaperExecutionService(session).list_trade_intents(context.organization_id)
    return [TradeIntentV1.model_validate(row) for row in rows]


@router.get("/orders/{order_id}", response_model=SimulationResponseV1)
async def get_paper_order(
    order_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
) -> SimulationResponseV1:
    context = context_from(auth)
    result = await PaperExecutionService(session).get_order_with_intent(order_id, context.organization_id)
    if result is None:
        raise HTTPException(status_code=404, detail="paper order not found")
    order, _intent = result
    if "portfolio:read" not in context.permissions:
        raise HTTPException(status_code=403, detail="permission required: portfolio:read")
    fills = await PaperExecutionService(session).list_fills_for_order(order.id)
    return SimulationResponseV1(
        order=PaperOrderV1.model_validate(order),
        fills=[PaperFillV1.model_validate(fill) for fill in fills],
    )


@router.post("/portfolios/{portfolio_id}/reconciliations", response_model=list[ReconciliationBreakV1])
async def reconcile_paper_portfolio(
    portfolio_id: UUID,
    as_of: datetime,
    correlation_id: Annotated[UUID | None, Header(alias="X-Correlation-ID")] = None,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
) -> list[ReconciliationBreakV1]:
    try:
        rows = await PaperExecutionService(session).reconcile_portfolio(
            portfolio_id,
            as_of=as_of,
            context=context_from(auth),
            correlation_id=correlation_id or uuid4(),
        )
    except (LookupError, PermissionError, ValueError) as exc:
        raise map_error(exc) from exc
    return [ReconciliationBreakV1.model_validate(row) for row in rows]


@router.post("/reconciliation-breaks/{break_id}/resolution", response_model=ReconciliationBreakV1)
async def resolve_reconciliation_break(
    break_id: UUID,
    body: ResolveBreakV1,
    correlation_id: Annotated[UUID | None, Header(alias="X-Correlation-ID")] = None,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
) -> ReconciliationBreakV1:
    try:
        row = await PaperExecutionService(session).resolve_break(
            break_id,
            resolution=body.model_dump(exclude_none=True),
            context=context_from(auth),
            correlation_id=correlation_id or uuid4(),
        )
    except (LookupError, PermissionError, ValueError) as exc:
        raise map_error(exc) from exc
    return ReconciliationBreakV1.model_validate(row)


@router.post("/alerts/{alert_id}/acknowledgement", response_model=OperationalAlertV1)
async def acknowledge_operational_alert(
    alert_id: UUID,
    correlation_id: Annotated[UUID | None, Header(alias="X-Correlation-ID")] = None,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
) -> OperationalAlertV1:
    try:
        row = await PaperExecutionService(session).acknowledge_alert(
            alert_id, context=context_from(auth), correlation_id=correlation_id or uuid4()
        )
    except (LookupError, PermissionError, ValueError) as exc:
        raise map_error(exc) from exc
    return OperationalAlertV1.model_validate(row)


@router.post("/kill-switches", response_model=KillSwitchV1, status_code=201)
async def activate_paper_kill_switch(
    body: KillSwitchInputV1,
    correlation_id: Annotated[UUID | None, Header(alias="X-Correlation-ID")] = None,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
) -> KillSwitchV1:
    try:
        row = await PaperExecutionService(session).activate_kill_switch(
            **body.model_dump(), context=context_from(auth), correlation_id=correlation_id or uuid4()
        )
    except (LookupError, PermissionError, ValueError) as exc:
        raise map_error(exc) from exc
    return KillSwitchV1.model_validate(row)


@router.post("/kill-switches/{switch_id}/release", response_model=KillSwitchV1)
async def release_paper_kill_switch(
    switch_id: UUID,
    correlation_id: Annotated[UUID | None, Header(alias="X-Correlation-ID")] = None,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
) -> KillSwitchV1:
    try:
        row = await PaperExecutionService(session).release_kill_switch(
            switch_id, context=context_from(auth), correlation_id=correlation_id or uuid4()
        )
    except (LookupError, PermissionError, ValueError) as exc:
        raise map_error(exc) from exc
    return KillSwitchV1.model_validate(row)


@router.post("/portfolios/{portfolio_id}/post-mortems", response_model=PostMortemV1, status_code=201)
async def create_paper_post_mortem(
    portfolio_id: UUID,
    body: PostMortemInputV1,
    correlation_id: Annotated[UUID | None, Header(alias="X-Correlation-ID")] = None,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
) -> PostMortemV1:
    try:
        row = await PaperExecutionService(session).create_post_mortem(
            portfolio_id,
            **body.model_dump(mode="python"),
            context=context_from(auth),
            correlation_id=correlation_id or uuid4(),
        )
    except (LookupError, PermissionError, ValueError) as exc:
        raise map_error(exc) from exc
    return PostMortemV1.model_validate(row)


@router.post("/challenger-evaluations", response_model=ChallengerV1, status_code=201)
async def create_challenger_evaluation(
    body: ChallengerInputV1,
    correlation_id: Annotated[UUID | None, Header(alias="X-Correlation-ID")] = None,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
) -> ChallengerV1:
    try:
        row = await PaperExecutionService(session).create_challenger_evaluation(
            **body.model_dump(mode="python"),
            context=context_from(auth),
            correlation_id=correlation_id or uuid4(),
        )
    except (LookupError, PermissionError, ValueError) as exc:
        raise map_error(exc) from exc
    return ChallengerV1.model_validate(row)


@router.post("/challenger-evaluations/{evaluation_id}/decision", response_model=ChallengerV1)
async def decide_challenger_evaluation(
    evaluation_id: UUID,
    body: ChallengerDecisionInputV1,
    correlation_id: Annotated[UUID | None, Header(alias="X-Correlation-ID")] = None,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
) -> ChallengerV1:
    try:
        row = await PaperExecutionService(session).decide_challenger(
            evaluation_id,
            decision=body.decision,
            context=context_from(auth),
            correlation_id=correlation_id or uuid4(),
        )
    except (LookupError, PermissionError, ValueError) as exc:
        raise map_error(exc) from exc
    return ChallengerV1.model_validate(row)
