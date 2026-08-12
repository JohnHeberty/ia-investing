from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from ia_investing.candidate_intelligence.contracts import CompanySourceDiscoveryOutput, SourceDiscoveryFinding
from ia_investing.candidate_intelligence.enums import (
    CandidateDecision,
    CandidateStatus,
    SourceKind,
    SourceStatus,
    VerificationMethod,
)
from ia_investing.candidate_intelligence.models import (
    CandidateIdentity,
    InvestmentCandidate,
)
from ia_investing.candidate_intelligence.repositories import InMemoryCandidateRepository
from ia_investing.candidate_intelligence.workflow import (
    CandidateAnalysisOrchestrator,
    CollectionResult,
    CommitteeResult,
    DataQualityResult,
    IdentityResolutionResult,
    ResearchResult,
    RiskResult,
)


def _make_candidate(status: CandidateStatus = CandidateStatus.IDENTITY_RESOLUTION) -> InvestmentCandidate:
    c = InvestmentCandidate.create_manual(
        organization_id=uuid4(),
        identity=CandidateIdentity(ticker="PETR4"),
        actor_id="test",
    )
    return replace(c, status=status)


def _identity_result(resolved: bool = True, confidence: Decimal = Decimal("0.95")) -> IdentityResolutionResult:
    return IdentityResolutionResult(
        resolved=resolved,
        legal_name="Petrobras",
        cnpj="33.000.167/0001-01",
        cvm_code="12345",
        issuer_id=uuid4(),
        instrument_id=uuid4(),
        confidence=confidence,
    )


def _discovery_output() -> CompanySourceDiscoveryOutput:
    return CompanySourceDiscoveryOutput(
        identity_confidence=Decimal("0.95"),
        resolved_legal_name="Petrobras",
        sources=(
            SourceDiscoveryFinding(
                kind=SourceKind.INVESTOR_RELATIONS,
                url="https://ri.petrobras.com.br/",
                status=SourceStatus.VERIFIED,
                verification_method=VerificationMethod.CROSS_SOURCE_MATCH,
                confidence=Decimal("0.95"),
                official=True,
            ),
            SourceDiscoveryFinding(
                kind=SourceKind.FINANCIAL_REPORTS,
                url="https://ri.petrobras.com.br/resultados/",
                status=SourceStatus.VERIFIED,
                verification_method=VerificationMethod.CROSS_SOURCE_MATCH,
                confidence=Decimal("0.90"),
                official=True,
            ),
            SourceDiscoveryFinding(
                kind=SourceKind.CVM_PROFILE,
                url="https://www.gov.br/cvm/pt-br/",
                status=SourceStatus.VERIFIED,
                verification_method=VerificationMethod.OFFICIAL_REGISTRY_LINK,
                confidence=Decimal("0.98"),
                official=True,
            ),
            SourceDiscoveryFinding(
                kind=SourceKind.CVM_FILINGS,
                url="https://www.gov.br/cvm/pt-br/documents/",
                status=SourceStatus.VERIFIED,
                verification_method=VerificationMethod.OFFICIAL_REGISTRY_LINK,
                confidence=Decimal("0.98"),
                official=True,
            ),
            SourceDiscoveryFinding(
                kind=SourceKind.B3_LISTING,
                url="https://www.b3.com.br/petr4/",
                status=SourceStatus.VERIFIED,
                verification_method=VerificationMethod.OFFICIAL_REGISTRY_LINK,
                confidence=Decimal("0.98"),
                official=True,
            ),
        ),
        gaps=(),
        summary="All sources found",
    )


def _collection_result(success: bool = True, latest_period: bool = True) -> CollectionResult:
    return CollectionResult(
        success=success,
        document_count=10 if success else 0,
        latest_period_found=latest_period,
    )


def _quality_result(promotable: bool = True) -> DataQualityResult:
    return DataQualityResult(
        promotable=promotable,
        completeness_score=Decimal("0.95"),
        reconciliation_score=Decimal("0.90"),
        blocker_codes=() if promotable else ("missing_revenue",),
    )


