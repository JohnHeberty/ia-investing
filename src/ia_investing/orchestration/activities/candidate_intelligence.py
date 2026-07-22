from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

from temporalio import activity


@dataclass(frozen=True, slots=True)
class CandidateWorkflowInput:
    candidate_id: UUID
    analysis_run_id: UUID
    organization_id: UUID
    data_as_of: datetime
    allow_incomplete: bool = False
    correlation_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class CandidateCheckpoint:
    candidate_id: UUID
    stage: str
    blocked: bool
    decision: str
    reason: str
    blocker_codes: tuple[str, ...] = ()
    payload: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class CandidateWorkflowResult:
    candidate_id: UUID
    analysis_run_id: UUID
    status: str
    decision: str
    reason: str
    blocker_codes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SourceDiscoveryCheckpoint:
    command: CandidateWorkflowInput
    output: dict[str, Any]


@dataclass(frozen=True, slots=True)
class CandidateSourceValidationInput:
    candidate_id: UUID
    source_id: UUID
    organization_id: UUID
    correlation_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class CandidateSourceValidationResult:
    candidate_id: UUID
    source_id: UUID
    status: str
    official: bool
    reason: str
    resolved_gap_codes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ExplorationWorkflowInput:
    exploration_run_id: UUID
    organization_id: UUID
    data_as_of: datetime
    correlation_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class ScheduledExplorationInput:
    organization_id: UUID
    strategy_codes: tuple[str, ...]
    minimum_liquidity: str
    maximum_suggestions: int
    requested_by: str = "schedule:autonomous-equity-explorer"
    correlation_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class ExplorationShortlist:
    command: ExplorationWorkflowInput
    securities: tuple[dict[str, Any], ...]
    universe_size: int
    eligible_size: int


@dataclass(frozen=True, slots=True)
class ExplorationFindings:
    shortlist: ExplorationShortlist
    suggestions: tuple[dict[str, Any], ...]
    limitations: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ExplorationWorkflowResult:
    exploration_run_id: UUID
    status: str
    universe_size: int
    eligible_size: int
    suggestion_count: int


class CandidateActivityRuntime(Protocol):
    async def resolve_candidate_identity(self, command: CandidateWorkflowInput) -> CandidateCheckpoint: ...

    async def discover_candidate_sources(self, command: CandidateWorkflowInput) -> SourceDiscoveryCheckpoint: ...

    async def persist_candidate_sources_and_gaps(self, checkpoint: SourceDiscoveryCheckpoint) -> None: ...

    async def validate_supplied_candidate_source(
        self,
        command: CandidateSourceValidationInput,
    ) -> CandidateSourceValidationResult: ...

    async def evaluate_candidate_readiness(self, command: CandidateWorkflowInput) -> CandidateCheckpoint: ...

    async def validate_candidate_sources(self, command: CandidateWorkflowInput) -> CandidateCheckpoint: ...

    async def collect_candidate_documents(self, command: CandidateWorkflowInput) -> CandidateCheckpoint: ...

    async def validate_candidate_financial_data(self, command: CandidateWorkflowInput) -> CandidateCheckpoint: ...

    async def run_candidate_fundamental_analysis(self, command: CandidateWorkflowInput) -> CandidateCheckpoint: ...

    async def run_candidate_risk_analysis(self, command: CandidateWorkflowInput) -> CandidateCheckpoint: ...

    async def create_committee_pack(self, command: CandidateWorkflowInput) -> CandidateCheckpoint: ...

    async def complete_candidate_analysis_run(
        self,
        command: CandidateWorkflowInput,
        checkpoint: CandidateCheckpoint,
    ) -> CandidateWorkflowResult: ...

    async def screen_equity_universe(self, command: ExplorationWorkflowInput) -> ExplorationShortlist: ...

    async def run_equity_explorer_agent(self, shortlist: ExplorationShortlist) -> ExplorationFindings: ...

    async def persist_exploration_suggestions(
        self,
        findings: ExplorationFindings,
    ) -> ExplorationWorkflowResult: ...


