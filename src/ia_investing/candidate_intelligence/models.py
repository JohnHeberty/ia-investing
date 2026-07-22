from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from urllib.parse import urlsplit, urlunsplit
from uuid import UUID, uuid4

from .enums import (
    AnalysisRunStatus,
    AnalysisTrigger,
    CandidateDecision,
    CandidateOrigin,
    CandidateStatus,
    ExplorationRunStatus,
    GapStatus,
    RequirementLevel,
    SourceKind,
    SourceStatus,
    SuggestionStatus,
    VerificationMethod,
)


def utcnow() -> datetime:
    return datetime.now(UTC)


def normalize_ticker(value: str) -> str:
    ticker = "".join(value.strip().upper().split())
    if not ticker or len(ticker) > 24:
        raise ValueError("ticker must contain between 1 and 24 characters")
    allowed = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.-")
    if any(char not in allowed for char in ticker):
        raise ValueError("ticker contains unsupported characters")
    return ticker


def normalize_url(value: str) -> str:
    raw = value.strip()
    parsed = urlsplit(raw)
    if parsed.scheme.lower() not in {"http", "https"}:
        raise ValueError("source URL must use http or https")
    if not parsed.hostname:
        raise ValueError("source URL must contain a hostname")
    hostname = parsed.hostname.lower().rstrip(".")
    if hostname in {"localhost", "localhost.localdomain"}:
        raise ValueError("local source URLs are not allowed")
    if parsed.username or parsed.password:
        raise ValueError("credentials in source URLs are not allowed")
    netloc = hostname
    if parsed.port:
        netloc = f"{hostname}:{parsed.port}"
    normalized_path = parsed.path or "/"
    return urlunsplit((parsed.scheme.lower(), netloc, normalized_path, parsed.query, ""))


@dataclass(frozen=True, slots=True)
class CandidateIdentity:
    ticker: str
    exchange: str = "B3"
    legal_name: str | None = None
    trading_name: str | None = None
    cnpj: str | None = None
    cvm_code: str | None = None
    issuer_id: UUID | None = None
    instrument_id: UUID | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "ticker", normalize_ticker(self.ticker))
        if not self.exchange.strip():
            raise ValueError("exchange is required")


@dataclass(frozen=True, slots=True)
class CandidateSource:
    id: UUID
    candidate_id: UUID
    kind: SourceKind
    url: str
    status: SourceStatus
    verification_method: VerificationMethod
    confidence: Decimal
    official: bool
    discovered_by: str
    created_at: datetime
    verified_at: datetime | None = None
    last_checked_at: datetime | None = None
    notes: str | None = None
    evidence: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "url", normalize_url(self.url))
        if not Decimal("0") <= self.confidence <= Decimal("1"):
            raise ValueError("source confidence must be between 0 and 1")
        if self.status is SourceStatus.VERIFIED and self.verified_at is None:
            raise ValueError("verified source must have verified_at")
        if self.verification_method is VerificationMethod.AGENT_INFERENCE and self.official:
            raise ValueError("agent inference alone cannot mark a source official")

    @classmethod
    def user_supplied(
        cls,
        *,
        candidate_id: UUID,
        kind: SourceKind,
        url: str,
        actor_id: str,
        notes: str | None = None,
    ) -> CandidateSource:
        now = utcnow()
        return cls(
            id=uuid4(),
            candidate_id=candidate_id,
            kind=kind,
            url=url,
            status=SourceStatus.DISCOVERED,
            verification_method=VerificationMethod.USER_CONFIRMED,
            confidence=Decimal("0.70"),
            official=False,
            discovered_by=actor_id,
            created_at=now,
            verified_at=None,
            last_checked_at=None,
            notes=notes,
        )


@dataclass(frozen=True, slots=True)
class CandidateGap:
    id: UUID
    candidate_id: UUID
    code: str
    title: str
    description: str
    source_kind: SourceKind | None
    level: RequirementLevel
    status: GapStatus
    requested_user_action: str
    created_at: datetime
    resolved_at: datetime | None = None
    resolved_by: str | None = None
    resolution_notes: str | None = None

    @property
    def blocks_progress(self) -> bool:
        return self.status is GapStatus.OPEN and self.level is RequirementLevel.BLOCKING

    def resolve(self, actor_id: str, notes: str) -> CandidateGap:
        if self.status is not GapStatus.OPEN:
            raise ValueError("only open gaps can be resolved")
        if not notes.strip():
            raise ValueError("resolution notes are required")
        return replace(
            self,
            status=GapStatus.RESOLVED,
            resolved_at=utcnow(),
            resolved_by=actor_id,
            resolution_notes=notes.strip(),
        )


@dataclass(frozen=True, slots=True)
class ReadinessDimension:
    code: str
    label: str
    satisfied: bool
    score: Decimal
    reason: str
    blocking: bool


@dataclass(frozen=True, slots=True)
class CandidateReadiness:
    score: Decimal
    dimensions: tuple[ReadinessDimension, ...]
    blocker_codes: tuple[str, ...]
    missing_source_kinds: tuple[SourceKind, ...]

    @property
    def ready_for_document_collection(self) -> bool:
        return not self.blocker_codes

    @property
    def ready_for_committee(self) -> bool:
        return not self.blocker_codes and self.score >= Decimal("0.90")


