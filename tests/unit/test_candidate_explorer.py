from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest

from ia_investing.candidate_intelligence.contracts import (
    AutonomousExplorerOutput,
    ExplorerCandidateFinding,
)
from ia_investing.candidate_intelligence.enums import (
    ExplorationRunStatus,
)
from ia_investing.candidate_intelligence.explorer import (
    AutonomousExplorationOrchestrator,
    ScreenedSecurity,
    UniverseSecurity,
)
from ia_investing.candidate_intelligence.models import (
    CandidateIdentity,
    ExplorationRun,
    utcnow,
)
from ia_investing.candidate_intelligence.repositories import (
    InMemoryCandidateRepository,
    InMemoryExplorationRepository,
)


def _universe_security(
    ticker: str = "PETR4",
    active: bool = True,
    restricted: bool = False,
    liquidity: Decimal = Decimal("1000000"),
    coverage: Decimal = Decimal("0.80"),
) -> UniverseSecurity:
    return UniverseSecurity(
        instrument_id=uuid4(),
        issuer_id=uuid4(),
        ticker=ticker,
        exchange="B3",
        legal_name=f"{ticker} SA",
        cnpj="33.000.167/0001-01",
        cvm_code="12345",
        average_daily_liquidity=liquidity,
        active=active,
        restricted=restricted,
        data_coverage_score=coverage,
    )


def _screened_security(
    ticker: str = "PETR4",
    score: Decimal = Decimal("0.85"),
) -> ScreenedSecurity:
    return ScreenedSecurity(
        security=_universe_security(ticker=ticker),
        quantitative_score=score,
        signals=("value",),
        risk_flags=(),
    )


def _make_run(
    status: ExplorationRunStatus = ExplorationRunStatus.QUEUED,
    strategy_codes: tuple[str, ...] = ("value",),
    maximum_suggestions: int = 10,
    excluded: tuple[UUID, ...] = (),
    minimum_liquidity: Decimal = Decimal("100000"),
    organization_id: UUID | None = None,
) -> ExplorationRun:
    return ExplorationRun(
        id=uuid4(),
        organization_id=organization_id or uuid4(),
        status=status,
        strategy_codes=strategy_codes,
        requested_by="test",
        created_at=utcnow(),
        data_as_of=datetime.now(UTC),
        minimum_liquidity=minimum_liquidity,
        maximum_suggestions=maximum_suggestions,
        excluded_instrument_ids=excluded,
    )


def _build_orchestrator(
    universe: tuple[UniverseSecurity, ...] | None = None,
    screened: tuple[ScreenedSecurity, ...] | None = None,
) -> tuple[AutonomousExplorationOrchestrator, InMemoryExplorationRepository, InMemoryCandidateRepository]:
    expl_repo = InMemoryExplorationRepository()
    cand_repo = InMemoryCandidateRepository()
    universe_provider = AsyncMock()
    universe_provider.snapshot = AsyncMock(return_value=universe or ())
    screener = AsyncMock()
    screener.screen = AsyncMock(return_value=screened or ())
    explorer_agent = AsyncMock()
    orch = AutonomousExplorationOrchestrator(
        exploration_repository=expl_repo,
        candidate_repository=cand_repo,
        universe_provider=universe_provider,
        screener=screener,
        explorer_agent=explorer_agent,
    )
    return orch, expl_repo, cand_repo


class TestExplorerHappyPath:
    @pytest.mark.asyncio
    async def test_run_completes_succeeded(self) -> None:
        orch, expl_repo, _ = _build_orchestrator()
        orch.explorer_agent.investigate = AsyncMock(
            return_value=AutonomousExplorerOutput(
                universe_size=0, eligible_size=0, candidates=(), methodology_summary="Test"
            )
        )
        run = _make_run()
        await expl_repo.add_run(run)
        result = await orch.run(run.id)
        assert result.status is ExplorationRunStatus.SUCCEEDED

    @pytest.mark.asyncio
    async def test_run_rejects_non_queued(self) -> None:
        orch, expl_repo, _ = _build_orchestrator()
        run = _make_run(status=ExplorationRunStatus.RUNNING)
        await expl_repo.add_run(run)
        with pytest.raises(ValueError, match="only queued"):
            await orch.run(run.id)


