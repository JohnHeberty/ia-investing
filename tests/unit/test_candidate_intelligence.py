from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from ia_investing.candidate_intelligence.contracts import (
    CandidateCreateRequest,
    CandidateReanalysisRequest,
    CandidateSourceCreateRequest,
)
from ia_investing.candidate_intelligence.enums import (
    AnalysisTrigger,
    CandidateStatus,
    SourceKind,
    SourceStatus,
    VerificationMethod,
)
from ia_investing.candidate_intelligence.models import (
    CandidateIdentity,
    CandidateSource,
    InvestmentCandidate,
    normalize_url,
    utcnow,
)
from ia_investing.candidate_intelligence.readiness import ReadinessEvaluator
from ia_investing.candidate_intelligence.repositories import InMemoryCandidateRepository
from ia_investing.candidate_intelligence.services import CandidateService
from ia_investing.candidate_intelligence.state_machine import can_transition, require_transition


class FakeWorkflowStarter:
    def __init__(self) -> None:
        self.candidate_calls: list[dict[str, object]] = []

    async def start_candidate_analysis(self, **kwargs):
        self.candidate_calls.append(kwargs)
        return f"candidate-{kwargs['candidate_id']}-{kwargs['analysis_run_id']}"

    async def start_exploration(self, *, exploration_run_id):
        return f"exploration-{exploration_run_id}"


def verified_source(candidate_id, kind: SourceKind) -> CandidateSource:
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


def test_normalize_url_removes_fragment_and_credentials_are_rejected() -> None:
    assert normalize_url("HTTPS://Example.COM/reports#latest") == "https://example.com/reports"
    with pytest.raises(ValueError, match="credentials"):
        normalize_url("https://user:secret@example.com/reports")


def test_agent_inference_cannot_confirm_official_source() -> None:
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
            discovered_by="agent:test",
            created_at=utcnow(),
        )


def test_readiness_blocks_when_mandatory_sources_are_missing() -> None:
    candidate = InvestmentCandidate.create_manual(
        organization_id=uuid4(),
        identity=CandidateIdentity(ticker="wege3"),
        actor_id="john",
    )
    evaluator = ReadinessEvaluator()
    gaps = evaluator.derive_source_gaps(candidate_id=candidate.id, sources=())
    readiness = evaluator.evaluate(
        sources=(),
        open_gaps=gaps,
        identity_resolved=False,
    )
    assert not readiness.ready_for_document_collection
    assert "identity" in readiness.blocker_codes
    assert "investor_relations" in readiness.blocker_codes
    assert SourceKind.FINANCIAL_REPORTS in readiness.missing_source_kinds


def test_readiness_releases_source_blockers_only_after_verification() -> None:
    candidate_id = uuid4()
    evaluator = ReadinessEvaluator()
    required = (
        SourceKind.INVESTOR_RELATIONS,
        SourceKind.FINANCIAL_REPORTS,
        SourceKind.CVM_PROFILE,
        SourceKind.CVM_FILINGS,
        SourceKind.B3_LISTING,
    )
    sources = tuple(verified_source(candidate_id, kind) for kind in required)
    gaps = evaluator.derive_source_gaps(candidate_id=candidate_id, sources=sources)
    readiness = evaluator.evaluate(
        sources=sources,
        open_gaps=gaps,
        identity_resolved=True,
    )
    assert not readiness.blocker_codes
    assert readiness.ready_for_document_collection


@pytest.mark.asyncio
async def test_manual_registration_creates_initial_run_and_blocking_gaps() -> None:
    repository = InMemoryCandidateRepository()
    workflows = FakeWorkflowStarter()
    service = CandidateService(repository=repository, workflow_starter=workflows)
    candidate, run, workflow_id = await service.create_manual(
        organization_id=uuid4(),
        actor_id="john",
        request=CandidateCreateRequest(ticker="PETR4", rationale="Teste de oportunidade"),
        data_as_of=datetime.now(UTC),
    )
    assert candidate.status is CandidateStatus.IDENTITY_RESOLUTION
    assert candidate.analysis_runs == (run,)
    assert candidate.blocking_gaps
    assert workflow_id.startswith("candidate-")
    assert len(workflows.candidate_calls) == 1


@pytest.mark.asyncio
async def test_user_supplied_source_remains_pending_validation() -> None:
    repository = InMemoryCandidateRepository()
    workflows = FakeWorkflowStarter()
    service = CandidateService(repository=repository, workflow_starter=workflows)
    candidate, _, _ = await service.create_manual(
        organization_id=uuid4(),
        actor_id="john",
        request=CandidateCreateRequest(ticker="VALE3"),
        data_as_of=datetime.now(UTC),
    )
    updated = await service.add_user_source(
        candidate_id=candidate.id,
        actor_id="john",
        request=CandidateSourceCreateRequest(
            kind=SourceKind.FINANCIAL_REPORTS,
            url="https://ri.example.com/resultados",
            notes="URL fornecida para validação",
        ),
        expected_version=candidate.lock_version,
    )
    source = updated.sources[-1]
    assert source.status is SourceStatus.DISCOVERED
    assert source.verification_method is VerificationMethod.USER_CONFIRMED
    assert source.official is False
    assert any(gap.code == "financial_reports" and gap.status.value == "open" for gap in updated.gaps)


@pytest.mark.asyncio
async def test_reanalysis_refuses_unresolved_blockers() -> None:
    repository = InMemoryCandidateRepository()
    workflows = FakeWorkflowStarter()
    service = CandidateService(repository=repository, workflow_starter=workflows)
    candidate, _, _ = await service.create_manual(
        organization_id=uuid4(),
        actor_id="john",
        request=CandidateCreateRequest(ticker="ITUB4"),
        data_as_of=datetime.now(UTC),
    )
    with pytest.raises(ValueError, match="blocking gaps"):
        await service.request_reanalysis(
            candidate_id=candidate.id,
            actor_id="john",
            request=CandidateReanalysisRequest(
                trigger=AnalysisTrigger.USER_COMPLETION,
                data_as_of=datetime.now(UTC),
            ),
            expected_version=candidate.lock_version,
        )


def test_state_machine_disallows_skipping_research_and_risk() -> None:
    assert can_transition(CandidateStatus.SOURCE_DISCOVERY, CandidateStatus.SOURCE_VALIDATION)
    assert not can_transition(CandidateStatus.SOURCE_DISCOVERY, CandidateStatus.APPROVED)
    with pytest.raises(ValueError, match="invalid candidate transition"):
        require_transition(CandidateStatus.SOURCE_DISCOVERY, CandidateStatus.APPROVED)