def _research_result(
    completed: bool = True,
    recommendation: CandidateDecision = CandidateDecision.APPROVE,
) -> ResearchResult:
    return ResearchResult(
        completed=completed,
        research_case_id=uuid4(),
        thesis_version_id=uuid4(),
        evidence_coverage=Decimal("0.95"),
        recommendation=recommendation,
    )


def _risk_result(eligible: bool = True) -> RiskResult:
    return RiskResult(
        completed=True,
        eligible=eligible,
        risk_snapshot_id=uuid4(),
    )


def _committee_result(decision: CandidateDecision = CandidateDecision.APPROVE) -> CommitteeResult:
    return CommitteeResult(
        decision=decision,
        committee_decision_id=uuid4(),
        reason="Strong fundamentals",
    )


def _build_orchestrator(
    *,
    identity: IdentityResolutionResult | None = None,
    discovery: CompanySourceDiscoveryOutput | None = None,
    collection: CollectionResult | None = None,
    quality: DataQualityResult | None = None,
    research: ResearchResult | None = None,
    risk: RiskResult | None = None,
    committee: CommitteeResult | None = None,
) -> tuple[CandidateAnalysisOrchestrator, InMemoryCandidateRepository]:
    repo = InMemoryCandidateRepository()

    identity_resolver = AsyncMock()
    identity_resolver.resolve = AsyncMock(return_value=identity or _identity_result())

    source_discovery = AsyncMock()
    source_discovery.discover = AsyncMock(return_value=discovery or _discovery_output())

    document_collector = AsyncMock()
    document_collector.collect = AsyncMock(return_value=collection or _collection_result())

    data_validator = AsyncMock()
    data_validator.validate = AsyncMock(return_value=quality or _quality_result())

    research_pipeline = AsyncMock()
    research_pipeline.analyze = AsyncMock(return_value=research or _research_result())

    risk_pipeline = AsyncMock()
    risk_pipeline.analyze = AsyncMock(return_value=risk or _risk_result())

    committee_gw = AsyncMock()
    committee_gw.review = AsyncMock(return_value=committee or _committee_result())

    orch = CandidateAnalysisOrchestrator(
        repository=repo,
        identity_resolver=identity_resolver,
        source_discovery=source_discovery,
        document_collector=document_collector,
        data_validator=data_validator,
        research_pipeline=research_pipeline,
        risk_pipeline=risk_pipeline,
        committee=committee_gw,
    )
    return orch, repo


class TestOrchestratorHappyPath:
    @pytest.mark.asyncio
    async def test_full_happy_path_approve(self) -> None:
        orch, repo = _build_orchestrator()
        candidate = _make_candidate()
        await repo.add(candidate)
        result = await orch.run(candidate_id=candidate.id, data_as_of=datetime.now(UTC))
        assert result.decision is CandidateDecision.APPROVE
        assert result.status is CandidateStatus.APPROVED

    @pytest.mark.asyncio
    async def test_full_happy_path_reject_by_committee(self) -> None:
        orch, repo = _build_orchestrator(committee=_committee_result(CandidateDecision.REJECT))
        candidate = _make_candidate()
        await repo.add(candidate)
        result = await orch.run(candidate_id=candidate.id, data_as_of=datetime.now(UTC))
        assert result.decision is CandidateDecision.REJECT
        assert result.status is CandidateStatus.REJECTED

    @pytest.mark.asyncio
    async def test_full_happy_path_watchlist(self) -> None:
        orch, repo = _build_orchestrator(committee=_committee_result(CandidateDecision.WATCHLIST))
        candidate = _make_candidate()
        await repo.add(candidate)
        result = await orch.run(candidate_id=candidate.id, data_as_of=datetime.now(UTC))
        assert result.decision is CandidateDecision.WATCHLIST
        assert result.status is CandidateStatus.WATCHLIST