class TestExplorerUniverseFiltering:
    @pytest.mark.asyncio
    async def test_inactive_securities_excluded(self) -> None:
        active = _universe_security(ticker="PETR4", active=True)
        inactive = _universe_security(ticker="VALE3", active=False)
        orch, expl_repo, _ = _build_orchestrator(universe=(active, inactive))
        run = _make_run()
        await expl_repo.add_run(run)
        orch.explorer_agent.investigate = AsyncMock(
            return_value=AutonomousExplorerOutput(
                universe_size=2, eligible_size=1, candidates=(), methodology_summary="Test"
            )
        )
        result = await orch.run(run.id)
        assert result.universe_size == 2
        assert result.eligible_size == 1

    @pytest.mark.asyncio
    async def test_restricted_securities_excluded(self) -> None:
        normal = _universe_security(ticker="PETR4")
        restricted = _universe_security(ticker="VALE3", restricted=True)
        orch, expl_repo, _ = _build_orchestrator(universe=(normal, restricted))
        run = _make_run()
        await expl_repo.add_run(run)
        orch.explorer_agent.investigate = AsyncMock(
            return_value=AutonomousExplorerOutput(
                universe_size=2, eligible_size=1, candidates=(), methodology_summary="Test"
            )
        )
        result = await orch.run(run.id)
        assert result.eligible_size == 1

    @pytest.mark.asyncio
    async def test_low_liquidity_excluded(self) -> None:
        liquid = _universe_security(ticker="PETR4", liquidity=Decimal("1000000"))
        illiquid = _universe_security(ticker="VALE3", liquidity=Decimal("50000"))
        orch, expl_repo, _ = _build_orchestrator(universe=(liquid, illiquid))
        run = _make_run(minimum_liquidity=Decimal("100000"))
        await expl_repo.add_run(run)
        orch.explorer_agent.investigate = AsyncMock(
            return_value=AutonomousExplorerOutput(
                universe_size=2, eligible_size=1, candidates=(), methodology_summary="Test"
            )
        )
        result = await orch.run(run.id)
        assert result.eligible_size == 1

    @pytest.mark.asyncio
    async def test_low_coverage_excluded(self) -> None:
        good = _universe_security(ticker="PETR4", coverage=Decimal("0.80"))
        bad = _universe_security(ticker="VALE3", coverage=Decimal("0.40"))
        orch, expl_repo, _ = _build_orchestrator(universe=(good, bad))
        run = _make_run()
        await expl_repo.add_run(run)
        orch.explorer_agent.investigate = AsyncMock(
            return_value=AutonomousExplorerOutput(
                universe_size=2, eligible_size=1, candidates=(), methodology_summary="Test"
            )
        )
        result = await orch.run(run.id)
        assert result.eligible_size == 1

    @pytest.mark.asyncio
    async def test_excluded_instrument_ids_filtered(self) -> None:
        sec1 = _universe_security(ticker="PETR4")
        sec2 = _universe_security(ticker="VALE3")
        orch, expl_repo, _ = _build_orchestrator(universe=(sec1, sec2))
        run = _make_run(excluded=(sec2.instrument_id,))
        await expl_repo.add_run(run)
        orch.explorer_agent.investigate = AsyncMock(
            return_value=AutonomousExplorerOutput(
                universe_size=2, eligible_size=1, candidates=(), methodology_summary="Test"
            )
        )
        result = await orch.run(run.id)
        assert result.eligible_size == 1


class TestExplorerDuplicateDetection:
    @pytest.mark.asyncio
    async def test_existing_candidate_excluded(self) -> None:
        from ia_investing.candidate_intelligence.models import InvestmentCandidate

        cand_repo = InMemoryCandidateRepository()
        org_id = uuid4()
        existing = InvestmentCandidate.create_manual(
            organization_id=org_id,
            identity=CandidateIdentity(ticker="PETR4"),
            actor_id="test",
        )
        await cand_repo.add(existing)

        sec = _universe_security(ticker="PETR4")
        orch, expl_repo, _ = _build_orchestrator(universe=(sec,))
        orch.candidate_repository = cand_repo
        run = _make_run(organization_id=org_id)
        await expl_repo.add_run(run)

        orch.explorer_agent.investigate = AsyncMock(
            return_value=AutonomousExplorerOutput(
                universe_size=1, eligible_size=0, candidates=(), methodology_summary="Test"
            )
        )
        result = await orch.run(run.id)
        assert result.eligible_size == 0


class TestExplorerPartialStatus:
    @pytest.mark.asyncio
    async def test_partial_when_suggestions_fewer_than_candidates(self) -> None:
        sec = _screened_security(ticker="PETR4")
        finding = ExplorerCandidateFinding(
            ticker="PETR4",
            exchange="B3",
            quantitative_score=Decimal("0.80"),
            data_coverage_score=Decimal("0.70"),
            source_discovery_score=Decimal("0.60"),
            rationale="Value play",
            signals=("value",),
        )
        orch, expl_repo, _ = _build_orchestrator(screened=(sec,))
        orch.explorer_agent.investigate = AsyncMock(
            return_value=AutonomousExplorerOutput(
                universe_size=1,
                eligible_size=1,
                candidates=(finding, finding),
                methodology_summary="Test",
            )
        )
        run = _make_run(maximum_suggestions=1)
        await expl_repo.add_run(run)
        result = await orch.run(run.id)
        assert result.status is ExplorationRunStatus.PARTIAL
        assert result.suggestion_count == 1
