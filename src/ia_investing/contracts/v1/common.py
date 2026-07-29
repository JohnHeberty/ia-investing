from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class PaginatedResponse(BaseModel):
    """Standard offset-based pagination envelope."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    items: list[Any]
    total: int
    limit: int
    offset: int


class HealthCheckResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: str
    checks: dict[str, str]


class CalibrationStatusResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    components: dict[str, Any]
    gate_status: dict[str, Any]
    uncalibrated: list[str]


class ComponentStatusResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    component: str
    calibration_score: float
    drift: dict[str, Any]
    reliability: list[dict[str, Any]]
    gate: dict[str, Any]


class OverrideResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    component: str
    reason: str
    created_at: str
    expires_at: str
    requested_by: str


class OverrideActiveResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    component: str
    reason: str
    requested_by: str
    created_at: str
    expires_at: str
    active: bool


class ExecutionCreatedResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    order_id: str
    state: str
    action: str
    quantity: str


class ExecutionListItem(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    order_id: str
    portfolio_id: str
    action: str
    quantity: str
    state: str
    created_at: str | None = None


class ExecutionStateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    state: str


class ExecutionDispatchedResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    state: str
    dispatched_at: str | None = None


class ExecutionConfirmedResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    state: str
    filled_quantity: str
    avg_price: str


class ExecutionFailedResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    state: str
    reason: str


class ExecutionSettledResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    state: str
    settled_at: str | None = None


class CommitteeSessionCreatedResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    state: str
    scheduled_at: str


class CommitteeSessionListItem(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    state: str
    scheduled_at: str | None = None
    total_members: int
    present_members: int
    created_at: str | None = None


class CommitteeSessionDetailResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    state: str
    present_members: int | None = None


class CommitteeVotingResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    state: str
    proposals: list[Any]


class CommitteeVoteResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    vote: str
    proposal_id: str


class CommitteeFinalizeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    state: str
    votes_in_favor: int
    votes_against: int


class CommitteePublishResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    state: str
    decision: str
    published_at: str | None = None


class RebalanceProposalCreatedResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    state: str
    portfolio_id: str
    target_allocations: dict[str, float]
    rationale: str
    created_by: str


class RebalanceProposalListItem(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    state: str
    portfolio_id: str
    target_allocations: dict[str, float]
    rationale: str
    created_by: str


class RebalanceProposalDetailResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    state: str
    portfolio_id: str
    target_allocations: dict[str, float]
    rationale: str
    created_by: str


class RebalanceProposalActionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    state: str


class RebalanceHistoryItem(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    state: str
    portfolio_id: str


class PortfolioCreatedResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str | None = None
    name: str | None = None
    is_paper_trading: bool | None = None
    base_currency: str | None = None


class PortfolioListItem(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    name: str
    is_paper_trading: bool
    base_currency: str


class PortfolioDetailResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    name: str
    positions: list[Any]


class PortfolioOptimizationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    operation_id: str
    status: str
    weights: dict[str, Any]
    trades: list[Any]
    slacks: dict[str, Any]
    diagnostics: dict[str, Any]
    input_sha256: str