class TestOrchestratorIdentityFailure:
    @pytest.mark.asyncio
    async def test_unresolved_identity_goes_to_awaiting_user_input(self) -> None:
        orch, repo = _build_orchestrator(
            identity=IdentityResolutionResult(
                resolved=False,
                legal_name=None,
                cnpj=None,
                cvm_code=None,
                issuer_id=None,
                instrument_id=None,
                confidence=Decimal("0.50"),
            )
        )
        candidate = _make_candidate()
        await repo.add(candidate)
        result = await orch.run(candidate_id=candidate.id, data_as_of=datetime.now(UTC))
        assert result.status is CandidateStatus.AWAITING_USER_INPUT
        assert result.decision is CandidateDecision.PENDING
        assert "identity_resolution" in result.blocker_codes

    @pytest.mark.asyncio
    async def test_low_confidence_identity_goes_to_awaiting_user_input(self) -> None:
        orch, repo = _build_orchestrator(identity=_identity_result(confidence=Decimal("0.70")))
        candidate = _make_candidate()
        await repo.add(candidate)
        result = await orch.run(candidate_id=candidate.id, data_as_of=datetime.now(UTC))
        assert result.status is CandidateStatus.AWAITING_USER_INPUT


class TestOrchestratorDocumentCollectionFailure:
    @pytest.mark.asyncio
    async def test_collection_failure_goes_to_awaiting_user_input(self) -> None:
        orch, repo = _build_orchestrator(collection=_collection_result(success=False))
        candidate = _make_candidate()
        await repo.add(candidate)
        result = await orch.run(candidate_id=candidate.id, data_as_of=datetime.now(UTC))
        assert result.status is CandidateStatus.AWAITING_USER_INPUT
        assert result.decision is CandidateDecision.PENDING


class TestOrchestratorDataQualityFailure:
    @pytest.mark.asyncio
    async def test_quality_not_promotable_goes_to_awaiting_user_input(self) -> None:
        orch, repo = _build_orchestrator(quality=_quality_result(promotable=False))
        candidate = _make_candidate()
        await repo.add(candidate)
        result = await orch.run(candidate_id=candidate.id, data_as_of=datetime.now(UTC))
        assert result.status is CandidateStatus.AWAITING_USER_INPUT
        assert result.decision is CandidateDecision.PENDING


class TestOrchestratorResearchFailure:
    @pytest.mark.asyncio
    async def test_incomplete_research_goes_to_awaiting_user_input(self) -> None:
        orch, repo = _build_orchestrator(
            research=ResearchResult(
                completed=False,
                research_case_id=None,
                thesis_version_id=None,
                evidence_coverage=Decimal("0.50"),
                recommendation=CandidateDecision.PENDING,
            )
        )
        candidate = _make_candidate()
        await repo.add(candidate)
        result = await orch.run(candidate_id=candidate.id, data_as_of=datetime.now(UTC))
        assert result.status is CandidateStatus.AWAITING_USER_INPUT

    @pytest.mark.asyncio
    async def test_low_evidence_coverage_goes_to_awaiting_user_input(self) -> None:
        orch, repo = _build_orchestrator(
            research=ResearchResult(
                completed=True,
                research_case_id=uuid4(),
                thesis_version_id=uuid4(),
                evidence_coverage=Decimal("0.70"),
                recommendation=CandidateDecision.APPROVE,
            )
        )
        candidate = _make_candidate()
        await repo.add(candidate)
        result = await orch.run(candidate_id=candidate.id, data_as_of=datetime.now(UTC))
        assert result.status is CandidateStatus.AWAITING_USER_INPUT

    @pytest.mark.asyncio
    async def test_research_reject_causes_direct_reject(self) -> None:
        orch, repo = _build_orchestrator(research=_research_result(recommendation=CandidateDecision.REJECT))
        candidate = _make_candidate()
        await repo.add(candidate)
        result = await orch.run(candidate_id=candidate.id, data_as_of=datetime.now(UTC))
        assert result.status is CandidateStatus.REJECTED
        assert result.decision is CandidateDecision.REJECT