@dataclass(frozen=True, slots=True)
class AnalysisRun:
    id: UUID
    candidate_id: UUID
    run_number: int
    trigger: AnalysisTrigger
    status: AnalysisRunStatus
    requested_by: str
    requested_at: datetime
    data_as_of: datetime
    workflow_id: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    decision: CandidateDecision | None = None
    summary: str | None = None
    blocker_codes: tuple[str, ...] = ()
    agent_run_ids: tuple[UUID, ...] = ()
    research_case_id: UUID | None = None
    thesis_version_id: UUID | None = None
    committee_decision_id: UUID | None = None
    error_code: str | None = None
    error_detail: str | None = None

    def start(self, workflow_id: str) -> AnalysisRun:
        if self.status is not AnalysisRunStatus.QUEUED:
            raise ValueError("only queued runs can start")
        return replace(
            self,
            status=AnalysisRunStatus.RUNNING,
            workflow_id=workflow_id,
            started_at=utcnow(),
        )


@dataclass(frozen=True, slots=True)
class InvestmentCandidate:
    id: UUID
    organization_id: UUID
    origin: CandidateOrigin
    identity: CandidateIdentity
    status: CandidateStatus
    created_by: str
    created_at: datetime
    updated_at: datetime
    lock_version: int
    rationale: str | None = None
    exploration_suggestion_id: UUID | None = None
    sources: tuple[CandidateSource, ...] = ()
    gaps: tuple[CandidateGap, ...] = ()
    analysis_runs: tuple[AnalysisRun, ...] = ()
    final_decision: CandidateDecision | None = None
    final_decision_reason: str | None = None
    approved_portfolio_eligible: bool = False

    @classmethod
    def create_manual(
        cls,
        *,
        organization_id: UUID,
        identity: CandidateIdentity,
        actor_id: str,
        rationale: str | None = None,
    ) -> InvestmentCandidate:
        now = utcnow()
        return cls(
            id=uuid4(),
            organization_id=organization_id,
            origin=CandidateOrigin.MANUAL,
            identity=identity,
            status=CandidateStatus.IDENTITY_RESOLUTION,
            created_by=actor_id,
            created_at=now,
            updated_at=now,
            lock_version=1,
            rationale=rationale,
        )

    @classmethod
    def create_from_explorer(
        cls,
        *,
        organization_id: UUID,
        identity: CandidateIdentity,
        actor_id: str,
        suggestion_id: UUID,
        rationale: str,
    ) -> InvestmentCandidate:
        now = utcnow()
        return cls(
            id=uuid4(),
            organization_id=organization_id,
            origin=CandidateOrigin.EXPLORER,
            identity=identity,
            status=CandidateStatus.SUGGESTED,
            created_by=actor_id,
            created_at=now,
            updated_at=now,
            lock_version=1,
            rationale=rationale,
            exploration_suggestion_id=suggestion_id,
        )

    @property
    def open_gaps(self) -> tuple[CandidateGap, ...]:
        return tuple(gap for gap in self.gaps if gap.status is GapStatus.OPEN)

    @property
    def blocking_gaps(self) -> tuple[CandidateGap, ...]:
        return tuple(gap for gap in self.gaps if gap.blocks_progress)

    def with_source(self, source: CandidateSource) -> InvestmentCandidate:
        if source.candidate_id != self.id:
            raise ValueError("source belongs to another candidate")
        sources = tuple(item for item in self.sources if item.kind != source.kind or item.url != source.url)
        return replace(
            self,
            sources=(*sources, source),
            updated_at=utcnow(),
            lock_version=self.lock_version + 1,
        )

    def with_gaps(self, gaps: tuple[CandidateGap, ...]) -> InvestmentCandidate:
        if any(gap.candidate_id != self.id for gap in gaps):
            raise ValueError("gap belongs to another candidate")
        return replace(
            self,
            gaps=gaps,
            updated_at=utcnow(),
            lock_version=self.lock_version + 1,
        )

    def with_analysis_run(self, run: AnalysisRun) -> InvestmentCandidate:
        if run.candidate_id != self.id:
            raise ValueError("analysis run belongs to another candidate")
        return replace(
            self,
            analysis_runs=(*self.analysis_runs, run),
            updated_at=utcnow(),
            lock_version=self.lock_version + 1,
        )


@dataclass(frozen=True, slots=True)
class ExplorationSuggestion:
    id: UUID
    exploration_run_id: UUID
    organization_id: UUID
    identity: CandidateIdentity
    status: SuggestionStatus
    quantitative_score: Decimal
    data_coverage_score: Decimal
    source_discovery_score: Decimal
    rationale: str
    signals: tuple[str, ...]
    risks: tuple[str, ...]
    discovered_sources: tuple[CandidateSource, ...]
    created_at: datetime
    expires_at: datetime | None = None
    promoted_candidate_id: UUID | None = None

    def __post_init__(self) -> None:
        for value in (
            self.quantitative_score,
            self.data_coverage_score,
            self.source_discovery_score,
        ):
            if not Decimal("0") <= value <= Decimal("1"):
                raise ValueError("suggestion scores must be between 0 and 1")


@dataclass(frozen=True, slots=True)
class ExplorationRun:
    id: UUID
    organization_id: UUID
    status: ExplorationRunStatus
    strategy_codes: tuple[str, ...]
    requested_by: str
    created_at: datetime
    data_as_of: datetime
    minimum_liquidity: Decimal
    maximum_suggestions: int
    excluded_instrument_ids: tuple[UUID, ...] = ()
    started_at: datetime | None = None
    completed_at: datetime | None = None
    workflow_id: str | None = None
    universe_size: int = 0
    eligible_size: int = 0
    suggestions: tuple[ExplorationSuggestion, ...] = ()
    error_detail: str | None = None

    def __post_init__(self) -> None:
        if self.maximum_suggestions < 1 or self.maximum_suggestions > 100:
            raise ValueError("maximum_suggestions must be between 1 and 100")
        if self.minimum_liquidity < 0:
            raise ValueError("minimum_liquidity cannot be negative")
