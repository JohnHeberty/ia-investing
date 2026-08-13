from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from ia_investing.orchestration.activities.candidate_intelligence import (
    CallbackCandidateActivityRuntime,
    CandidateCheckpoint,
    CandidateSourceValidationInput,
    CandidateSourceValidationResult,
    CandidateWorkflowInput,
    CandidateWorkflowResult,
    ExplorationFindings,
    ExplorationShortlist,
    ExplorationWorkflowInput,
    ExplorationWorkflowResult,
    ScheduledExplorationInput,
    SourceDiscoveryCheckpoint,
    candidate_activity_runtime_configured,
    configure_candidate_activity_runtime,
    reset_candidate_activity_runtime_for_tests,
)


def _workflow_input(**overrides: object) -> CandidateWorkflowInput:
    defaults = {
        "candidate_id": uuid4(),
        "analysis_run_id": uuid4(),
        "organization_id": uuid4(),
        "data_as_of": datetime.now(UTC),
    }
    defaults.update(overrides)
    return CandidateWorkflowInput(**defaults)  # type: ignore[arg-type]


def _exploration_input(**overrides: object) -> ExplorationWorkflowInput:
    defaults = {
        "exploration_run_id": uuid4(),
        "organization_id": uuid4(),
        "data_as_of": datetime.now(UTC),
    }
    defaults.update(overrides)
    return ExplorationWorkflowInput(**defaults)  # type: ignore[arg-type]


def _runtime(**overrides: AsyncMock) -> CallbackCandidateActivityRuntime:
    defaults: dict[str, AsyncMock] = {
        name: AsyncMock()
        for name in [
            "resolve_identity",
            "discover_sources",
            "persist_sources",
            "validate_supplied_source",
            "evaluate_readiness",
            "validate_sources",
            "collect_documents",
            "ingest_financials",
            "validate_financials",
            "analyze_fundamentals",
            "analyze_risk",
            "build_committee_pack",
            "complete_run",
            "screen_universe",
            "explore_shortlist",
            "persist_suggestions",
            "expire_suggestions",
            "restrict_list",
        ]
    }
    defaults.update(overrides)
    return CallbackCandidateActivityRuntime(**defaults)


class TestFrozenDataclasses:
    def test_candidate_workflow_input_is_frozen(self) -> None:
        cmd = _workflow_input()
        with pytest.raises(AttributeError):
            cmd.candidate_id = uuid4()  # type: ignore[misc]

    def test_candidate_checkpoint_is_frozen(self) -> None:
        cp = CandidateCheckpoint(
            candidate_id=uuid4(),
            stage="resolve_identity",
            blocked=False,
            decision="approved",
            reason="ok",
        )
        with pytest.raises(AttributeError):
            cp.stage = "other"  # type: ignore[misc]

    def test_candidate_workflow_result_is_frozen(self) -> None:
        r = CandidateWorkflowResult(
            candidate_id=uuid4(),
            analysis_run_id=uuid4(),
            status="completed",
            decision="approved",
            reason="ok",
            blocker_codes=(),
        )
        assert r.status == "completed"

    def test_source_discovery_checkpoint_is_frozen(self) -> None:
        cmd = _workflow_input()
        cp = SourceDiscoveryCheckpoint(command=cmd, output={})
        with pytest.raises(AttributeError):
            cp.output = {}  # type: ignore[misc]

    def test_candidate_source_validation_input_is_frozen(self) -> None:
        v = CandidateSourceValidationInput(
            candidate_id=uuid4(),
            source_id=uuid4(),
            organization_id=uuid4(),
        )
        assert v.candidate_id is not None

    def test_candidate_source_validation_result_is_frozen(self) -> None:
        r = CandidateSourceValidationResult(
            candidate_id=uuid4(),
            source_id=uuid4(),
            status="verified",
            official=True,
            reason="cross-source match",
        )
        assert r.official is True

    def test_exploration_workflow_input_is_frozen(self) -> None:
        e = _exploration_input()
        with pytest.raises(AttributeError):
            e.exploration_run_id = uuid4()  # type: ignore[misc]

    def test_scheduled_exploration_input_is_frozen(self) -> None:
        s = ScheduledExplorationInput(
            organization_id=uuid4(),
            strategy_codes=("value", "quality"),
            minimum_liquidity="100000",
            maximum_suggestions=10,
        )
        assert len(s.strategy_codes) == 2

    def test_exploration_shortlist_is_frozen(self) -> None:
        cmd = _exploration_input()
        sl = ExplorationShortlist(
            command=cmd,
            securities=(),
            universe_size=100,
            eligible_size=50,
        )
        assert sl.eligible_size == 50

    def test_exploration_findings_is_frozen(self) -> None:
        cmd = _exploration_input()
        sl = ExplorationShortlist(command=cmd, securities=(), universe_size=100, eligible_size=50)
        f = ExplorationFindings(shortlist=sl, suggestions=())
        assert len(f.suggestions) == 0

    def test_exploration_workflow_result_is_frozen(self) -> None:
        r = ExplorationWorkflowResult(
            exploration_run_id=uuid4(),
            status="completed",
            universe_size=100,
            eligible_size=50,
            suggestion_count=5,
        )
        assert r.suggestion_count == 5


