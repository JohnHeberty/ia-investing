from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from ia_investing.candidate_intelligence.contracts import (
    CandidateCreateRequest,
    CandidateReanalysisRequest,
    CandidateSourceCreateRequest,
)
from ia_investing.candidate_intelligence.enums import (
    AnalysisTrigger,
    CandidateDecision,
    CandidateStatus,
    ExplorationRunStatus,
    SourceKind,
    SourceStatus,
    SuggestionStatus,
    VerificationMethod,
)
from ia_investing.candidate_intelligence.models import (
    CandidateIdentity,
    CandidateSource,
    ExplorationRun,
    ExplorationSuggestion,
    InvestmentCandidate,
    utcnow,
)
from ia_investing.candidate_intelligence.repositories import (
    InMemoryCandidateRepository,
    InMemoryExplorationRepository,
)
from ia_investing.candidate_intelligence.services import (
    CandidateService,
    ExplorationService,
    NullEventPublisher,
)


class FakeWorkflowStarter:
    def __init__(self) -> None:
        self.candidate_calls: list[dict[str, object]] = []
        self.exploration_calls: list[dict[str, object]] = []

    async def start_candidate_analysis(self, **kwargs: object) -> str:
        self.candidate_calls.append(kwargs)
        return f"wf-{kwargs['candidate_id']}"

    async def start_exploration(self, *, exploration_run_id: uuid4) -> str:  # type: ignore[override]
        self.exploration_calls.append({"exploration_run_id": exploration_run_id})
        return f"wf-exploration-{exploration_run_id}"


def _verified_source(candidate_id: uuid4, kind: SourceKind) -> CandidateSource:  # type: ignore[override]
    now = utcnow()
    return CandidateSource(
        id=uuid4(),
        candidate_id=candidate_id,
        kind=kind,
        url=f"https://example.com/{kind.value}",
        status=SourceStatus.VERIFIED,
        verification_method=VerificationMethod.CROSS_SOURCE_MATCH,
        confidence=Decimal("0.95"),
        official=True,
        discovered_by="test",
        created_at=now,
        verified_at=now,
        last_checked_at=now,
    )


def _make_candidate(**overrides: object) -> InvestmentCandidate:
    defaults = {
        "organization_id": uuid4(),
        "identity": CandidateIdentity(ticker="PETR4"),
        "actor_id": "test",
        "rationale": None,
    }
    defaults.update(overrides)
    return InvestmentCandidate.create_manual(
        organization_id=defaults["organization_id"],
        identity=defaults["identity"],
        actor_id=defaults["actor_id"],
        rationale=defaults["rationale"],
    )


def _make_suggestion(**overrides: object) -> ExplorationSuggestion:
    now = utcnow()
    defaults = {
        "id": uuid4(),
        "exploration_run_id": uuid4(),
        "organization_id": uuid4(),
        "identity": CandidateIdentity(ticker="VALE3"),
        "status": SuggestionStatus.NEW,
        "quantitative_score": Decimal("0.80"),
        "data_coverage_score": Decimal("0.70"),
        "source_discovery_score": Decimal("0.60"),
        "rationale": "Strong fundamentals",
        "signals": ("value",),
        "risks": (),
        "discovered_sources": (),
        "created_at": now,
    }
    defaults.update(overrides)
    return ExplorationSuggestion(**defaults)  # type: ignore[arg-type]


