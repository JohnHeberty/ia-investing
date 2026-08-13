from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest

from ia_investing.candidate_intelligence.enums import (
    CandidateStatus,
    ExplorationRunStatus,
    SuggestionStatus,
)
from ia_investing.candidate_intelligence.models import (
    CandidateIdentity,
    ExplorationRun,
    ExplorationSuggestion,
    InvestmentCandidate,
    utcnow,
)
from ia_investing.candidate_intelligence.repositories import (
    CandidateNotFoundError,
    ConcurrencyConflictError,
    DuplicateCandidateError,
    InMemoryCandidateRepository,
    InMemoryExplorationRepository,
)


def _make_candidate(
    ticker: str = "PETR4",
    organization_id: uuid4 | None = None,  # type: ignore[override]
    status: CandidateStatus = CandidateStatus.IDENTITY_RESOLUTION,
) -> InvestmentCandidate:
    c = InvestmentCandidate.create_manual(
        organization_id=organization_id or uuid4(),
        identity=CandidateIdentity(ticker=ticker),
        actor_id="test",
    )
    if status != CandidateStatus.IDENTITY_RESOLUTION:
        from dataclasses import replace

        c = replace(c, status=status)
    return c


def _make_suggestion(
    exploration_run_id: uuid4 | None = None,  # type: ignore[override]
    organization_id: uuid4 | None = None,  # type: ignore[override]
    ticker: str = "VALE3",
) -> ExplorationSuggestion:
    return ExplorationSuggestion(
        id=uuid4(),
        exploration_run_id=exploration_run_id or uuid4(),
        organization_id=organization_id or uuid4(),
        identity=CandidateIdentity(ticker=ticker),
        status=SuggestionStatus.NEW,
        quantitative_score=Decimal("0.80"),
        data_coverage_score=Decimal("0.70"),
        source_discovery_score=Decimal("0.60"),
        rationale="Strong fundamentals",
        signals=(),
        risks=(),
        discovered_sources=(),
        created_at=utcnow(),
    )


class TestInMemoryCandidateRepository:
    @pytest.mark.asyncio
    async def test_add_and_get(self) -> None:
        repo = InMemoryCandidateRepository()
        candidate = _make_candidate()
        await repo.add(candidate)
        loaded = await repo.get(candidate.id)
        assert loaded.id == candidate.id

    @pytest.mark.asyncio
    async def test_get_missing_raises(self) -> None:
        repo = InMemoryCandidateRepository()
        with pytest.raises(CandidateNotFoundError):
            await repo.get(uuid4())

    @pytest.mark.asyncio
    async def test_add_duplicate_ticker_raises(self) -> None:
        repo = InMemoryCandidateRepository()
        org_id = uuid4()
        c1 = _make_candidate(ticker="PETR4", organization_id=org_id)
        await repo.add(c1)
        c2 = _make_candidate(ticker="PETR4", organization_id=org_id)
        with pytest.raises(DuplicateCandidateError):
            await repo.add(c2)

    @pytest.mark.asyncio
    async def test_save_with_correct_version(self) -> None:
        repo = InMemoryCandidateRepository()
        candidate = _make_candidate()
        await repo.add(candidate)
        from dataclasses import replace

        updated = replace(candidate, lock_version=candidate.lock_version + 1)
        await repo.save(updated, expected_version=candidate.lock_version)
        loaded = await repo.get(candidate.id)
        assert loaded.lock_version == candidate.lock_version + 1

    @pytest.mark.asyncio
    async def test_save_with_wrong_version_raises(self) -> None:
        repo = InMemoryCandidateRepository()
        candidate = _make_candidate()
        await repo.add(candidate)
        from dataclasses import replace

        updated = replace(candidate, lock_version=candidate.lock_version + 1)
        with pytest.raises(ConcurrencyConflictError):
            await repo.save(updated, expected_version=999)

    @pytest.mark.asyncio
    async def test_find_active_by_ticker(self) -> None:
        repo = InMemoryCandidateRepository()
        org_id = uuid4()
        c = _make_candidate(ticker="PETR4", organization_id=org_id)
        await repo.add(c)
        found = await repo.find_active_by_ticker(org_id, "PETR4", "B3")
        assert found is not None
        assert found.id == c.id

    @pytest.mark.asyncio
    async def test_find_active_by_ticker_returns_none_for_cancelled(self) -> None:
        repo = InMemoryCandidateRepository()
        org_id = uuid4()
        c = _make_candidate(ticker="PETR4", organization_id=org_id, status=CandidateStatus.CANCELLED)
        await repo.add(c)
        found = await repo.find_active_by_ticker(org_id, "PETR4", "B3")
        assert found is None

    @pytest.mark.asyncio
    async def test_find_active_by_ticker_case_insensitive(self) -> None:
        repo = InMemoryCandidateRepository()
        org_id = uuid4()
        c = _make_candidate(ticker="PETR4", organization_id=org_id)
        await repo.add(c)
        found = await repo.find_active_by_ticker(org_id, "petr4", "b3")
        assert found is not None

    @pytest.mark.asyncio
    async def test_list_filters_by_status(self) -> None:
        repo = InMemoryCandidateRepository()
        org_id = uuid4()
        c1 = _make_candidate(ticker="PETR4", organization_id=org_id)
        c2 = _make_candidate(ticker="VALE3", organization_id=org_id)
        from dataclasses import replace

        c2 = replace(c2, status=CandidateStatus.APPROVED)
        await repo.add(c1)
        await repo.add(c2)
        results = await repo.list(org_id, statuses=frozenset({CandidateStatus.APPROVED}))
        assert len(results) == 1
        assert results[0].identity.ticker == "VALE3"

    @pytest.mark.asyncio
    async def test_list_all_for_org(self) -> None:
        repo = InMemoryCandidateRepository()
        org_id = uuid4()
        await repo.add(_make_candidate(ticker="PETR4", organization_id=org_id))
        await repo.add(_make_candidate(ticker="VALE3", organization_id=org_id))
        results = await repo.list(org_id)
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_list_excludes_other_org(self) -> None:
        repo = InMemoryCandidateRepository()
        await repo.add(_make_candidate(ticker="PETR4", organization_id=uuid4()))
        results = await repo.list(uuid4())
        assert len(results) == 0


