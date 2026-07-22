from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from decimal import Decimal
from typing import Protocol
from uuid import UUID, uuid4

from .contracts import AutonomousExplorerOutput
from .enums import ExplorationRunStatus, SourceStatus, SuggestionStatus, VerificationMethod
from .models import (
    CandidateIdentity,
    CandidateSource,
    ExplorationRun,
    ExplorationSuggestion,
    utcnow,
)
from .repositories import CandidateRepository, ExplorationRepository


@dataclass(frozen=True, slots=True)
class UniverseSecurity:
    instrument_id: UUID
    issuer_id: UUID
    ticker: str
    exchange: str
    legal_name: str
    cnpj: str | None
    cvm_code: str | None
    average_daily_liquidity: Decimal
    active: bool
    restricted: bool
    data_coverage_score: Decimal


@dataclass(frozen=True, slots=True)
class ScreenedSecurity:
    security: UniverseSecurity
    quantitative_score: Decimal
    signals: tuple[str, ...]
    risk_flags: tuple[str, ...]


class UniverseProvider(Protocol):
    async def snapshot(self, *, organization_id: UUID, data_as_of: datetime) -> tuple[UniverseSecurity, ...]: ...


class DeterministicScreener(Protocol):
    async def screen(
        self,
        universe: tuple[UniverseSecurity, ...],
        *,
        strategy_codes: tuple[str, ...],
        data_as_of: datetime,
    ) -> tuple[ScreenedSecurity, ...]: ...


class AutonomousExplorerAgent(Protocol):
    async def investigate(
        self,
        securities: tuple[ScreenedSecurity, ...],
        *,
        data_as_of: datetime,
        maximum_suggestions: int,
    ) -> AutonomousExplorerOutput: ...


@dataclass(frozen=True, slots=True)
class ExplorerExecutionResult:
    run_id: UUID
    status: ExplorationRunStatus
    universe_size: int
    eligible_size: int
    suggestion_count: int


class AutonomousExplorationOrchestrator:
    """Discovers ideas but never inserts them into a portfolio.

    The deterministic universe and screener run before the LLM. The LLM may explain,
    classify and discover sources only for the bounded shortlist.
    """

    def __init__(
        self,
        *,
        exploration_repository: ExplorationRepository,
        candidate_repository: CandidateRepository,
        universe_provider: UniverseProvider,
        screener: DeterministicScreener,
        explorer_agent: AutonomousExplorerAgent,
    ) -> None:
        self.exploration_repository = exploration_repository
        self.candidate_repository = candidate_repository
        self.universe_provider = universe_provider
        self.screener = screener
        self.explorer_agent = explorer_agent

    async def run(self, run_id: UUID) -> ExplorerExecutionResult:
        run = await self.exploration_repository.get_run(run_id)
        if run.status is not ExplorationRunStatus.QUEUED:
            raise ValueError("only queued exploration runs can start")
        run = replace(run, status=ExplorationRunStatus.RUNNING, started_at=utcnow())
        await self.exploration_repository.save_run(run)

        universe = await self.universe_provider.snapshot(
            organization_id=run.organization_id,
            data_as_of=run.data_as_of,
        )
        excluded = set(run.excluded_instrument_ids)
        eligible: list[UniverseSecurity] = []
        for security in universe:
            if (
                not security.active
                or security.restricted
                or security.instrument_id in excluded
                or security.average_daily_liquidity < run.minimum_liquidity
                or security.data_coverage_score < Decimal("0.60")
            ):
                continue
            existing = await self.candidate_repository.find_active_by_ticker(
                run.organization_id,
                security.ticker,
                security.exchange,
            )
            if existing is None:
                eligible.append(security)

        screened = await self.screener.screen(
            tuple(eligible),
            strategy_codes=run.strategy_codes,
            data_as_of=run.data_as_of,
        )
        bounded = tuple(
            sorted(screened, key=lambda item: item.quantitative_score, reverse=True)[
                : max(run.maximum_suggestions * 5, run.maximum_suggestions)
            ]
        )
        agent_output = await self.explorer_agent.investigate(
            bounded,
            data_as_of=run.data_as_of,
            maximum_suggestions=run.maximum_suggestions,
        )

        screened_by_ticker = {
            (item.security.exchange.upper(), item.security.ticker.upper()): item
            for item in bounded
        }
        suggestions: list[ExplorationSuggestion] = []
        for finding in agent_output.candidates[: run.maximum_suggestions]:
            key = (finding.exchange.upper(), finding.ticker.upper())
            screened_security = screened_by_ticker.get(key)
            if screened_security is None:
                # The agent cannot introduce an instrument outside the deterministic shortlist.
                continue
            duplicate = await self.candidate_repository.find_active_by_ticker(
                run.organization_id,
                finding.ticker,
                finding.exchange,
            )
            if duplicate is not None:
                continue
            suggestion_id = uuid4()
            sources = tuple(
                CandidateSource(
                    id=uuid4(),
                    candidate_id=suggestion_id,  # reassigned when promoted
                    kind=source.kind,
                    url=str(source.url),
                    status=source.status,
                    verification_method=source.verification_method,
                    confidence=source.confidence,
                    official=(
                        source.official
                        and source.verification_method is not VerificationMethod.AGENT_INFERENCE
                    ),
                    discovered_by="agent:autonomous-equity-explorer",
                    created_at=utcnow(),
                    verified_at=(utcnow() if source.status is SourceStatus.VERIFIED else None),
                    last_checked_at=utcnow(),
                    evidence=source.evidence,
                    notes="; ".join(source.warnings) or None,
                )
                for source in finding.sources
            )
            suggestions.append(
                ExplorationSuggestion(
                    id=suggestion_id,
                    exploration_run_id=run.id,
                    organization_id=run.organization_id,
                    identity=CandidateIdentity(
                        ticker=finding.ticker,
                        exchange=finding.exchange,
                        legal_name=finding.legal_name or screened_security.security.legal_name,
                        cnpj=finding.cnpj or screened_security.security.cnpj,
                        cvm_code=finding.cvm_code or screened_security.security.cvm_code,
                        issuer_id=screened_security.security.issuer_id,
                        instrument_id=screened_security.security.instrument_id,
                    ),
                    status=SuggestionStatus.NEW,
                    quantitative_score=screened_security.quantitative_score,
                    data_coverage_score=finding.data_coverage_score,
                    source_discovery_score=finding.source_discovery_score,
                    rationale=finding.rationale,
                    signals=tuple(dict.fromkeys((*screened_security.signals, *finding.signals))),
                    risks=tuple(dict.fromkeys((*screened_security.risk_flags, *finding.risks))),
                    discovered_sources=sources,
                    created_at=utcnow(),
                )
            )

        status = (
            ExplorationRunStatus.SUCCEEDED
            if len(suggestions) == len(agent_output.candidates)
            else ExplorationRunStatus.PARTIAL
        )
        run = replace(
            run,
            status=status,
            completed_at=utcnow(),
            universe_size=len(universe),
            eligible_size=len(eligible),
            suggestions=tuple(suggestions),
        )
        await self.exploration_repository.save_run(run)
        return ExplorerExecutionResult(
            run_id=run.id,
            status=run.status,
            universe_size=run.universe_size,
            eligible_size=run.eligible_size,
            suggestion_count=len(run.suggestions),
        )