class TestCandidateServiceCreateManual:
    @pytest.mark.asyncio
    async def test_create_manual_returns_candidate_and_run(self) -> None:
        repo = InMemoryCandidateRepository()
        wf = FakeWorkflowStarter()
        svc = CandidateService(repository=repo, workflow_starter=wf)
        candidate, run, workflow_id = await svc.create_manual(
            organization_id=uuid4(),
            actor_id="test",
            request=CandidateCreateRequest(ticker="ITUB4"),
            data_as_of=datetime.now(UTC),
        )
        assert candidate.status is CandidateStatus.IDENTITY_RESOLUTION
        assert run.status.value == "queued"
        assert workflow_id.startswith("wf-")
        assert len(wf.candidate_calls) == 1

    @pytest.mark.asyncio
    async def test_create_manual_persists_candidate(self) -> None:
        repo = InMemoryCandidateRepository()
        wf = FakeWorkflowStarter()
        svc = CandidateService(repository=repo, workflow_starter=wf)
        candidate, _, _ = await svc.create_manual(
            organization_id=uuid4(),
            actor_id="test",
            request=CandidateCreateRequest(ticker="BBDC4"),
            data_as_of=datetime.now(UTC),
        )
        loaded = await repo.get(candidate.id)
        assert loaded.id == candidate.id

    @pytest.mark.asyncio
    async def test_create_manual_publishes_event(self) -> None:
        repo = InMemoryCandidateRepository()
        wf = FakeWorkflowStarter()
        publisher = AsyncMock()
        svc = CandidateService(repository=repo, workflow_starter=wf, publisher=publisher)
        _candidate, _run, _workflow_id = await svc.create_manual(
            organization_id=uuid4(),
            actor_id="test",
            request=CandidateCreateRequest(ticker="ABEV3"),
            data_as_of=datetime.now(UTC),
        )
        publisher.publish.assert_awaited_once()
        args = publisher.publish.call_args
        assert args[0][0] == "investment_candidate.created"

    @pytest.mark.asyncio
    async def test_create_manual_creates_blocking_gaps(self) -> None:
        repo = InMemoryCandidateRepository()
        wf = FakeWorkflowStarter()
        svc = CandidateService(repository=repo, workflow_starter=wf)
        candidate, _, _ = await svc.create_manual(
            organization_id=uuid4(),
            actor_id="test",
            request=CandidateCreateRequest(ticker="WEGE3"),
            data_as_of=datetime.now(UTC),
        )
        assert len(candidate.blocking_gaps) > 0


class TestCandidateServiceAddUserSource:
    @pytest.mark.asyncio
    async def test_add_user_source_adds_source_to_candidate(self) -> None:
        repo = InMemoryCandidateRepository()
        wf = FakeWorkflowStarter()
        svc = CandidateService(repository=repo, workflow_starter=wf)
        candidate, _, _ = await svc.create_manual(
            organization_id=uuid4(),
            actor_id="test",
            request=CandidateCreateRequest(ticker="PETR4"),
            data_as_of=datetime.now(UTC),
        )
        updated = await svc.add_user_source(
            candidate_id=candidate.id,
            actor_id="test",
            request=CandidateSourceCreateRequest(
                kind=SourceKind.FINANCIAL_REPORTS,
                url="https://ri.petrobras.com.br/",  # type: ignore[arg-type]
            ),
            expected_version=candidate.lock_version,
        )
        assert len(updated.sources) == 1
        assert updated.sources[0].kind is SourceKind.FINANCIAL_REPORTS
        assert updated.sources[0].status is SourceStatus.DISCOVERED

    @pytest.mark.asyncio
    async def test_add_user_source_does_not_transition_without_enough_sources(self) -> None:
        repo = InMemoryCandidateRepository()
        wf = FakeWorkflowStarter()
        svc = CandidateService(repository=repo, workflow_starter=wf)
        candidate, _, _ = await svc.create_manual(
            organization_id=uuid4(),
            actor_id="test",
            request=CandidateCreateRequest(ticker="PETR4"),
            data_as_of=datetime.now(UTC),
        )
        updated = await svc.add_user_source(
            candidate_id=candidate.id,
            actor_id="test",
            request=CandidateSourceCreateRequest(
                kind=SourceKind.COMPANY_WEBSITE,
                url="https://petrobras.com.br/",  # type: ignore[arg-type]
            ),
            expected_version=candidate.lock_version,
        )
        assert updated.status is CandidateStatus.IDENTITY_RESOLUTION


