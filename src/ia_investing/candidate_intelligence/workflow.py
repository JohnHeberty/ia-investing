from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from decimal import Decimal
from typing import Protocol
from uuid import UUID, uuid4

from .contracts import CompanySourceDiscoveryOutput
from .enums import (
    CandidateDecision,
    CandidateStatus,
    GapStatus,
    RequirementLevel,
    SourceStatus,
    VerificationMethod,
)
from .models import CandidateGap, CandidateSource, InvestmentCandidate, utcnow
from .readiness import ReadinessEvaluator
from .repositories import CandidateRepository
from .state_machine import require_transition


@dataclass(frozen=True, slots=True)
class IdentityResolutionResult:
    resolved: bool
    legal_name: str | None
    cnpj: str | None
    cvm_code: str | None
    issuer_id: UUID | None
    instrument_id: UUID | None
    confidence: Decimal
    contradictions: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CollectionResult:
    success: bool
    document_count: int
    latest_period_found: bool
    source_object_ids: tuple[UUID, ...] = ()
    gaps: tuple[CandidateGap, ...] = ()
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class DataQualityResult:
    promotable: bool
    completeness_score: Decimal
    reconciliation_score: Decimal
    incident_ids: tuple[UUID, ...] = ()
    blocker_codes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ResearchResult:
    completed: bool
    research_case_id: UUID | None
    thesis_version_id: UUID | None
    evidence_coverage: Decimal
    recommendation: CandidateDecision
    blocker_codes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class RiskResult:
    completed: bool
    eligible: bool
    risk_snapshot_id: UUID | None
    hard_limit_breaches: tuple[str, ...] = ()
    conditions: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CommitteeResult:
    decision: CandidateDecision
    committee_decision_id: UUID | None
    reason: str
    conditions: tuple[str, ...] = ()
    missing_items: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CandidateWorkflowResult:
    candidate_id: UUID
    status: CandidateStatus
    decision: CandidateDecision
    reason: str
    blocker_codes: tuple[str, ...]


class IdentityResolver(Protocol):
    async def resolve(self, candidate: InvestmentCandidate, *, data_as_of: datetime) -> IdentityResolutionResult: ...


class SourceDiscoveryAgent(Protocol):
    async def discover(
        self,
        candidate: InvestmentCandidate,
        *,
        data_as_of: datetime,
    ) -> CompanySourceDiscoveryOutput: ...


class DocumentCollector(Protocol):
    async def collect(
        self,
        candidate: InvestmentCandidate,
        *,
        data_as_of: datetime,
    ) -> CollectionResult: ...


class FinancialDataValidator(Protocol):
    async def validate(
        self,
        candidate: InvestmentCandidate,
        collection: CollectionResult,
        *,
        data_as_of: datetime,
    ) -> DataQualityResult: ...


class ResearchPipeline(Protocol):
    async def analyze(
        self,
        candidate: InvestmentCandidate,
        *,
        data_as_of: datetime,
    ) -> ResearchResult: ...


class RiskPipeline(Protocol):
    async def analyze(
        self,
        candidate: InvestmentCandidate,
        research: ResearchResult,
        *,
        data_as_of: datetime,
    ) -> RiskResult: ...


class CommitteeGateway(Protocol):
    async def review(
        self,
        candidate: InvestmentCandidate,
        research: ResearchResult,
        risk: RiskResult,
        *,
        data_as_of: datetime,
    ) -> CommitteeResult: ...