class TestOrchestratorRiskFailure:
    @pytest.mark.asyncio
    async def test_risk_ineligible_rejects(self) -> None:
        orch, repo = _build_orchestrator(risk=_risk_result(eligible=False))
        candidate = _make_candidate()
        await repo.add(candidate)
        result = await orch.run(candidate_id=candidate.id, data_as_of=datetime.now(UTC))
        assert result.status is CandidateStatus.REJECTED
        assert result.decision is CandidateDecision.REJECT

    @pytest.mark.asyncio
    async def test_risk_hard_limit_breach_rejects(self) -> None:
        orch, repo = _build_orchestrator(
            risk=RiskResult(
                completed=True,
                eligible=True,
                risk_snapshot_id=uuid4(),
                hard_limit_breaches=("concentration_limit",),
            )
        )
        candidate = _make_candidate()
        await repo.add(candidate)
        result = await orch.run(candidate_id=candidate.id, data_as_of=datetime.now(UTC))
        assert result.status is CandidateStatus.REJECTED


class TestOrchestratorAgentInferenceDemotion:
    @pytest.mark.asyncio
    async def test_agent_inference_source_demoted_to_discovered(self) -> None:
        """Agent inference source that arrives as DISCOVERED stays DISCOVERED with official=False."""
        discovery = CompanySourceDiscoveryOutput(
            identity_confidence=Decimal("0.95"),
            sources=(
                SourceDiscoveryFinding(
                    kind=SourceKind.INVESTOR_RELATIONS,
                    url="https://example.com/ri/",
                    status=SourceStatus.DISCOVERED,
                    verification_method=VerificationMethod.AGENT_INFERENCE,
                    confidence=Decimal("0.90"),
                    official=False,
                ),
                SourceDiscoveryFinding(
                    kind=SourceKind.FINANCIAL_REPORTS,
                    url="https://example.com/resultados/",
                    status=SourceStatus.VERIFIED,
                    verification_method=VerificationMethod.CROSS_SOURCE_MATCH,
                    confidence=Decimal("0.90"),
                    official=True,
                ),
                SourceDiscoveryFinding(
                    kind=SourceKind.CVM_PROFILE,
                    url="https://gov.br/cvm/",
                    status=SourceStatus.VERIFIED,
                    verification_method=VerificationMethod.OFFICIAL_REGISTRY_LINK,
                    confidence=Decimal("0.98"),
                    official=True,
                ),
                SourceDiscoveryFinding(
                    kind=SourceKind.CVM_FILINGS,
                    url="https://gov.br/cvm/docs/",
                    status=SourceStatus.VERIFIED,
                    verification_method=VerificationMethod.OFFICIAL_REGISTRY_LINK,
                    confidence=Decimal("0.98"),
                    official=True,
                ),
                SourceDiscoveryFinding(
                    kind=SourceKind.B3_LISTING,
                    url="https://b3.com.br/petr4/",
                    status=SourceStatus.VERIFIED,
                    verification_method=VerificationMethod.OFFICIAL_REGISTRY_LINK,
                    confidence=Decimal("0.98"),
                    official=True,
                ),
            ),
            gaps=(),
            summary="Found",
        )
        orch, repo = _build_orchestrator(discovery=discovery)
        candidate = _make_candidate()
        await repo.add(candidate)
        await orch.run(candidate_id=candidate.id, data_as_of=datetime.now(UTC))
        loaded = await repo.get(candidate.id)
        agent_source = [s for s in loaded.sources if s.verification_method is VerificationMethod.AGENT_INFERENCE]
        assert len(agent_source) == 1
        assert agent_source[0].official is False
        assert agent_source[0].status is SourceStatus.DISCOVERED


class TestOrchestratorAllowIncomplete:
    @pytest.mark.asyncio
    async def test_allow_incomplete_skips_readiness_blockers(self) -> None:
        orch, repo = _build_orchestrator()
        candidate = _make_candidate()
        await repo.add(candidate)
        result = await orch.run(
            candidate_id=candidate.id,
            data_as_of=datetime.now(UTC),
            allow_incomplete=True,
        )
        # Should proceed even with missing sources
        assert result.decision is CandidateDecision.APPROVE
