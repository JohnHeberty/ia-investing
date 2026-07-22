from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ApiModel(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")


class PortfolioRankItem(ApiModel):
    portfolio_id: UUID
    name: str
    cohort_key: str
    category: str
    benchmark: str
    currency: str
    risk_class: str
    environment: Literal["paper", "live"]
    stage: str
    score: Decimal | None
    rank: int | None
    eligible: bool
    exclusion_reasons: list[str] = Field(default_factory=list)
    nav: Decimal | None
    nav_as_of: datetime | None
    reconciled: bool
    volatility: Decimal | None
    drawdown: Decimal | None
    open_hard_breaches: int
    open_soft_breaches: int
    data_confidence: Decimal
    thesis_coverage: Decimal


class ResearchFunnel(ApiModel):
    draft: int = 0
    triage: int = 0
    in_research: int = 0
    review: int = 0
    approved: int = 0
    rejected: int = 0
    closed: int = 0


class AgentOperationsSummary(ApiModel):
    running: int = 0
    succeeded_24h: int = 0
    failed_24h: int = 0
    schema_pass_rate: Decimal | None = None
    evidence_coverage: Decimal | None = None
    cost_usd_24h: Decimal = Decimal("0")
    p95_duration_ms: int | None = None


class SourceHealthItem(ApiModel):
    source_id: UUID
    code: str
    name: str
    status: Literal["healthy", "stale", "failed", "never_succeeded"]
    last_success_at: datetime | None
    last_failure_at: datetime | None
    expected_frequency_minutes: int
    freshness_grace_minutes: int
    age_minutes: int | None
    error_code: str | None


class RiskSummary(ApiModel):
    open_hard_breaches: int = 0
    open_soft_breaches: int = 0
    portfolios_with_breaches: int = 0
    stale_risk_snapshots: int = 0


class MissionControlResponse(ApiModel):
    generated_at: datetime
    data_as_of: datetime | None
    top_portfolios: list[PortfolioRankItem]
    excluded_portfolios: list[PortfolioRankItem]
    research_funnel: ResearchFunnel
    agent_operations: AgentOperationsSummary
    source_health: list[SourceHealthItem]
    risk: RiskSummary
    pending_approvals: int
    critical_alerts: int