class TestCallbackCandidateActivityRuntime:
    @pytest.mark.asyncio
    async def test_resolve_identity_delegates_to_callback(self) -> None:
        expected = CandidateCheckpoint(
            candidate_id=uuid4(), stage="resolve_identity", blocked=False, decision="approved", reason="ok"
        )
        cb = AsyncMock(return_value=expected)
        rt = _runtime(resolve_identity=cb)
        cmd = _workflow_input()
        result = await rt.resolve_candidate_identity(cmd)
        cb.assert_awaited_once_with(cmd)
        assert result is expected

    @pytest.mark.asyncio
    async def test_discover_sources_delegates_to_callback(self) -> None:
        cmd = _workflow_input()
        expected = SourceDiscoveryCheckpoint(command=cmd, output={"sources": []})
        cb = AsyncMock(return_value=expected)
        rt = _runtime(discover_sources=cb)
        result = await rt.discover_candidate_sources(cmd)
        cb.assert_awaited_once_with(cmd)
        assert result is expected

    @pytest.mark.asyncio
    async def test_persist_sources_delegates_to_callback(self) -> None:
        cmd = _workflow_input()
        cp = SourceDiscoveryCheckpoint(command=cmd, output={})
        cb = AsyncMock()
        rt = _runtime(persist_sources=cb)
        await rt.persist_candidate_sources_and_gaps(cp)
        cb.assert_awaited_once_with(cp)

    @pytest.mark.asyncio
    async def test_validate_supplied_source_delegates_to_callback(self) -> None:
        validation_cmd = CandidateSourceValidationInput(
            candidate_id=uuid4(), source_id=uuid4(), organization_id=uuid4()
        )
        expected = CandidateSourceValidationResult(
            candidate_id=validation_cmd.candidate_id,
            source_id=validation_cmd.source_id,
            status="verified",
            official=True,
            reason="ok",
        )
        cb = AsyncMock(return_value=expected)
        rt = _runtime(validate_supplied_source=cb)
        result = await rt.validate_supplied_candidate_source(validation_cmd)
        cb.assert_awaited_once_with(validation_cmd)
        assert result is expected

    @pytest.mark.asyncio
    async def test_evaluate_readiness_delegates_to_callback(self) -> None:
        cmd = _workflow_input()
        expected = CandidateCheckpoint(
            candidate_id=cmd.candidate_id, stage="readiness", blocked=False, decision="ready", reason="all gaps closed"
        )
        cb = AsyncMock(return_value=expected)
        rt = _runtime(evaluate_readiness=cb)
        result = await rt.evaluate_candidate_readiness(cmd)
        cb.assert_awaited_once_with(cmd)
        assert result is expected

    @pytest.mark.asyncio
    async def test_validate_sources_delegates_to_callback(self) -> None:
        cmd = _workflow_input()
        expected = CandidateCheckpoint(
            candidate_id=cmd.candidate_id, stage="validate_sources", blocked=False, decision="valid", reason="ok"
        )
        cb = AsyncMock(return_value=expected)
        rt = _runtime(validate_sources=cb)
        result = await rt.validate_candidate_sources(cmd)
        cb.assert_awaited_once_with(cmd)
        assert result is expected

    @pytest.mark.asyncio
    async def test_collect_documents_delegates_to_callback(self) -> None:
        cmd = _workflow_input()
        expected = CandidateCheckpoint(
            candidate_id=cmd.candidate_id, stage="collect_documents", blocked=False, decision="collected", reason="ok"
        )
        cb = AsyncMock(return_value=expected)
        rt = _runtime(collect_documents=cb)
        result = await rt.collect_candidate_documents(cmd)
        cb.assert_awaited_once_with(cmd)
        assert result is expected

    @pytest.mark.asyncio
    async def test_ingest_financials_delegates_to_callback(self) -> None:
        cmd = _workflow_input()
        expected = CandidateCheckpoint(
            candidate_id=cmd.candidate_id, stage="ingest_financials", blocked=False, decision="ingested", reason="ok"
        )
        cb = AsyncMock(return_value=expected)
        rt = _runtime(ingest_financials=cb)
        result = await rt.ingest_candidate_financial_data(cmd)
        cb.assert_awaited_once_with(cmd)
        assert result is expected

    @pytest.mark.asyncio
    async def test_validate_financials_delegates_to_callback(self) -> None:
        cmd = _workflow_input()
        expected = CandidateCheckpoint(
            candidate_id=cmd.candidate_id, stage="validate_financials", blocked=False, decision="valid", reason="ok"
        )
        cb = AsyncMock(return_value=expected)
        rt = _runtime(validate_financials=cb)
        result = await rt.validate_candidate_financial_data(cmd)
        cb.assert_awaited_once_with(cmd)
        assert result is expected

    @pytest.mark.asyncio
    async def test_analyze_fundamentals_delegates_to_callback(self) -> None:
        cmd = _workflow_input()
        expected = CandidateCheckpoint(
            candidate_id=cmd.candidate_id, stage="fundamentals", blocked=False, decision="approved", reason="ok"
        )
        cb = AsyncMock(return_value=expected)
        rt = _runtime(analyze_fundamentals=cb)
        result = await rt.run_candidate_fundamental_analysis(cmd)
        cb.assert_awaited_once_with(cmd)
        assert result is expected

    @pytest.mark.asyncio
    async def test_analyze_risk_delegates_to_callback(self) -> None:
        cmd = _workflow_input()
        expected = CandidateCheckpoint(
            candidate_id=cmd.candidate_id, stage="risk", blocked=False, decision="approved", reason="ok"
        )
        cb = AsyncMock(return_value=expected)
        rt = _runtime(analyze_risk=cb)
        result = await rt.run_candidate_risk_analysis(cmd)
        cb.assert_awaited_once_with(cmd)
        assert result is expected

    @pytest.mark.asyncio
    async def test_build_committee_pack_delegates_to_callback(self) -> None:
        cmd = _workflow_input()
        expected = CandidateCheckpoint(
            candidate_id=cmd.candidate_id, stage="committee_pack", blocked=False, decision="ready", reason="ok"
        )
        cb = AsyncMock(return_value=expected)
        rt = _runtime(build_committee_pack=cb)
        result = await rt.create_committee_pack(cmd)
        cb.assert_awaited_once_with(cmd)
        assert result is expected

    @pytest.mark.asyncio
    async def test_complete_run_delegates_to_callback(self) -> None:
        cmd = _workflow_input()
        cp = CandidateCheckpoint(
            candidate_id=cmd.candidate_id, stage="done", blocked=False, decision="approved", reason="ok"
        )
        expected = CandidateWorkflowResult(
            candidate_id=cmd.candidate_id,
            analysis_run_id=cmd.analysis_run_id,
            status="completed",
            decision="approved",
            reason="ok",
            blocker_codes=(),
        )
        cb = AsyncMock(return_value=expected)
        rt = _runtime(complete_run=cb)
        result = await rt.complete_candidate_analysis_run(cmd, cp)
        cb.assert_awaited_once_with(cmd, cp)
        assert result is expected

    @pytest.mark.asyncio
    async def test_screen_universe_delegates_to_callback(self) -> None:
        cmd = _exploration_input()
        expected = ExplorationShortlist(command=cmd, securities=(), universe_size=100, eligible_size=50)
        cb = AsyncMock(return_value=expected)
        rt = _runtime(screen_universe=cb)
        result = await rt.screen_equity_universe(cmd)
        cb.assert_awaited_once_with(cmd)
        assert result is expected

    @pytest.mark.asyncio
    async def test_explore_shortlist_delegates_to_callback(self) -> None:
        cmd = _exploration_input()
        sl = ExplorationShortlist(command=cmd, securities=(), universe_size=100, eligible_size=50)
        expected = ExplorationFindings(shortlist=sl, suggestions=())
        cb = AsyncMock(return_value=expected)
        rt = _runtime(explore_shortlist=cb)
        result = await rt.run_equity_explorer_agent(sl)
        cb.assert_awaited_once_with(sl)
        assert result is expected

    @pytest.mark.asyncio
    async def test_persist_suggestions_delegates_to_callback(self) -> None:
        cmd = _exploration_input()
        sl = ExplorationShortlist(command=cmd, securities=(), universe_size=100, eligible_size=50)
        findings = ExplorationFindings(shortlist=sl, suggestions=())
        expected = ExplorationWorkflowResult(
            exploration_run_id=cmd.exploration_run_id,
            status="completed",
            universe_size=100,
            eligible_size=50,
            suggestion_count=0,
        )
        cb = AsyncMock(return_value=expected)
        rt = _runtime(persist_suggestions=cb)
        result = await rt.persist_exploration_suggestions(findings)
        cb.assert_awaited_once_with(findings)
        assert result is expected

    @pytest.mark.asyncio
    async def test_expire_suggestions_delegates_to_callback(self) -> None:
        cb = AsyncMock(return_value=3)
        rt = _runtime(expire_suggestions=cb)
        result = await rt.expire_stale_suggestions()
        cb.assert_awaited_once_with()
        assert result == 3

    @pytest.mark.asyncio
    async def test_restrict_list_delegates_to_callback(self) -> None:
        ids = [uuid4(), uuid4()]
        cb = AsyncMock(return_value=2)
        rt = _runtime(restrict_list=cb)
        result = await rt.apply_restricted_list_block(ids)
        cb.assert_awaited_once_with(ids)
        assert result == 2


class TestModuleSingleton:
    def test_configure_and_reset_lifecycle(self) -> None:
        reset_candidate_activity_runtime_for_tests()
        assert not candidate_activity_runtime_configured()
        rt = _runtime()
        configure_candidate_activity_runtime(rt)
        assert candidate_activity_runtime_configured()
        with pytest.raises(RuntimeError, match="already configured"):
            configure_candidate_activity_runtime(rt)
        reset_candidate_activity_runtime_for_tests()
        assert not candidate_activity_runtime_configured()

    def test_runtime_raises_when_not_configured(self) -> None:
        reset_candidate_activity_runtime_for_tests()
        assert not candidate_activity_runtime_configured()