@dataclass(slots=True)
class CallbackCandidateActivityRuntime:
    """Composable runtime adapter for the existing application services.

    The worker startup builds this object with callbacks that open database sessions,
    invoke the existing source registry, agent runtime, research, risk and committee
    services, and commit through the transactional outbox.
    """

    resolve_identity: Callable[[CandidateWorkflowInput], Awaitable[CandidateCheckpoint]]
    discover_sources: Callable[[CandidateWorkflowInput], Awaitable[SourceDiscoveryCheckpoint]]
    persist_sources: Callable[[SourceDiscoveryCheckpoint], Awaitable[None]]
    validate_supplied_source: Callable[
        [CandidateSourceValidationInput],
        Awaitable[CandidateSourceValidationResult],
    ]
    evaluate_readiness: Callable[[CandidateWorkflowInput], Awaitable[CandidateCheckpoint]]
    validate_sources: Callable[[CandidateWorkflowInput], Awaitable[CandidateCheckpoint]]
    collect_documents: Callable[[CandidateWorkflowInput], Awaitable[CandidateCheckpoint]]
    validate_financials: Callable[[CandidateWorkflowInput], Awaitable[CandidateCheckpoint]]
    analyze_fundamentals: Callable[[CandidateWorkflowInput], Awaitable[CandidateCheckpoint]]
    analyze_risk: Callable[[CandidateWorkflowInput], Awaitable[CandidateCheckpoint]]
    build_committee_pack: Callable[[CandidateWorkflowInput], Awaitable[CandidateCheckpoint]]
    complete_run: Callable[
        [CandidateWorkflowInput, CandidateCheckpoint],
        Awaitable[CandidateWorkflowResult],
    ]
    screen_universe: Callable[[ExplorationWorkflowInput], Awaitable[ExplorationShortlist]]
    explore_shortlist: Callable[[ExplorationShortlist], Awaitable[ExplorationFindings]]
    persist_suggestions: Callable[[ExplorationFindings], Awaitable[ExplorationWorkflowResult]]

    async def resolve_candidate_identity(self, command: CandidateWorkflowInput) -> CandidateCheckpoint:
        return await self.resolve_identity(command)

    async def discover_candidate_sources(self, command: CandidateWorkflowInput) -> SourceDiscoveryCheckpoint:
        return await self.discover_sources(command)

    async def persist_candidate_sources_and_gaps(self, checkpoint: SourceDiscoveryCheckpoint) -> None:
        await self.persist_sources(checkpoint)

    async def validate_supplied_candidate_source(
        self,
        command: CandidateSourceValidationInput,
    ) -> CandidateSourceValidationResult:
        return await self.validate_supplied_source(command)

    async def evaluate_candidate_readiness(self, command: CandidateWorkflowInput) -> CandidateCheckpoint:
        return await self.evaluate_readiness(command)

    async def validate_candidate_sources(self, command: CandidateWorkflowInput) -> CandidateCheckpoint:
        return await self.validate_sources(command)

    async def collect_candidate_documents(self, command: CandidateWorkflowInput) -> CandidateCheckpoint:
        return await self.collect_documents(command)

    async def validate_candidate_financial_data(self, command: CandidateWorkflowInput) -> CandidateCheckpoint:
        return await self.validate_financials(command)

    async def run_candidate_fundamental_analysis(self, command: CandidateWorkflowInput) -> CandidateCheckpoint:
        return await self.analyze_fundamentals(command)

    async def run_candidate_risk_analysis(self, command: CandidateWorkflowInput) -> CandidateCheckpoint:
        return await self.analyze_risk(command)

    async def create_committee_pack(self, command: CandidateWorkflowInput) -> CandidateCheckpoint:
        return await self.build_committee_pack(command)

    async def complete_candidate_analysis_run(
        self,
        command: CandidateWorkflowInput,
        checkpoint: CandidateCheckpoint,
    ) -> CandidateWorkflowResult:
        return await self.complete_run(command, checkpoint)

    async def screen_equity_universe(self, command: ExplorationWorkflowInput) -> ExplorationShortlist:
        return await self.screen_universe(command)

    async def run_equity_explorer_agent(self, shortlist: ExplorationShortlist) -> ExplorationFindings:
        return await self.explore_shortlist(shortlist)

    async def persist_exploration_suggestions(
        self,
        findings: ExplorationFindings,
    ) -> ExplorationWorkflowResult:
        return await self.persist_suggestions(findings)