class TestCandidateServiceResolveGap:
    @pytest.mark.asyncio
    async def test_resolve_gap_marks_gap_resolved(self) -> None:
        repo = InMemoryCandidateRepository()
        wf = FakeWorkflowStarter()
        svc = CandidateService(repository=repo, workflow_starter=wf)
        candidate, _, _ = await svc.create_manual(
            organization_id=uuid4(),
            actor_id="test",
            request=CandidateCreateRequest(ticker="PETR4"),
            data_as_of=datetime.now(UTC),
        )
        gap = candidate.gaps[0]
        updated = await svc.resolve_gap(
            candidate_id=candidate.id,
            gap_id=gap.id,
            actor_id="test",
            notes="Provided by user",
            expected_version=candidate.lock_version,
        )
        resolved = [g for g in updated.gaps if g.id == gap.id]
        assert len(resolved) == 1
        assert resolved[0].status.value == "resolved"
        assert resolved[0].resolved_by == "test"

    @pytest.mark.asyncio
    async def test_resolve_gap_raises_on_missing_gap(self) -> None:
        repo = InMemoryCandidateRepository()
        wf = FakeWorkflowStarter()
        svc = CandidateService(repository=repo, workflow_starter=wf)
        candidate, _, _ = await svc.create_manual(
            organization_id=uuid4(),
            actor_id="test",
            request=CandidateCreateRequest(ticker="PETR4"),
            data_as_of=datetime.now(UTC),
        )
        with pytest.raises(LookupError):
            await svc.resolve_gap(
                candidate_id=candidate.id,
                gap_id=uuid4(),
                actor_id="test",
                notes="Some notes",
                expected_version=candidate.lock_version,
            )


class TestCandidateServiceRequestReanalysis:
    @pytest.mark.asyncio
    async def test_reanalysis_allows_with_allow_incomplete(self) -> None:
        repo = InMemoryCandidateRepository()
        wf = FakeWorkflowStarter()
        svc = CandidateService(repository=repo, workflow_starter=wf)
        candidate, _, _ = await svc.create_manual(
            organization_id=uuid4(),
            actor_id="test",
            request=CandidateCreateRequest(ticker="PETR4"),
            data_as_of=datetime.now(UTC),
        )
        updated, run, _workflow_id = await svc.request_reanalysis(
            candidate_id=candidate.id,
            actor_id="test",
            request=CandidateReanalysisRequest(
                trigger=AnalysisTrigger.MANUAL_RETRY,
                data_as_of=datetime.now(UTC),
                allow_incomplete=True,
            ),
            expected_version=candidate.lock_version,
        )
        assert len(updated.analysis_runs) == 2
        assert run.status.value == "queued"

    @pytest.mark.asyncio
    async def test_reanalysis_transitions_from_watchlist(self) -> None:
        from dataclasses import replace as dc_replace

        repo = InMemoryCandidateRepository()
        wf = FakeWorkflowStarter()
        svc = CandidateService(repository=repo, workflow_starter=wf)
        candidate, _, _ = await svc.create_manual(
            organization_id=uuid4(),
            actor_id="test",
            request=CandidateCreateRequest(ticker="PETR4"),
            data_as_of=datetime.now(UTC),
        )
        candidate = dc_replace(candidate, status=CandidateStatus.WATCHLIST, lock_version=candidate.lock_version + 1)
        await repo.save(candidate, expected_version=candidate.lock_version - 1)
        updated, _, _ = await svc.request_reanalysis(
            candidate_id=candidate.id,
            actor_id="test",
            request=CandidateReanalysisRequest(
                trigger=AnalysisTrigger.USER_COMPLETION,
                data_as_of=datetime.now(UTC),
                allow_incomplete=True,
            ),
            expected_version=candidate.lock_version,
        )
        assert updated.status is CandidateStatus.SOURCE_DISCOVERY