class CandidateAnalysisOrchestrator:
    """Deterministic control flow for a candidate investigation.

    This class intentionally owns state progression. LLM agents only return typed findings.
    A Temporal workflow should call the equivalent activities and persist every checkpoint.
    """

    def __init__(
        self,
        *,
        repository: CandidateRepository,
        identity_resolver: IdentityResolver,
        source_discovery: SourceDiscoveryAgent,
        document_collector: DocumentCollector,
        data_validator: FinancialDataValidator,
        research_pipeline: ResearchPipeline,
        risk_pipeline: RiskPipeline,
        committee: CommitteeGateway,
        readiness: ReadinessEvaluator | None = None,
    ) -> None:
        self.repository = repository
        self.identity_resolver = identity_resolver
        self.source_discovery = source_discovery
        self.document_collector = document_collector
        self.data_validator = data_validator
        self.research_pipeline = research_pipeline
        self.risk_pipeline = risk_pipeline
        self.committee = committee
        self.readiness = readiness or ReadinessEvaluator()

    async def run(
        self,
        *,
        candidate_id: UUID,
        data_as_of: datetime,
        allow_incomplete: bool = False,
    ) -> CandidateWorkflowResult:
        candidate = await self.repository.get(candidate_id)
        candidate = await self._move(candidate, CandidateStatus.IDENTITY_RESOLUTION)

        identity = await self.identity_resolver.resolve(candidate, data_as_of=data_as_of)
        if not identity.resolved or identity.confidence < Decimal("0.80"):
            gap = CandidateGap(
                id=uuid4(),
                candidate_id=candidate.id,
                code="identity_resolution",
                title="Identidade do ativo não confirmada",
                description=(
                    "Não foi possível reconciliar ticker, emissor, CNPJ e cadastro CVM com confiança suficiente."
                ),
                source_kind=None,
                level=RequirementLevel.BLOCKING,
                status=GapStatus.OPEN,
                requested_user_action=(
                    "Informe CNPJ, código CVM ou o link oficial da companhia/listagem e solicite nova análise."
                ),
                created_at=utcnow(),
            )
            candidate = candidate.with_gaps((*candidate.gaps, gap))
            candidate = await self._move(candidate, CandidateStatus.AWAITING_USER_INPUT)
            return self._pending(candidate, "Identidade não confirmada")

        candidate = replace(
            candidate,
            identity=replace(
                candidate.identity,
                legal_name=identity.legal_name or candidate.identity.legal_name,
                cnpj=identity.cnpj or candidate.identity.cnpj,
                cvm_code=identity.cvm_code or candidate.identity.cvm_code,
                issuer_id=identity.issuer_id or candidate.identity.issuer_id,
                instrument_id=identity.instrument_id or candidate.identity.instrument_id,
            ),
            updated_at=utcnow(),
            lock_version=candidate.lock_version + 1,
        )
        candidate = await self._persist(candidate)
        candidate = await self._move(candidate, CandidateStatus.SOURCE_DISCOVERY)

        discovery = await self.source_discovery.discover(candidate, data_as_of=data_as_of)
        for finding in discovery.sources:
            source = CandidateSource(
                id=uuid4(),
                candidate_id=candidate.id,
                kind=finding.kind,
                url=str(finding.url),
                status=finding.status,
                verification_method=finding.verification_method,
                confidence=finding.confidence,
                official=finding.official,
                discovered_by="agent:company-source-discovery",
                created_at=utcnow(),
                verified_at=(utcnow() if finding.status is SourceStatus.VERIFIED else None),
                last_checked_at=utcnow(),
                notes="; ".join(finding.warnings) or None,
                evidence=finding.evidence,
            )
            # Agent inference can propose, but never establish officiality by itself.
            if source.verification_method is VerificationMethod.AGENT_INFERENCE and source.official:
                source = replace(source, official=False, status=SourceStatus.DISCOVERED)
            candidate = candidate.with_source(source)

        gaps = self.readiness.derive_source_gaps(
            candidate_id=candidate.id,
            sources=candidate.sources,
            existing_gaps=candidate.gaps,
        )
        for gap_finding in discovery.gaps:
            if not any(gap.code == gap_finding.code and gap.status is GapStatus.OPEN for gap in gaps):
                gaps = (
                    *gaps,
                    CandidateGap(
                        id=uuid4(),
                        candidate_id=candidate.id,
                        code=gap_finding.code,
                        title=gap_finding.title,
                        description=gap_finding.description,
                        source_kind=gap_finding.source_kind,
                        level=gap_finding.level,
                        status=GapStatus.OPEN,
                        requested_user_action=gap_finding.requested_user_action,
                        created_at=utcnow(),
                    ),
                )
        candidate = candidate.with_gaps(gaps)
        candidate = await self._persist(candidate)

        readiness = self.readiness.evaluate(
            sources=candidate.sources,
            open_gaps=candidate.open_gaps,
            identity_resolved=True,
        )
        if readiness.blocker_codes and not allow_incomplete:
            candidate = await self._move(candidate, CandidateStatus.AWAITING_USER_INPUT)
            return self._pending(candidate, "Fontes oficiais obrigatórias não foram encontradas")

        candidate = await self._move(candidate, CandidateStatus.SOURCE_VALIDATION)
        candidate = await self._move(candidate, CandidateStatus.DOCUMENT_COLLECTION)
        collection = await self.document_collector.collect(candidate, data_as_of=data_as_of)
        if not collection.success or not collection.latest_period_found:
            candidate = candidate.with_gaps((*candidate.gaps, *collection.gaps))
            candidate = await self._persist(candidate)
            candidate = await self._move(candidate, CandidateStatus.AWAITING_USER_INPUT)
            return self._pending(candidate, "Documentos financeiros atuais não foram coletados")

        candidate = await self._move(candidate, CandidateStatus.DATA_QUALITY)
        quality = await self.data_validator.validate(candidate, collection, data_as_of=data_as_of)
        if not quality.promotable:
            gaps = tuple(
                CandidateGap(
                    id=uuid4(),
                    candidate_id=candidate.id,
                    code=code,
                    title=f"Bloqueio de qualidade: {code}",
                    description="Os dados não passaram nas regras determinísticas de qualidade e reconciliação.",
                    source_kind=None,
                    level=RequirementLevel.BLOCKING,
                    status=GapStatus.OPEN,
                    requested_user_action=(
                        "Revise a fonte/documento ou aprove uma correção de dados antes de reprocessar."
                    ),
                    created_at=utcnow(),
                )
                for code in quality.blocker_codes
            )
            candidate = candidate.with_gaps((*candidate.gaps, *gaps))
            candidate = await self._persist(candidate)
            candidate = await self._move(candidate, CandidateStatus.AWAITING_USER_INPUT)
            return self._pending(candidate, "Dados financeiros não promovíveis")

        candidate = await self._move(candidate, CandidateStatus.FUNDAMENTAL_ANALYSIS)
        research = await self.research_pipeline.analyze(candidate, data_as_of=data_as_of)
        if not research.completed or research.evidence_coverage < Decimal("0.90"):
            gap = CandidateGap(
                id=uuid4(),
                candidate_id=candidate.id,
                code="research_evidence_coverage",
                title="Cobertura de evidências insuficiente",
                description="A análise não possui evidência citável suficiente para sustentar uma decisão.",
                source_kind=None,
                level=RequirementLevel.BLOCKING,
                status=GapStatus.OPEN,
                requested_user_action="Revise os documentos ausentes ou forneça fontes complementares e reexecute.",
                created_at=utcnow(),
            )
            candidate = candidate.with_gaps((*candidate.gaps, gap))
            candidate = await self._persist(candidate)
            candidate = await self._move(candidate, CandidateStatus.AWAITING_USER_INPUT)
            return self._pending(candidate, "Pesquisa incompleta")

        if research.recommendation is CandidateDecision.REJECT:
            candidate = await self._move(candidate, CandidateStatus.REJECTED)
            return CandidateWorkflowResult(
                candidate_id=candidate.id,
                status=candidate.status,
                decision=CandidateDecision.REJECT,
                reason="Pesquisa fundamentalista rejeitou o candidato",
                blocker_codes=research.blocker_codes,
            )

        candidate = await self._move(candidate, CandidateStatus.RISK_ANALYSIS)
        risk = await self.risk_pipeline.analyze(candidate, research, data_as_of=data_as_of)
        if not risk.completed or not risk.eligible or risk.hard_limit_breaches:
            candidate = await self._move(candidate, CandidateStatus.REJECTED)
            return CandidateWorkflowResult(
                candidate_id=candidate.id,
                status=candidate.status,
                decision=CandidateDecision.REJECT,
                reason="Candidato bloqueado por risco",
                blocker_codes=risk.hard_limit_breaches,
            )

        candidate = await self._move(candidate, CandidateStatus.COMMITTEE_REVIEW)
        committee = await self.committee.review(
            candidate,
            research,
            risk,
            data_as_of=data_as_of,
        )
        target = {
            CandidateDecision.APPROVE: CandidateStatus.APPROVED,
            CandidateDecision.REJECT: CandidateStatus.REJECTED,
            CandidateDecision.PENDING: CandidateStatus.AWAITING_USER_INPUT,
            CandidateDecision.WATCHLIST: CandidateStatus.WATCHLIST,
        }[committee.decision]
        candidate = await self._move(candidate, target)
        candidate = replace(
            candidate,
            final_decision=committee.decision,
            final_decision_reason=committee.reason,
            approved_portfolio_eligible=(committee.decision is CandidateDecision.APPROVE),
            updated_at=utcnow(),
            lock_version=candidate.lock_version + 1,
        )
        candidate = await self._persist(candidate)
        return CandidateWorkflowResult(
            candidate_id=candidate.id,
            status=candidate.status,
            decision=committee.decision,
            reason=committee.reason,
            blocker_codes=committee.missing_items,
        )

    async def _move(
        self,
        candidate: InvestmentCandidate,
        target: CandidateStatus,
    ) -> InvestmentCandidate:
        if candidate.status is target:
            return candidate
        require_transition(candidate.status, target)
        updated = replace(
            candidate,
            status=target,
            updated_at=utcnow(),
            lock_version=candidate.lock_version + 1,
        )
        return await self._persist(updated)

    async def _persist(self, candidate: InvestmentCandidate) -> InvestmentCandidate:
        current = await self.repository.get(candidate.id)
        await self.repository.save(candidate, expected_version=current.lock_version)
        return candidate

    @staticmethod
    def _pending(candidate: InvestmentCandidate, reason: str) -> CandidateWorkflowResult:
        return CandidateWorkflowResult(
            candidate_id=candidate.id,
            status=candidate.status,
            decision=CandidateDecision.PENDING,
            reason=reason,
            blocker_codes=tuple(gap.code for gap in candidate.blocking_gaps),
        )
