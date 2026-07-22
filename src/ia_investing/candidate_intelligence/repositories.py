from __future__ import annotations

from collections.abc import Iterable
from dataclasses import replace
from typing import Protocol
from uuid import UUID

from .enums import CandidateStatus, SuggestionStatus
from .models import ExplorationRun, ExplorationSuggestion, InvestmentCandidate


class CandidateNotFoundError(LookupError):
    pass


class ConcurrencyConflictError(RuntimeError):
    pass


class DuplicateCandidateError(ValueError):
    pass


class CandidateRepository(Protocol):
    async def get(self, candidate_id: UUID) -> InvestmentCandidate: ...

    async def add(self, candidate: InvestmentCandidate) -> None: ...

    async def save(self, candidate: InvestmentCandidate, *, expected_version: int) -> None: ...

    async def find_active_by_ticker(
        self,
        organization_id: UUID,
        ticker: str,
        exchange: str,
    ) -> InvestmentCandidate | None: ...

    async def list(
        self,
        organization_id: UUID,
        *,
        statuses: frozenset[CandidateStatus] | None = None,
    ) -> tuple[InvestmentCandidate, ...]: ...


class ExplorationRepository(Protocol):
    async def add_run(self, run: ExplorationRun) -> None: ...

    async def get_run(self, run_id: UUID) -> ExplorationRun: ...

    async def save_run(self, run: ExplorationRun) -> None: ...

    async def get_suggestion(self, suggestion_id: UUID) -> ExplorationSuggestion: ...

    async def save_suggestion(self, suggestion: ExplorationSuggestion) -> None: ...


class InMemoryCandidateRepository:
    """Reference repository used by unit tests and local demos.

    Production must use a transactional SQLAlchemy implementation and an outbox.
    """

    def __init__(self) -> None:
        self._items: dict[UUID, InvestmentCandidate] = {}

    async def get(self, candidate_id: UUID) -> InvestmentCandidate:
        try:
            return self._items[candidate_id]
        except KeyError as exc:
            raise CandidateNotFoundError(str(candidate_id)) from exc

    async def add(self, candidate: InvestmentCandidate) -> None:
        duplicate = await self.find_active_by_ticker(
            candidate.organization_id,
            candidate.identity.ticker,
            candidate.identity.exchange,
        )
        if duplicate is not None:
            raise DuplicateCandidateError(
                f"active candidate already exists for {candidate.identity.exchange}:{candidate.identity.ticker}"
            )
        self._items[candidate.id] = candidate

    async def save(self, candidate: InvestmentCandidate, *, expected_version: int) -> None:
        current = await self.get(candidate.id)
        if current.lock_version != expected_version:
            raise ConcurrencyConflictError(f"expected version {expected_version}, found {current.lock_version}")
        self._items[candidate.id] = candidate

    async def find_active_by_ticker(
        self,
        organization_id: UUID,
        ticker: str,
        exchange: str,
    ) -> InvestmentCandidate | None:
        terminal = {CandidateStatus.CANCELLED}
        normalized = ticker.upper()
        for candidate in self._items.values():
            if (
                candidate.organization_id == organization_id
                and candidate.identity.ticker == normalized
                and candidate.identity.exchange.upper() == exchange.upper()
                and candidate.status not in terminal
            ):
                return candidate
        return None

    async def list(
        self,
        organization_id: UUID,
        *,
        statuses: frozenset[CandidateStatus] | None = None,
    ) -> tuple[InvestmentCandidate, ...]:
        values: Iterable[InvestmentCandidate] = (
            candidate for candidate in self._items.values() if candidate.organization_id == organization_id
        )
        if statuses is not None:
            values = (candidate for candidate in values if candidate.status in statuses)
        return tuple(sorted(values, key=lambda item: item.created_at, reverse=True))


class InMemoryExplorationRepository:
    def __init__(self) -> None:
        self._runs: dict[UUID, ExplorationRun] = {}
        self._suggestions: dict[UUID, ExplorationSuggestion] = {}

    async def add_run(self, run: ExplorationRun) -> None:
        self._runs[run.id] = run
        for suggestion in run.suggestions:
            self._suggestions[suggestion.id] = suggestion

    async def get_run(self, run_id: UUID) -> ExplorationRun:
        try:
            return self._runs[run_id]
        except KeyError as exc:
            raise LookupError(str(run_id)) from exc

    async def save_run(self, run: ExplorationRun) -> None:
        self._runs[run.id] = run
        for suggestion in run.suggestions:
            self._suggestions[suggestion.id] = suggestion

    async def get_suggestion(self, suggestion_id: UUID) -> ExplorationSuggestion:
        try:
            return self._suggestions[suggestion_id]
        except KeyError as exc:
            raise LookupError(str(suggestion_id)) from exc

    async def save_suggestion(self, suggestion: ExplorationSuggestion) -> None:
        self._suggestions[suggestion.id] = suggestion
        run = self._runs.get(suggestion.exploration_run_id)
        if run is not None:
            suggestions = tuple(suggestion if item.id == suggestion.id else item for item in run.suggestions)
            self._runs[run.id] = replace(run, suggestions=suggestions)

    async def mark_promoted(self, suggestion_id: UUID, candidate_id: UUID) -> None:
        suggestion = await self.get_suggestion(suggestion_id)
        await self.save_suggestion(
            replace(
                suggestion,
                status=SuggestionStatus.PROMOTED,
                promoted_candidate_id=candidate_id,
            )
        )
