from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.security import AuthContext, get_auth_context
from database.core import get_async_session
from database.models.portfolio_domain import ModelPortfolio
from ia_investing.application.backtests import InstitutionalBacktestService
from ia_investing.application.institutional_portfolio import (
    InstitutionalPortfolioService,
    PortfolioConcurrencyError,
)
from ia_investing.application.portfolio import BackendPortfolioOptimizationService
from ia_investing.domain.backtest import (
    HistoricalUniverseMember,
    InstitutionalBacktestConfig,
    MarketSession,
    PointInTimeCorporateAction,
    PointInTimePrice,
    PointInTimeSignal,
)
from ia_investing.domain.identity import InstitutionalAccessContext

router = APIRouter(prefix="/api/v1", tags=["institutional-portfolios"])


def institutional_context(auth: AuthContext) -> InstitutionalAccessContext:
    if auth.organization_id is None:
        raise HTTPException(status_code=403, detail="Institutional organization context is required")
    return InstitutionalAccessContext(auth.subject, auth.organization_id, auth.team_ids, auth.permissions, "paper")


class CreateMandateV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    logical_id: str = Field(pattern=r"^[a-z][a-z0-9_-]*$")
    objective: str = Field(min_length=1)
    strategy_type: str
    universe_definition: dict[str, object]
    benchmark_index_id: UUID
    benchmark_in_universe: bool = False
    base_currency: str = Field(default="BRL", pattern=r"^[A-Z]{3}$")
    investment_horizon_days: int = Field(gt=0)
    rebalance_policy: dict[str, object]
    risk_budget: dict[str, object]
    target_volatility: Decimal | None = Field(default=None, ge=0, le=1)
    max_drawdown: Decimal = Field(ge=0, le=1)
    concentration_limits: dict[str, object]
    factor_limits: dict[str, object]
    liquidity_policy: dict[str, object]
    min_cash_weight: Decimal = Field(ge=0, le=1)
    max_cash_weight: Decimal = Field(ge=0, le=1)
    max_turnover: Decimal = Field(ge=0, le=2)
    exclusions: dict[str, object]
    cost_policy: dict[str, object]
    tax_policy: dict[str, object]
    approval_policy: dict[str, object]