class TestCandidateServiceApplyDecision:
    @pytest.mark.asyncio
    async def test_apply_reject_decision(self) -> None:
        from dataclasses import replace as dc_replace

        repo = InMemoryCandidateRepository()
        wf = FakeWorkflowStarter()
        svc = CandidateService(repository=repo, workflow_starter=wf)
        candidate, _, _ = await svc.create_manual(
            organization_id=uuid4(),
            actor_id="test",
            request=CandidateCreateRequest(ticker="PETR4"),
            data_as_of=datetime.now(UTC),
        )
        candidate = dc_replace(
            candidate, status=CandidateStatus.COMMITTEE_REVIEW, lock_version=candidate.lock_version + 1
        )
        await repo.save(candidate, expected_version=candidate.lock_version - 1)
        updated = await svc.apply_decision(
            candidate_id=candidate.id,
            decision=CandidateDecision.REJECT,
            reason="Does not meet criteria",
            expected_version=candidate.lock_version,
        )
        assert updated.status is CandidateStatus.REJECTED
        assert updated.final_decision is CandidateDecision.REJECT
        assert updated.final_decision_reason == "Does not meet criteria"

    @pytest.mark.asyncio
    async def test_apply_approve_checks_readiness(self) -> None:
        from dataclasses import replace as dc_replace

        repo = InMemoryCandidateRepository()
        wf = FakeWorkflowStarter()
        svc = CandidateService(repository=repo, workflow_starter=wf)
        candidate, _, _ = await svc.create_manual(
            organization_id=uuid4(),
            actor_id="test",
            request=CandidateCreateRequest(ticker="PETR4"),
            data_as_of=datetime.now(UTC),
        )
        candidate = dc_replace(
            candidate, status=CandidateStatus.COMMITTEE_REVIEW, lock_version=candidate.lock_version + 1
        )
        await repo.save(candidate, expected_version=candidate.lock_version - 1)
        with pytest.raises(ValueError, match="readiness"):
            await svc.apply_decision(
                candidate_id=candidate.id,
                decision=CandidateDecision.APPROVE,
                reason="Approved",
                expected_version=candidate.lock_version,
            )

    @pytest.mark.asyncio
    async def test_apply_watchlist_decision(self) -> None:
        from dataclasses import replace as dc_replace

        repo = InMemoryCandidateRepository()
        wf = FakeWorkflowStarter()
        svc = CandidateService(repository=repo, workflow_starter=wf)
        candidate, _, _ = await svc.create_manual(
            organization_id=uuid4(),
            actor_id="test",
            request=CandidateCreateRequest(ticker="PETR4"),
            data_as_of=datetime.now(UTC),
        )
        candidate = dc_replace(
            candidate, status=CandidateStatus.COMMITTEE_REVIEW, lock_version=candidate.lock_version + 1
        )
        await repo.save(candidate, expected_version=candidate.lock_version - 1)
        updated = await svc.apply_decision(
            candidate_id=candidate.id,
            decision=CandidateDecision.WATCHLIST,
            reason="Monitor",
            expected_version=candidate.lock_version,
        )
        assert updated.status is CandidateStatus.WATCHLIST
        assert updated.approved_portfolio_eligible is False


class TestExplorationServiceCreateRun:
    @pytest.mark.asyncio
    async def test_create_run_returns_exploration_run(self) -> None:
        expl_repo = InMemoryExplorationRepository()
        cand_repo = InMemoryCandidateRepository()
        wf = FakeWorkflowStarter()
        svc = ExplorationService(
            exploration_repository=expl_repo,
            candidate_repository=cand_repo,
            workflow_starter=wf,
        )
        run, workflow_id = await svc.create_run(
            organization_id=uuid4(),
            actor_id="test",
            strategy_codes=("value",),
            data_as_of=datetime.now(UTC),
            minimum_liquidity=Decimal("100000"),
            maximum_suggestions=10,
        )
        assert run.status is ExplorationRunStatus.QUEUED
        assert workflow_id.startswith("wf-exploration-")

    @pytest.mark.asyncio
    async def test_create_run_persists_in_repo(self) -> None:
        expl_repo = InMemoryExplorationRepository()
        cand_repo = InMemoryCandidateRepository()
        wf = FakeWorkflowStarter()
        svc = ExplorationService(
            exploration_repository=expl_repo,
            candidate_repository=cand_repo,
            workflow_starter=wf,
        )
        run, _ = await svc.create_run(
            organization_id=uuid4(),
            actor_id="test",
            strategy_codes=("value",),
            data_as_of=datetime.now(UTC),
            minimum_liquidity=Decimal("50000"),
            maximum_suggestions=5,
        )
        loaded = await expl_repo.get_run(run.id)
        assert loaded.id == run.id
        assert loaded.workflow_id is not None


