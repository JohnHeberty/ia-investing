from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest

from ia_investing.candidate_intelligence.enums import (
    AnalysisRunStatus,
    AnalysisTrigger,
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
from ia_investing.candidate_intelligence.models import (
    AnalysisRun,
    CandidateGap,
    CandidateIdentity,
    CandidateSource,
    ExplorationRun,
    ExplorationSuggestion,
    InvestmentCandidate,
    normalize_ticker,
    normalize_url,
    utcnow,
)


class TestNormalizeTicker:
    def test_normalizes_to_uppercase(self) -> None:
        assert normalize_ticker("petr4") == "PETR4"

    def test_strips_whitespace(self) -> None:
        assert normalize_ticker("  PETR 4  ") == "PETR4"

    def test_allows_dots_and_hyphens(self) -> None:
        assert normalize_ticker("BR.WT") == "BR.WT"

    def test_rejects_empty_string(self) -> None:
        with pytest.raises(ValueError, match="between 1 and 24"):
            normalize_ticker("")

    def test_rejects_too_long(self) -> None:
        with pytest.raises(ValueError, match="between 1 and 24"):
            normalize_ticker("A" * 25)

    def test_rejects_unsupported_characters(self) -> None:
        with pytest.raises(ValueError, match="unsupported"):
            normalize_ticker("PETR@4")


class TestNormalizeUrl:
    def test_normalizes_to_lowercase(self) -> None:
        result = normalize_url("HTTPS://Example.COM/Reports")
        assert result == "https://example.com/Reports"

    def test_strips_fragment(self) -> None:
        result = normalize_url("https://example.com/reports#latest")
        assert "#" not in result

    def test_rejects_ftp(self) -> None:
        with pytest.raises(ValueError, match="http or https"):
            normalize_url("ftp://example.com/file")

    def test_rejects_localhost(self) -> None:
        with pytest.raises(ValueError, match="local"):
            normalize_url("http://localhost/report")

    def test_rejects_credentials(self) -> None:
        with pytest.raises(ValueError, match="credentials"):
            normalize_url("https://user:pass@example.com/report")

    def test_preserves_port(self) -> None:
        result = normalize_url("https://example.com:8080/report")
        assert ":8080" in result

    def test_default_path_slash(self) -> None:
        result = normalize_url("https://example.com")
        assert result.endswith("/")


class TestCandidateIdentity:
    def test_creates_with_defaults(self) -> None:
        identity = CandidateIdentity(ticker="PETR4")
        assert identity.ticker == "PETR4"
        assert identity.exchange == "B3"

    def test_rejects_empty_exchange(self) -> None:
        with pytest.raises(ValueError, match="exchange"):
            CandidateIdentity(ticker="PETR4", exchange="  ")

    def test_normalizes_ticker(self) -> None:
        identity = CandidateIdentity(ticker="petr4")
        assert identity.ticker == "PETR4"


class TestCandidateSource:
    def test_validates_confidence_range(self) -> None:
        with pytest.raises(ValueError, match="confidence"):
            CandidateSource(
                id=uuid4(),
                candidate_id=uuid4(),
                kind=SourceKind.INVESTOR_RELATIONS,
                url="https://example.com/ri",
                status=SourceStatus.VERIFIED,
                verification_method=VerificationMethod.CROSS_SOURCE_MATCH,
                confidence=Decimal("1.5"),
                official=True,
                discovered_by="test",
                created_at=utcnow(),
                verified_at=utcnow(),
            )

    def test_verified_requires_verified_at(self) -> None:
        with pytest.raises(ValueError, match="verified_at"):
            CandidateSource(
                id=uuid4(),
                candidate_id=uuid4(),
                kind=SourceKind.INVESTOR_RELATIONS,
                url="https://example.com/ri",
                status=SourceStatus.VERIFIED,
                verification_method=VerificationMethod.CROSS_SOURCE_MATCH,
                confidence=Decimal("0.90"),
                official=True,
                discovered_by="test",
                created_at=utcnow(),
                verified_at=None,
            )

    def test_agent_inference_cannot_be_official(self) -> None:
        with pytest.raises(ValueError, match="agent inference"):
            CandidateSource(
                id=uuid4(),
                candidate_id=uuid4(),
                kind=SourceKind.INVESTOR_RELATIONS,
                url="https://example.com/ri",
                status=SourceStatus.DISCOVERED,
                verification_method=VerificationMethod.AGENT_INFERENCE,
                confidence=Decimal("0.70"),
                official=True,
                discovered_by="agent",
                created_at=utcnow(),
            )

    def test_user_supplied_classmethod(self) -> None:
        source = CandidateSource.user_supplied(
            candidate_id=uuid4(),
            kind=SourceKind.FINANCIAL_REPORTS,
            url="https://example.com/reports",
            actor_id="test",
        )
        assert source.status is SourceStatus.DISCOVERED
        assert source.verification_method is VerificationMethod.USER_CONFIRMED
        assert source.official is False


class TestCandidateGap:
    def test_blocks_progress_when_open_and_blocking(self) -> None:
        gap = CandidateGap(
            id=uuid4(),
            candidate_id=uuid4(),
            code="test",
            title="Test",
            description="",
            source_kind=None,
            level=RequirementLevel.BLOCKING,
            status=GapStatus.OPEN,
            requested_user_action="Fix",
            created_at=utcnow(),
        )
        assert gap.blocks_progress is True

    def test_does_not_block_when_resolved(self) -> None:
        gap = CandidateGap(
            id=uuid4(),
            candidate_id=uuid4(),
            code="test",
            title="Test",
            description="",
            source_kind=None,
            level=RequirementLevel.BLOCKING,
            status=GapStatus.RESOLVED,
            requested_user_action="Fix",
            created_at=utcnow(),
        )
        assert gap.blocks_progress is False

    def test_does_not_block_when_optional(self) -> None:
        gap = CandidateGap(
            id=uuid4(),
            candidate_id=uuid4(),
            code="test",
            title="Test",
            description="",
            source_kind=None,
            level=RequirementLevel.OPTIONAL,
            status=GapStatus.OPEN,
            requested_user_action="Fix",
            created_at=utcnow(),
        )
        assert gap.blocks_progress is False

    def test_resolve_marks_resolved(self) -> None:
        gap = CandidateGap(
            id=uuid4(),
            candidate_id=uuid4(),
            code="test",
            title="Test",
            description="",
            source_kind=None,
            level=RequirementLevel.BLOCKING,
            status=GapStatus.OPEN,
            requested_user_action="Fix",
            created_at=utcnow(),
        )
        resolved = gap.resolve("user1", "Fixed by providing URL")
        assert resolved.status is GapStatus.RESOLVED
        assert resolved.resolved_by == "user1"
        assert resolved.resolution_notes == "Fixed by providing URL"
        assert resolved.resolved_at is not None

    def test_resolve_rejects_already_resolved(self) -> None:
        gap = CandidateGap(
            id=uuid4(),
            candidate_id=uuid4(),
            code="test",
            title="Test",
            description="",
            source_kind=None,
            level=RequirementLevel.BLOCKING,
            status=GapStatus.RESOLVED,
            requested_user_action="Fix",
            created_at=utcnow(),
        )
        with pytest.raises(ValueError, match="only open"):
            gap.resolve("user1", "Notes")

    def test_resolve_rejects_empty_notes(self) -> None:
        gap = CandidateGap(
            id=uuid4(),
            candidate_id=uuid4(),
            code="test",
            title="Test",
            description="",
            source_kind=None,
            level=RequirementLevel.BLOCKING,
            status=GapStatus.OPEN,
            requested_user_action="Fix",
            created_at=utcnow(),
        )
        with pytest.raises(ValueError, match="notes"):
            gap.resolve("user1", "   ")


class TestInvestmentCandidate:
    def test_create_manual(self) -> None:
        c = InvestmentCandidate.create_manual(
            organization_id=uuid4(),
            identity=CandidateIdentity(ticker="PETR4"),
            actor_id="test",
        )
        assert c.origin is CandidateOrigin.MANUAL
        assert c.status is CandidateStatus.IDENTITY_RESOLUTION
        assert c.lock_version == 1

    def test_create_from_explorer(self) -> None:
        c = InvestmentCandidate.create_from_explorer(
            organization_id=uuid4(),
            identity=CandidateIdentity(ticker="VALE3"),
            actor_id="agent",
            suggestion_id=uuid4(),
            rationale="Strong value",
        )
        assert c.origin is CandidateOrigin.EXPLORER
        assert c.status is CandidateStatus.SUGGESTED
        assert c.exploration_suggestion_id is not None

    def test_open_gaps_property(self) -> None:
        c = InvestmentCandidate.create_manual(
            organization_id=uuid4(),
            identity=CandidateIdentity(ticker="PETR4"),
            actor_id="test",
        )
        open_gap = CandidateGap(
            id=uuid4(),
            candidate_id=c.id,
            code="test",
            title="Test",
            description="",
            source_kind=None,
            level=RequirementLevel.BLOCKING,
            status=GapStatus.OPEN,
            requested_user_action="Fix",
            created_at=utcnow(),
        )
        resolved_gap = CandidateGap(
            id=uuid4(),
            candidate_id=c.id,
            code="resolved",
            title="Resolved",
            description="",
            source_kind=None,
            level=RequirementLevel.BLOCKING,
            status=GapStatus.RESOLVED,
            requested_user_action="Fix",
            created_at=utcnow(),
        )
        c = c.with_gaps((open_gap, resolved_gap))
        assert len(c.open_gaps) == 1

    def test_blocking_gaps_property(self) -> None:
        c = InvestmentCandidate.create_manual(
            organization_id=uuid4(),
            identity=CandidateIdentity(ticker="PETR4"),
            actor_id="test",
        )
        blocking = CandidateGap(
            id=uuid4(),
            candidate_id=c.id,
            code="test",
            title="Test",
            description="",
            source_kind=None,
            level=RequirementLevel.BLOCKING,
            status=GapStatus.OPEN,
            requested_user_action="Fix",
            created_at=utcnow(),
        )
        optional = CandidateGap(
            id=uuid4(),
            candidate_id=c.id,
            code="opt",
            title="Opt",
            description="",
            source_kind=None,
            level=RequirementLevel.OPTIONAL,
            status=GapStatus.OPEN,
            requested_user_action="Fix",
            created_at=utcnow(),
        )
        c = c.with_gaps((blocking, optional))
        assert len(c.blocking_gaps) == 1

    def test_with_source_rejects_wrong_candidate(self) -> None:
        c = InvestmentCandidate.create_manual(
            organization_id=uuid4(),
            identity=CandidateIdentity(ticker="PETR4"),
            actor_id="test",
        )
        source = CandidateSource(
            id=uuid4(),
            candidate_id=uuid4(),  # wrong candidate
            kind=SourceKind.INVESTOR_RELATIONS,
            url="https://example.com/ri",
            status=SourceStatus.DISCOVERED,
            verification_method=VerificationMethod.USER_CONFIRMED,
            confidence=Decimal("0.70"),
            official=False,
            discovered_by="test",
            created_at=utcnow(),
        )
        with pytest.raises(ValueError, match="another candidate"):
            c.with_source(source)

    def test_with_gaps_rejects_wrong_candidate(self) -> None:
        c = InvestmentCandidate.create_manual(
            organization_id=uuid4(),
            identity=CandidateIdentity(ticker="PETR4"),
            actor_id="test",
        )
        gap = CandidateGap(
            id=uuid4(),
            candidate_id=uuid4(),  # wrong candidate
            code="test",
            title="Test",
            description="",
            source_kind=None,
            level=RequirementLevel.BLOCKING,
            status=GapStatus.OPEN,
            requested_user_action="Fix",
            created_at=utcnow(),
        )
        with pytest.raises(ValueError, match="another candidate"):
            c.with_gaps((gap,))

    def test_with_analysis_run_rejects_wrong_candidate(self) -> None:
        c = InvestmentCandidate.create_manual(
            organization_id=uuid4(),
            identity=CandidateIdentity(ticker="PETR4"),
            actor_id="test",
        )
        run = AnalysisRun(
            id=uuid4(),
            candidate_id=uuid4(),  # wrong
            run_number=1,
            trigger=AnalysisTrigger.INITIAL,
            status=AnalysisRunStatus.QUEUED,
            requested_by="test",
            requested_at=utcnow(),
            data_as_of=utcnow(),
        )
        with pytest.raises(ValueError, match="another candidate"):
            c.with_analysis_run(run)

    def test_with_analysis_run_appends(self) -> None:
        c = InvestmentCandidate.create_manual(
            organization_id=uuid4(),
            identity=CandidateIdentity(ticker="PETR4"),
            actor_id="test",
        )
        run = AnalysisRun(
            id=uuid4(),
            candidate_id=c.id,
            run_number=1,
            trigger=AnalysisTrigger.INITIAL,
            status=AnalysisRunStatus.QUEUED,
            requested_by="test",
            requested_at=utcnow(),
            data_as_of=utcnow(),
        )
        updated = c.with_analysis_run(run)
        assert len(updated.analysis_runs) == 1


class TestAnalysisRun:
    def test_start_from_queued(self) -> None:
        run = AnalysisRun(
            id=uuid4(),
            candidate_id=uuid4(),
            run_number=1,
            trigger=AnalysisTrigger.INITIAL,
            status=AnalysisRunStatus.QUEUED,
            requested_by="test",
            requested_at=utcnow(),
            data_as_of=utcnow(),
        )
        started = run.start("wf-123")
        assert started.status is AnalysisRunStatus.RUNNING
        assert started.workflow_id == "wf-123"
        assert started.started_at is not None

    def test_start_rejects_non_queued(self) -> None:
        run = AnalysisRun(
            id=uuid4(),
            candidate_id=uuid4(),
            run_number=1,
            trigger=AnalysisTrigger.INITIAL,
            status=AnalysisRunStatus.RUNNING,
            requested_by="test",
            requested_at=utcnow(),
            data_as_of=utcnow(),
        )
        with pytest.raises(ValueError, match="only queued"):
            run.start("wf-123")


class TestExplorationSuggestion:
    def test_validates_score_range(self) -> None:
        with pytest.raises(ValueError, match="between 0 and 1"):
            ExplorationSuggestion(
                id=uuid4(),
                exploration_run_id=uuid4(),
                organization_id=uuid4(),
                identity=CandidateIdentity(ticker="TEST"),
                status=SuggestionStatus.NEW,
                quantitative_score=Decimal("1.5"),
                data_coverage_score=Decimal("0.5"),
                source_discovery_score=Decimal("0.5"),
                rationale="Test",
                signals=(),
                risks=(),
                discovered_sources=(),
                created_at=utcnow(),
            )


class TestExplorationRun:
    def test_rejects_zero_max_suggestions(self) -> None:
        with pytest.raises(ValueError, match="between 1 and 100"):
            ExplorationRun(
                id=uuid4(),
                organization_id=uuid4(),
                status=ExplorationRunStatus.QUEUED,
                strategy_codes=("value",),
                requested_by="test",
                created_at=utcnow(),
                data_as_of=utcnow(),
                minimum_liquidity=Decimal("100000"),
                maximum_suggestions=0,
            )

    def test_rejects_negative_liquidity(self) -> None:
        with pytest.raises(ValueError, match="cannot be negative"):
            ExplorationRun(
                id=uuid4(),
                organization_id=uuid4(),
                status=ExplorationRunStatus.QUEUED,
                strategy_codes=("value",),
                requested_by="test",
                created_at=utcnow(),
                data_as_of=utcnow(),
                minimum_liquidity=Decimal("-1"),
                maximum_suggestions=10,
            )