class MandateV1(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: UUID
    organization_id: UUID
    logical_id: str
    version: int
    objective: str
    strategy_type: str
    base_currency: str
    content_sha256: str
    status: str
    created_by: str
    created_at: datetime


class CreateModelPortfolioV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mandate_id: UUID
    owner_team_id: UUID
    name: str = Field(min_length=1, max_length=200)


class ModelPortfolioV1(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: UUID
    organization_id: UUID
    owner_team_id: UUID
    mandate_id: UUID
    name: str
    base_currency: str
    state: str
    environment: str
    lock_version: int
    created_by: str
    created_at: datetime
    updated_at: datetime


class PortfolioTransitionV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target: str
    reason: str = Field(min_length=1, max_length=2_000)


class PositionSnapshotInputV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    instrument_id: UUID
    quantity: Decimal = Field(ge=0)
    cost_basis: Decimal = Field(ge=0)


class CashSnapshotInputV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    currency: str = Field(pattern=r"^[A-Z]{3}$")
    amount: Decimal = Field(ge=0)


class CreatePortfolioVersionV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    as_of: datetime
    positions: list[PositionSnapshotInputV1]
    cash: list[CashSnapshotInputV1]
    proposal: dict[str, object]
    thesis_version_ids: list[UUID] = Field(min_length=1)
    valuation_run_ids: list[UUID] = Field(min_length=1)


class PortfolioVersionV1(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: UUID
    portfolio_id: UUID
    mandate_id: UUID
    version: int
    as_of: datetime
    input_snapshot_sha256: str
    weights_sha256: str
    approved_weights: dict[str, object]
    proposal: dict[str, object]
    decision: dict[str, object] | None
    status: str
    created_by: str
    approved_by: str | None
    created_at: datetime


class ApprovalDecisionV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    optimization_run_id: UUID
    risk_snapshot_id: UUID
    rationale: str = Field(min_length=1)
    votes: list[dict[str, object]] = Field(min_length=1)


class NavPublicationV1(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: UUID
    portfolio_id: UUID
    portfolio_version_id: UUID
    as_of: datetime
    revision: int
    methodology_version: str
    input_sha256: str
    input_details: dict[str, object]
    cash_value: Decimal
    positions_value: Decimal
    gross_pnl: Decimal
    net_pnl: Decimal
    fees_value: Decimal
    taxes_value: Decimal
    nav: Decimal
    benchmark_value: Decimal | None
    benchmark_return: Decimal | None
    reconciled: bool
    published_by: str
    created_at: datetime


class PositionSnapshotV1(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: UUID
    portfolio_version_id: UUID
    instrument_id: UUID
    quantity: Decimal
    cost_basis: Decimal
    as_of: datetime


class RiskAssessmentInputV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    policy_id: UUID
    as_of: datetime


class RiskBreachV1(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: UUID
    risk_snapshot_id: UUID
    limit_name: str
    limit_type: str
    observed_value: Decimal
    limit_value: Decimal
    status: str


class RiskAssessmentV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    snapshot_id: UUID
    as_of: datetime
    input_sha256: str
    exposures: dict[str, object]
    concentration: dict[str, object]
    liquidity: dict[str, object]
    volatility: Decimal | None
    drawdown: Decimal | None
    breaches: list[RiskBreachV1]


class RiskWaiverInputV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=1, max_length=2_000)
    expires_at: datetime


class RiskWaiverV1(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: UUID
    breach_id: UUID
    granted_by: str
    reason: str
    granted_at: datetime
    expires_at: datetime


class OptimizationRunV1(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: UUID
    portfolio_id: UUID
    as_of: datetime
    input_sha256: str
    solver: str
    solver_version: str
    tolerances: dict[str, object]
    status: str
    weights: dict[str, object]
    trades: list[dict[str, object]]
    slacks: dict[str, object]
    diagnostics: dict[str, object]
    created_at: datetime


class BacktestMarketSessionV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_date: date
    close_at: datetime


class BacktestSignalV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    instrument_id: str
    signal_date: date
    knowledge_at: datetime
    score: Decimal
    source: str = "quant"


class BacktestUniverseMemberV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    instrument_id: str
    valid_from: date
    valid_to: date | None = None
    knowledge_at: datetime


class BacktestPriceV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    instrument_id: str
    session_date: date
    knowledge_at: datetime
    close: Decimal = Field(gt=0)


class BacktestCorporateActionV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    instrument_id: str
    effective_date: date
    knowledge_at: datetime
    action_type: str
    value: Decimal
    tax_rate: Decimal = Field(default=Decimal(0), ge=0, le=1)


class RunBacktestV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    strategy_name: str = Field(min_length=1, max_length=200)
    universe_definition: dict[str, object]
    benchmark_index_id: UUID
    benchmark_instrument_id: str | None = None
    start_date: date
    end_date: date
    signal_delay_sessions: int = Field(ge=1)
    top_n: int = Field(ge=1)
    initial_cash: Decimal = Field(gt=0)
    transaction_cost_bps: Decimal = Field(default=Decimal(0), ge=0)
    sell_tax_bps: Decimal = Field(default=Decimal(0), ge=0)
    seed: int = 0
    code_version: str = Field(min_length=1, max_length=100)
    sessions: list[BacktestMarketSessionV1] = Field(min_length=1)
    signals: list[BacktestSignalV1]
    universe_members: list[BacktestUniverseMemberV1]
    prices: list[BacktestPriceV1] = Field(min_length=1)
    corporate_actions: list[BacktestCorporateActionV1] = Field(default_factory=list)


class BacktestRunV1(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: UUID
    config_id: UUID
    code_version: str
    data_snapshot_sha256: str
    status: str
    result_sha256: str | None
    results: dict[str, object] | None
    created_at: datetime


def set_etag(portfolio: ModelPortfolio, response: Response) -> ModelPortfolioV1:
    response.headers["ETag"] = f'"{portfolio.lock_version}"'
    return ModelPortfolioV1.model_validate(portfolio)


def parse_etag(value: str) -> int:
    try:
        return int(value.strip().removeprefix("W/").strip('"'))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="If-Match must contain a numeric portfolio version") from exc


@router.post("/mandates", response_model=MandateV1, status_code=201)
async def create_mandate(
    body: CreateMandateV1,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=255)],
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
) -> MandateV1:
    try:
        mandate = await InstitutionalPortfolioService(session).create_mandate(
            body.model_dump(mode="python"), institutional_context(auth)
        )
    except (PermissionError, ValueError) as exc:
        raise HTTPException(status_code=403 if isinstance(exc, PermissionError) else 409, detail=str(exc)) from exc
    return MandateV1.model_validate(mandate)


@router.post("/model-portfolios", response_model=ModelPortfolioV1, status_code=201)
async def create_model_portfolio(
    body: CreateModelPortfolioV1,
    response: Response,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=255)],
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
) -> ModelPortfolioV1:
    try:
        portfolio = await InstitutionalPortfolioService(session).create_portfolio(
            mandate_id=body.mandate_id,
            owner_team_id=body.owner_team_id,
            name=body.name,
            context=institutional_context(auth),
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return set_etag(portfolio, response)


@router.get("/model-portfolios/{portfolio_id}", response_model=ModelPortfolioV1)
async def get_model_portfolio(
    portfolio_id: UUID,
    response: Response,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
) -> ModelPortfolioV1:
    context = institutional_context(auth)
    portfolio = await InstitutionalPortfolioService(session).get_portfolio(portfolio_id, context.organization_id)
    if portfolio is None:
        raise HTTPException(status_code=404, detail="portfolio not found")
    if "portfolio:read" not in context.permissions:
        raise HTTPException(status_code=403, detail="permission required: portfolio:read")
    return set_etag(portfolio, response)


@router.get("/model-portfolios", response_model=list[ModelPortfolioV1])
async def list_model_portfolios(
    response: Response,
    limit: int = Query(default=50, ge=1, le=200),
    after: UUID | None = None,
    state: str | None = None,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
) -> list[ModelPortfolioV1]:
    context = institutional_context(auth)
    if "portfolio:read" not in context.permissions:
        raise HTTPException(status_code=403, detail="permission required: portfolio:read")
    rows, has_more = await InstitutionalPortfolioService(session).list_model_portfolios(
        context.organization_id, limit=limit, after=after, state=state
    )
    if has_more:
        response.headers["X-Next-Cursor"] = str(rows[-1].id)
    return [ModelPortfolioV1.model_validate(item) for item in rows]


@router.post("/model-portfolios/{portfolio_id}/transitions", response_model=ModelPortfolioV1)
async def transition_model_portfolio(
    portfolio_id: UUID,
    body: PortfolioTransitionV1,
    response: Response,
    if_match: Annotated[str, Header(alias="If-Match")],
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
) -> ModelPortfolioV1:
    try:
        portfolio = await InstitutionalPortfolioService(session).transition(
            portfolio_id, body.target, parse_etag(if_match), body.reason, institutional_context(auth)
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PortfolioConcurrencyError as exc:
        raise HTTPException(status_code=412, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return set_etag(portfolio, response)


@router.post("/model-portfolios/{portfolio_id}/versions", response_model=PortfolioVersionV1, status_code=201)
async def create_portfolio_version(
    portfolio_id: UUID,
    body: CreatePortfolioVersionV1,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=255)],
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
) -> PortfolioVersionV1:
    try:
        version = await InstitutionalPortfolioService(session).create_version(
            portfolio_id=portfolio_id,
            as_of=body.as_of,
            positions=tuple((item.instrument_id, item.quantity, item.cost_basis) for item in body.positions),
            cash=tuple((item.currency, item.amount) for item in body.cash),
            proposal=body.proposal,
            thesis_version_ids=tuple(body.thesis_version_ids),
            valuation_run_ids=tuple(body.valuation_run_ids),
            context=institutional_context(auth),
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return PortfolioVersionV1.model_validate(version)


@router.post("/portfolio-versions/{version_id}/approval", response_model=PortfolioVersionV1)
async def approve_portfolio_version(
    version_id: UUID,
    body: ApprovalDecisionV1,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=255)],
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
) -> PortfolioVersionV1:
    try:
        version = await InstitutionalPortfolioService(session).approve_version(
            version_id,
            body.optimization_run_id,
            body.risk_snapshot_id,
            body.model_dump(mode="json", exclude={"optimization_run_id", "risk_snapshot_id"}),
            institutional_context(auth),
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return PortfolioVersionV1.model_validate(version)


@router.get("/portfolio-versions/{version_id}", response_model=PortfolioVersionV1)
async def get_portfolio_version(
    version_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
) -> PortfolioVersionV1:
    context = institutional_context(auth)
    result = await InstitutionalPortfolioService(session).get_portfolio_version_with_portfolio(
        version_id, context.organization_id
    )
    if result is None:
        raise HTTPException(status_code=404, detail="portfolio version not found")
    if "portfolio:read" not in context.permissions:
        raise HTTPException(status_code=403, detail="permission required: portfolio:read")
    return PortfolioVersionV1.model_validate(result[0])


@router.get("/portfolio-versions/{version_id}/positions", response_model=list[PositionSnapshotV1])
async def list_portfolio_positions(
    version_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
) -> list[PositionSnapshotV1]:
    await get_portfolio_version(version_id, auth, session)
    rows = await InstitutionalPortfolioService(session).list_positions(version_id)
    return [PositionSnapshotV1.model_validate(item) for item in rows]


@router.post("/portfolio-versions/{version_id}/nav", response_model=NavPublicationV1, status_code=201)
async def publish_nav(
    version_id: UUID,
    as_of: datetime,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=255)],
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
) -> NavPublicationV1:
    try:
        publication = await InstitutionalPortfolioService(session).publish_nav(
            version_id, as_of, institutional_context(auth)
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return NavPublicationV1.model_validate(publication)


@router.get("/model-portfolios/{portfolio_id}/nav", response_model=list[NavPublicationV1])
async def list_nav_publications(
    portfolio_id: UUID,
    as_of: datetime | None = None,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
) -> list[NavPublicationV1]:
    await get_model_portfolio(portfolio_id, Response(), auth, session)
    rows = await InstitutionalPortfolioService(session).list_nav_publications(portfolio_id, as_of=as_of)
    return [NavPublicationV1.model_validate(item) for item in rows]


@router.post("/portfolio-versions/{version_id}/risk-assessments", response_model=RiskAssessmentV1, status_code=201)
async def assess_portfolio_risk(
    version_id: UUID,
    body: RiskAssessmentInputV1,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=255)],
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
) -> RiskAssessmentV1:
    try:
        snapshot, breaches = await InstitutionalPortfolioService(session).assess_risk(
            version_id, body.policy_id, body.as_of, institutional_context(auth)
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return RiskAssessmentV1(
        snapshot_id=snapshot.id,
        as_of=snapshot.as_of,
        input_sha256=snapshot.input_sha256,
        exposures=snapshot.exposures,
        concentration=snapshot.concentration,
        liquidity=snapshot.liquidity,
        volatility=snapshot.volatility,
        drawdown=snapshot.drawdown,
        breaches=[RiskBreachV1.model_validate(item) for item in breaches],
    )


@router.get("/risk-assessments/{snapshot_id}/breaches", response_model=list[RiskBreachV1])
async def list_risk_breaches(
    snapshot_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
) -> list[RiskBreachV1]:
    context = institutional_context(auth)
    result = await InstitutionalPortfolioService(session).list_risk_breaches(snapshot_id, context.organization_id)
    if result is None:
        raise HTTPException(status_code=404, detail="risk assessment not found")
    if "portfolio:read" not in context.permissions:
        raise HTTPException(status_code=403, detail="permission required: portfolio:read")
    _, rows = result
    return [RiskBreachV1.model_validate(item) for item in rows]


@router.post("/risk-breaches/{breach_id}/waivers", response_model=RiskWaiverV1, status_code=201)
async def waive_risk_breach(
    breach_id: UUID,
    body: RiskWaiverInputV1,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=255)],
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
) -> RiskWaiverV1:
    try:
        waiver = await InstitutionalPortfolioService(session).waive_breach(
            breach_id, body.reason, body.expires_at, institutional_context(auth)
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return RiskWaiverV1.model_validate(waiver)


@router.post("/model-portfolios/{portfolio_id}/optimizations", response_model=OptimizationRunV1, status_code=201)
async def optimize_model_portfolio(
    portfolio_id: UUID,
    as_of: datetime,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=255)],
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
) -> OptimizationRunV1:
    try:
        run = await BackendPortfolioOptimizationService(session).optimize(
            portfolio_id, as_of, institutional_context(auth)
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return OptimizationRunV1.model_validate(run)


@router.post("/backtests", response_model=BacktestRunV1, status_code=201)
async def run_institutional_backtest(
    body: RunBacktestV1,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=255)],
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
) -> BacktestRunV1:
    try:
        run = await InstitutionalBacktestService(session).run(
            config=InstitutionalBacktestConfig(
                body.start_date,
                body.end_date,
                body.signal_delay_sessions,
                body.top_n,
                body.initial_cash,
                body.transaction_cost_bps,
                body.sell_tax_bps,
                body.seed,
            ),
            strategy_name=body.strategy_name,
            universe_definition=body.universe_definition,
            benchmark_index_id=body.benchmark_index_id,
            benchmark_instrument_id=body.benchmark_instrument_id,
            sessions=tuple(MarketSession(item.session_date, item.close_at) for item in body.sessions),
            signals=tuple(
                PointInTimeSignal(
                    item.instrument_id,
                    item.signal_date,
                    item.knowledge_at,
                    item.score,
                    item.source,
                )
                for item in body.signals
            ),
            universe_members=tuple(
                HistoricalUniverseMember(item.instrument_id, item.valid_from, item.valid_to, item.knowledge_at)
                for item in body.universe_members
            ),
            prices=tuple(
                PointInTimePrice(item.instrument_id, item.session_date, item.knowledge_at, item.close)
                for item in body.prices
            ),
            corporate_actions=tuple(
                PointInTimeCorporateAction(
                    item.instrument_id,
                    item.effective_date,
                    item.knowledge_at,
                    item.action_type,
                    item.value,
                    item.tax_rate,
                )
                for item in body.corporate_actions
            ),
            code_version=body.code_version,
            context=institutional_context(auth),
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return BacktestRunV1.model_validate(run)


@router.get("/backtests/{run_id}", response_model=BacktestRunV1)
async def get_institutional_backtest(
    run_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
) -> BacktestRunV1:
    try:
        run = await InstitutionalBacktestService(session).get(run_id, institutional_context(auth))
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return BacktestRunV1.model_validate(run)