class TestExplorationServicePromoteSuggestion:
    @pytest.mark.asyncio
    async def test_promote_new_suggestion_creates_candidate(self) -> None:
        expl_repo = InMemoryExplorationRepository()
        cand_repo = InMemoryCandidateRepository()
        wf = FakeWorkflowStarter()
        svc = ExplorationService(
            exploration_repository=expl_repo,
            candidate_repository=cand_repo,
            workflow_starter=wf,
        )
        suggestion = _make_suggestion()
        run = ExplorationRun(
            id=suggestion.exploration_run_id,
            organization_id=suggestion.organization_id,
            status=ExplorationRunStatus.SUCCEEDED,
            strategy_codes=("value",),
            requested_by="test",
            created_at=utcnow(),
            data_as_of=datetime.now(UTC),
            minimum_liquidity=Decimal("100000"),
            maximum_suggestions=10,
            suggestions=(suggestion,),
        )
        await expl_repo.add_run(run)
        candidate = await svc.promote_suggestion(
            suggestion_id=suggestion.id,
            actor_id="test",
        )
        assert candidate.identity.ticker == "VALE3"
        assert candidate.origin.value == "explorer"

    @pytest.mark.asyncio
    async def test_promote_non_new_suggestion_raises(self) -> None:
        expl_repo = InMemoryExplorationRepository()
        cand_repo = InMemoryCandidateRepository()
        wf = FakeWorkflowStarter()
        svc = ExplorationService(
            exploration_repository=expl_repo,
            candidate_repository=cand_repo,
            workflow_starter=wf,
        )
        suggestion = _make_suggestion(status=SuggestionStatus.PROMOTED)
        run = ExplorationRun(
            id=suggestion.exploration_run_id,
            organization_id=suggestion.organization_id,
            status=ExplorationRunStatus.SUCCEEDED,
            strategy_codes=("value",),
            requested_by="test",
            created_at=utcnow(),
            data_as_of=datetime.now(UTC),
            minimum_liquidity=Decimal("100000"),
            maximum_suggestions=10,
            suggestions=(suggestion,),
        )
        await expl_repo.add_run(run)
        with pytest.raises(ValueError, match="only new"):
            await svc.promote_suggestion(suggestion_id=suggestion.id, actor_id="test")

    @pytest.mark.asyncio
    async def test_promote_duplicate_returns_existing_candidate(self) -> None:
        expl_repo = InMemoryExplorationRepository()
        cand_repo = InMemoryCandidateRepository()
        wf = FakeWorkflowStarter()
        svc = ExplorationService(
            exploration_repository=expl_repo,
            candidate_repository=cand_repo,
            workflow_starter=wf,
        )
        existing = _make_candidate(
            identity=CandidateIdentity(ticker="VALE3"),
        )
        await cand_repo.add(existing)
        suggestion = _make_suggestion(
            organization_id=existing.organization_id,
        )
        run = ExplorationRun(
            id=suggestion.exploration_run_id,
            organization_id=suggestion.organization_id,
            status=ExplorationRunStatus.SUCCEEDED,
            strategy_codes=("value",),
            requested_by="test",
            created_at=utcnow(),
            data_as_of=datetime.now(UTC),
            minimum_liquidity=Decimal("100000"),
            maximum_suggestions=10,
            suggestions=(suggestion,),
        )
        await expl_repo.add_run(run)
        result = await svc.promote_suggestion(
            suggestion_id=suggestion.id,
            actor_id="test",
        )
        assert result.id == existing.id
        updated_suggestion = await expl_repo.get_suggestion(suggestion.id)
        assert updated_suggestion.status is SuggestionStatus.DUPLICATE


class TestNullEventPublisher:
    @pytest.mark.asyncio
    async def test_publish_returns_none(self) -> None:
        pub = NullEventPublisher()
        result = await pub.publish("test.event", {})
        assert result is None