class TestInMemoryExplorationRepository:
    @pytest.mark.asyncio
    async def test_add_and_get_run(self) -> None:
        repo = InMemoryExplorationRepository()
        run = ExplorationRun(
            id=uuid4(),
            organization_id=uuid4(),
            status=ExplorationRunStatus.QUEUED,
            strategy_codes=("value",),
            requested_by="test",
            created_at=utcnow(),
            data_as_of=utcnow(),
            minimum_liquidity=Decimal("100000"),
            maximum_suggestions=10,
        )
        await repo.add_run(run)
        loaded = await repo.get_run(run.id)
        assert loaded.id == run.id

    @pytest.mark.asyncio
    async def test_get_missing_run_raises(self) -> None:
        repo = InMemoryExplorationRepository()
        with pytest.raises(LookupError):
            await repo.get_run(uuid4())

    @pytest.mark.asyncio
    async def test_save_run(self) -> None:
        repo = InMemoryExplorationRepository()
        run = ExplorationRun(
            id=uuid4(),
            organization_id=uuid4(),
            status=ExplorationRunStatus.QUEUED,
            strategy_codes=("value",),
            requested_by="test",
            created_at=utcnow(),
            data_as_of=utcnow(),
            minimum_liquidity=Decimal("100000"),
            maximum_suggestions=10,
        )
        await repo.add_run(run)
        from dataclasses import replace

        updated = replace(run, status=ExplorationRunStatus.RUNNING)
        await repo.save_run(updated)
        loaded = await repo.get_run(run.id)
        assert loaded.status is ExplorationRunStatus.RUNNING

    @pytest.mark.asyncio
    async def test_add_run_persists_suggestions(self) -> None:
        repo = InMemoryExplorationRepository()
        suggestion = _make_suggestion()
        run = ExplorationRun(
            id=suggestion.exploration_run_id,
            organization_id=suggestion.organization_id,
            status=ExplorationRunStatus.QUEUED,
            strategy_codes=("value",),
            requested_by="test",
            created_at=utcnow(),
            data_as_of=utcnow(),
            minimum_liquidity=Decimal("100000"),
            maximum_suggestions=10,
            suggestions=(suggestion,),
        )
        await repo.add_run(run)
        loaded = await repo.get_suggestion(suggestion.id)
        assert loaded.id == suggestion.id

    @pytest.mark.asyncio
    async def test_get_suggestion_missing_raises(self) -> None:
        repo = InMemoryExplorationRepository()
        with pytest.raises(LookupError):
            await repo.get_suggestion(uuid4())

    @pytest.mark.asyncio
    async def test_save_suggestion_updates_run(self) -> None:
        repo = InMemoryExplorationRepository()
        suggestion = _make_suggestion()
        run = ExplorationRun(
            id=suggestion.exploration_run_id,
            organization_id=suggestion.organization_id,
            status=ExplorationRunStatus.QUEUED,
            strategy_codes=("value",),
            requested_by="test",
            created_at=utcnow(),
            data_as_of=utcnow(),
            minimum_liquidity=Decimal("100000"),
            maximum_suggestions=10,
            suggestions=(suggestion,),
        )
        await repo.add_run(run)
        from dataclasses import replace

        updated_suggestion = replace(suggestion, status=SuggestionStatus.PROMOTED, promoted_candidate_id=uuid4())
        await repo.save_suggestion(updated_suggestion)
        loaded_suggestion = await repo.get_suggestion(suggestion.id)
        assert loaded_suggestion.status is SuggestionStatus.PROMOTED

    @pytest.mark.asyncio
    async def test_mark_promoted(self) -> None:
        repo = InMemoryExplorationRepository()
        suggestion = _make_suggestion()
        run = ExplorationRun(
            id=suggestion.exploration_run_id,
            organization_id=suggestion.organization_id,
            status=ExplorationRunStatus.QUEUED,
            strategy_codes=("value",),
            requested_by="test",
            created_at=utcnow(),
            data_as_of=utcnow(),
            minimum_liquidity=Decimal("100000"),
            maximum_suggestions=10,
            suggestions=(suggestion,),
        )
        await repo.add_run(run)
        candidate_id = uuid4()
        await repo.mark_promoted(suggestion.id, candidate_id)
        loaded = await repo.get_suggestion(suggestion.id)
        assert loaded.status is SuggestionStatus.PROMOTED
        assert loaded.promoted_candidate_id == candidate_id
