from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

try:
    from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator
except ImportError as exc:  # pragma: no cover - repository dependency guard
    raise RuntimeError("pydantic is required by candidate intelligence contracts") from exc

from .enums import (
    AnalysisTrigger,
    CandidateOrigin,
    CandidateStatus,
    RequirementLevel,
    SourceKind,
    SourceStatus,
    VerificationMethod,
)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)


class CandidateCreateRequest(StrictModel):
    ticker: str = Field(min_length=1, max_length=24)
    exchange: str = Field(default="B3", min_length=1, max_length=20)
    legal_name: str | None = Field(default=None, max_length=300)
    trading_name: str | None = Field(default=None, max_length=300)
    cnpj: str | None = Field(default=None, max_length=32)
    cvm_code: str | None = Field(default=None, max_length=32)
    rationale: str | None = Field(default=None, max_length=4000)

    @field_validator("ticker")
    @classmethod
    def normalize_ticker(cls, value: str) -> str:
        return "".join(value.upper().split())


class CandidateSourceCreateRequest(StrictModel):
    kind: SourceKind
    url: HttpUrl
    notes: str | None = Field(default=None, max_length=4000)


class CandidateGapResolveRequest(StrictModel):
    notes: str = Field(min_length=3, max_length=4000)
    source: CandidateSourceCreateRequest | None = None


class CandidateReanalysisRequest(StrictModel):
    trigger: AnalysisTrigger = AnalysisTrigger.MANUAL_RETRY
    data_as_of: datetime
    allow_incomplete: bool = False
    notes: str | None = Field(default=None, max_length=4000)


class ExplorationCreateRequest(StrictModel):
    strategy_codes: tuple[str, ...] = Field(min_length=1, max_length=20)
    data_as_of: datetime
    minimum_liquidity: Decimal = Field(ge=0)
    maximum_suggestions: int = Field(default=20, ge=1, le=100)
    excluded_instrument_ids: tuple[UUID, ...] = ()


class SourceDiscoveryFinding(StrictModel):
    kind: SourceKind
    url: HttpUrl
    status: SourceStatus
    verification_method: VerificationMethod
    confidence: Decimal = Field(ge=0, le=1)
    official: bool
    title: str | None = Field(default=None, max_length=500)
    evidence: dict[str, Any] = Field(default_factory=dict)
    warnings: tuple[str, ...] = ()


class DiscoveryGapFinding(StrictModel):
    code: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=500)
    description: str = Field(min_length=1, max_length=4000)
    source_kind: SourceKind | None = None
    level: RequirementLevel
    requested_user_action: str = Field(min_length=1, max_length=1000)


class CompanySourceDiscoveryOutput(StrictModel):
    identity_confidence: Decimal = Field(ge=0, le=1)
    resolved_legal_name: str | None = Field(default=None, max_length=300)
    resolved_cnpj: str | None = Field(default=None, max_length=32)
    resolved_cvm_code: str | None = Field(default=None, max_length=32)
    sources: tuple[SourceDiscoveryFinding, ...]
    gaps: tuple[DiscoveryGapFinding, ...]
    contradictions: tuple[str, ...] = ()
    summary: str = Field(min_length=1, max_length=5000)


class ExplorerCandidateFinding(StrictModel):
    ticker: str = Field(min_length=1, max_length=24)
    exchange: str = Field(default="B3", min_length=1, max_length=20)
    legal_name: str | None = Field(default=None, max_length=300)
    cnpj: str | None = Field(default=None, max_length=32)
    cvm_code: str | None = Field(default=None, max_length=32)
    quantitative_score: Decimal = Field(ge=0, le=1)
    data_coverage_score: Decimal = Field(ge=0, le=1)
    source_discovery_score: Decimal = Field(ge=0, le=1)
    rationale: str = Field(min_length=1, max_length=5000)
    signals: tuple[str, ...] = ()
    risks: tuple[str, ...] = ()
    sources: tuple[SourceDiscoveryFinding, ...] = ()


class AutonomousExplorerOutput(StrictModel):
    universe_size: int = Field(ge=0)
    eligible_size: int = Field(ge=0)
    candidates: tuple[ExplorerCandidateFinding, ...]
    methodology_summary: str = Field(min_length=1, max_length=5000)
    limitations: tuple[str, ...] = ()


class CandidateSummaryResponse(StrictModel):
    id: UUID
    organization_id: UUID
    origin: CandidateOrigin
    ticker: str
    exchange: str
    legal_name: str | None
    status: CandidateStatus
    readiness_score: Decimal
    blocker_codes: tuple[str, ...]
    open_gap_count: int
    latest_analysis_status: str | None
    final_decision: str | None
    created_at: datetime
    updated_at: datetime
    lock_version: int
