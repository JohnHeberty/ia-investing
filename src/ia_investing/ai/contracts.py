from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Citation(BaseModel):
    evidence_id: UUID
    claim: str = Field(min_length=1, max_length=2_000)


class AgentFinding(BaseModel):
    statement: str = Field(min_length=1, max_length=4_000)
    kind: Literal["fact", "inference"]
    confidence: Decimal = Field(ge=0, le=1)
    citations: list[Citation] = Field(default_factory=list)

    @model_validator(mode="after")
    def facts_must_be_cited(self) -> AgentFinding:
        if self.kind == "fact" and not self.citations:
            raise ValueError("facts require at least one citation")
        return self


class SpecialistOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    capability: Literal["filing", "news", "macro", "political", "critic"]
    summary: str = Field(min_length=1, max_length=8_000)
    findings: list[AgentFinding]
    contradictions: list[str] = Field(default_factory=list)
    uncertainty: list[str] = Field(default_factory=list)
    materiality: Literal["low", "medium", "high"]
    knowledge_cutoff: datetime


class ResearchPlanStep(BaseModel):
    capability: Literal["filing", "news", "macro", "political", "critic"]
    question: str = Field(min_length=1, max_length=2_000)
    required: bool = True


class ResearchPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    objective: str = Field(min_length=1, max_length=4_000)
    steps: list[ResearchPlanStep] = Field(min_length=1, max_length=10)
    data_as_of: datetime
    knowledge_cutoff: datetime

    @model_validator(mode="after")
    def cutoff_cannot_be_future_relative_to_data(self) -> ResearchPlan:
        if self.knowledge_cutoff > self.data_as_of:
            raise ValueError("knowledge_cutoff cannot exceed data_as_of")
        return self


class CoordinatorOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan: ResearchPlan
    specialist_outputs: list[SpecialistOutput]
    consolidated_findings: list[AgentFinding]
    unresolved_contradictions: list[str]
    confidence: Decimal = Field(ge=0, le=1)
    partial_failure_capabilities: list[str] = Field(default_factory=list)


class FundamentalAnalysisOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ticker: str = Field(min_length=1, max_length=24)
    issuer_id: str = Field(min_length=1, max_length=64)
    summary: str = Field(min_length=1, max_length=8_000)
    findings: list[AgentFinding]
    financial_health_score: Decimal = Field(ge=0, le=1)
    key_metrics: dict[str, str] = Field(default_factory=dict)
    risks: list[str] = Field(default_factory=list)
    catalysts: list[str] = Field(default_factory=list)
    knowledge_cutoff: datetime

    @model_validator(mode="after")
    def material_findings_need_citations(self) -> FundamentalAnalysisOutput:
        material = [f for f in self.findings if f.confidence >= Decimal("0.5")]
        for finding in material:
            if finding.kind == "fact" and not finding.citations:
                raise ValueError(f"Material fact finding requires citations: {finding.statement[:80]}")
        return self


class RiskAnalysisOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ticker: str = Field(min_length=1, max_length=24)
    issuer_id: str = Field(min_length=1, max_length=64)
    summary: str = Field(min_length=1, max_length=8_000)
    findings: list[AgentFinding]
    risk_rating: Literal["low", "medium", "high", "critical"]
    risk_factors: list[str] = Field(min_length=1)
    max_drawdown_estimate: Decimal = Field(ge=0, le=1)
    volatility_regime: Literal["low", "normal", "high", "extreme"]
    knowledge_cutoff: datetime

    @model_validator(mode="after")
    def critical_risk_requires_evidence(self) -> RiskAnalysisOutput:
        if self.risk_rating == "critical" and len(self.findings) < 3:
            raise ValueError("Critical risk rating requires at least 3 supporting findings")
        return self


class CommitteeDecisionOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ticker: str = Field(min_length=1, max_length=24)
    decision: Literal["approve", "reject", "defer", "conditional"]
    confidence: Decimal = Field(ge=0, le=1)
    rationale: str = Field(min_length=1, max_length=10_000)
    conditions: list[str] = Field(default_factory=list)
    dissenting_views: list[str] = Field(default_factory=list)
    risk_acknowledgment: str = Field(min_length=1, max_length=5_000)
    knowledge_cutoff: datetime

    @model_validator(mode="after")
    def conditional_needs_conditions(self) -> CommitteeDecisionOutput:
        if self.decision == "conditional" and not self.conditions:
            raise ValueError("Conditional decision must specify conditions")
        return self


class CommandReceipt(BaseModel):
    command_id: UUID
    command: str
    status: Literal["awaiting_approval", "accepted", "rejected"]
    scope: str
    impact_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


class ProviderUsage(BaseModel):
    prompt_tokens: int = Field(ge=0)
    completion_tokens: int = Field(ge=0)
    cost_usd: Decimal = Field(ge=0)
    duration_ms: int = Field(ge=0)


class ProviderResponse(BaseModel):
    provider_run_id: str
    output: dict[str, object]
    usage: ProviderUsage