_RUNTIME: CandidateActivityRuntime | None = None


def configure_candidate_activity_runtime(runtime: CandidateActivityRuntime) -> None:
    global _RUNTIME
    if _RUNTIME is not None:
        raise RuntimeError("candidate activity runtime is already configured")
    _RUNTIME = runtime


def reset_candidate_activity_runtime_for_tests() -> None:
    global _RUNTIME
    _RUNTIME = None


def candidate_activity_runtime_configured() -> bool:
    """Return whether the worker has a concrete candidate runtime installed."""

    return _RUNTIME is not None


def _runtime() -> CandidateActivityRuntime:
    if _RUNTIME is None:
        raise RuntimeError(
            "candidate activity runtime is not configured; wire CallbackCandidateActivityRuntime "
            "during worker startup"
        )
    return _RUNTIME


@activity.defn
async def resolve_candidate_identity(command: CandidateWorkflowInput) -> CandidateCheckpoint:
    return await _runtime().resolve_candidate_identity(command)


@activity.defn
async def discover_candidate_sources(command: CandidateWorkflowInput) -> SourceDiscoveryCheckpoint:
    return await _runtime().discover_candidate_sources(command)


@activity.defn
async def persist_candidate_sources_and_gaps(checkpoint: SourceDiscoveryCheckpoint) -> None:
    await _runtime().persist_candidate_sources_and_gaps(checkpoint)


@activity.defn
async def validate_supplied_candidate_source(
    command: CandidateSourceValidationInput,
) -> CandidateSourceValidationResult:
    return await _runtime().validate_supplied_candidate_source(command)


@activity.defn
async def evaluate_candidate_readiness(command: CandidateWorkflowInput) -> CandidateCheckpoint:
    return await _runtime().evaluate_candidate_readiness(command)


@activity.defn
async def validate_candidate_sources(command: CandidateWorkflowInput) -> CandidateCheckpoint:
    return await _runtime().validate_candidate_sources(command)


@activity.defn
async def collect_candidate_documents(command: CandidateWorkflowInput) -> CandidateCheckpoint:
    return await _runtime().collect_candidate_documents(command)


@activity.defn
async def validate_candidate_financial_data(command: CandidateWorkflowInput) -> CandidateCheckpoint:
    return await _runtime().validate_candidate_financial_data(command)


@activity.defn
async def run_candidate_fundamental_analysis(command: CandidateWorkflowInput) -> CandidateCheckpoint:
    return await _runtime().run_candidate_fundamental_analysis(command)


@activity.defn
async def run_candidate_risk_analysis(command: CandidateWorkflowInput) -> CandidateCheckpoint:
    return await _runtime().run_candidate_risk_analysis(command)


@activity.defn
async def create_committee_pack(command: CandidateWorkflowInput) -> CandidateCheckpoint:
    return await _runtime().create_committee_pack(command)


@activity.defn
async def complete_candidate_analysis_run(
    args: tuple[CandidateWorkflowInput, CandidateCheckpoint],
) -> CandidateWorkflowResult:
    command, checkpoint = args
    return await _runtime().complete_candidate_analysis_run(command, checkpoint)


@activity.defn
async def screen_equity_universe(command: ExplorationWorkflowInput) -> ExplorationShortlist:
    return await _runtime().screen_equity_universe(command)


@activity.defn
async def run_equity_explorer_agent(shortlist: ExplorationShortlist) -> ExplorationFindings:
    return await _runtime().run_equity_explorer_agent(shortlist)


@activity.defn
async def persist_exploration_suggestions(findings: ExplorationFindings) -> ExplorationWorkflowResult:
    return await _runtime().persist_exploration_suggestions(findings)


CANDIDATE_INTELLIGENCE_ACTIVITIES = (
    resolve_candidate_identity,
    discover_candidate_sources,
    persist_candidate_sources_and_gaps,
    validate_supplied_candidate_source,
    evaluate_candidate_readiness,
    validate_candidate_sources,
    collect_candidate_documents,
    validate_candidate_financial_data,
    run_candidate_fundamental_analysis,
    run_candidate_risk_analysis,
    create_committee_pack,
    complete_candidate_analysis_run,
    screen_equity_universe,
    run_equity_explorer_agent,
    persist_exploration_suggestions,
)
