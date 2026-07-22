from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from decimal import Decimal
from typing import Protocol
from uuid import UUID, uuid4

from .contracts import CandidateCreateRequest, CandidateReanalysisRequest, CandidateSourceCreateRequest
from .enums import (
    AnalysisRunStatus,
    AnalysisTrigger,
    CandidateDecision,
    CandidateStatus,
    ExplorationRunStatus,
    SuggestionStatus,
)
from .models import (
    AnalysisRun,
    CandidateIdentity,
    CandidateSource,
    ExplorationRun,
    InvestmentCandidate,
    utcnow,
)
from .readiness import ReadinessEvaluator
from .repositories import CandidateRepository, ExplorationRepository
from .state_machine import require_transition


class WorkflowStarter(Protocol):
    async def start_candidate_analysis(
        self,
        *,
        candidate_id: UUID,
        analysis_run_id: UUID,
        trigger: AnalysisTrigger,
        data_as_of: datetime,
        allow_incomplete: bool,
    ) -> str: ...

    async def start_exploration(self, *, exploration_run_id: UUID) -> str: ...


class EventPublisher(Protocol):
    async def publish(self, event_type: str, payload: dict[str, object]) -> None: ...


class NullEventPublisher:
    async def publish(self, event_type: str, payload: dict[str, object]) -> None:
        return None


class CandidateService:
    def __init__(
        self,
        *,
        repository: CandidateRepository,
        workflow_starter: WorkflowStarter,
        readiness: ReadinessEvaluator | None = None,
        publisher: EventPublisher | None = None,
    ) -> None:
        self.repository = repository
        self.workflow_starter = workflow_starter
        self.readiness = readiness or ReadinessEvaluator()
        self.publisher = publisher or NullEventPublisher()

    async def create_manual(
        self,
        *,
        organization_id: UUID,
        actor_id: str,
        request: CandidateCreateRequest,
        data_as_of: datetime,
    ) -> tuple[InvestmentCandidate, AnalysisRun, str]:
        identity = CandidateIdentity(
            ticker=request.ticker,
            exchange=request.exchange,
            legal_name=request.legal_name,
            trading_name=request.trading_name,
            cnpj=request.cnpj,
            cvm_code=request.cvm_code,
        )
        candidate = InvestmentCandidate.create_manual(
            organization_id=organization_id,
            identity=identity,
            actor_id=actor_id,
            rationale=request.rationale,
        )
        gaps = self.readiness.derive_source_gaps(candidate_id=candidate.id, sources=())
        candidate = candidate.with_gaps(gaps)
        run = AnalysisRun(
            id=uuid4(),
            candidate_id=candidate.id,
            run_number=1,
            trigger=AnalysisTrigger.INITIAL,
            status=AnalysisRunStatus.QUEUED,
            requested_by=actor_id,
            requested_at=utcnow(),
            data_as_of=data_as_of,
        )
        candidate = candidate.with_analysis_run(run)
        await self.repository.add(candidate)
        workflow_id = await self.workflow_starter.start_candidate_analysis(
            candidate_id=candidate.id,
            analysis_run_id=run.id,
            trigger=run.trigger,
            data_as_of=data_as_of,
            allow_incomplete=False,
        )
        await self.publisher.publish(
            "investment_candidate.created",
            {
                "candidate_id": str(candidate.id),
                "organization_id": str(organization_id),
                "ticker": candidate.identity.ticker,
                "origin": candidate.origin.value,
                "analysis_run_id": str(run.id),
                "workflow_id": workflow_id,
            },
        )
        return candidate, run, workflow_id

    async def add_user_source(
        self,
        *,
        candidate_id: UUID,
        actor_id: str,
        request: CandidateSourceCreateRequest,
        expected_version: int,
    ) -> InvestmentCandidate:
        candidate = await self.repository.get(candidate_id)
        source = CandidateSource.user_supplied(
            candidate_id=candidate.id,
            kind=request.kind,
            url=str(request.url),
            actor_id=actor_id,
            notes=request.notes,
        )
        updated = candidate.with_source(source)
        updated_gaps = self.readiness.derive_source_gaps(
            candidate_id=updated.id,
            sources=updated.sources,
            existing_gaps=updated.gaps,
        )
        updated = updated.with_gaps(updated_gaps)
        if updated.status is CandidateStatus.AWAITING_USER_INPUT and not updated.blocking_gaps:
            require_transition(updated.status, CandidateStatus.SOURCE_VALIDATION)
            updated = replace(
                updated,
                status=CandidateStatus.SOURCE_VALIDATION,
                updated_at=utcnow(),
                lock_version=updated.lock_version + 1,
            )
        await self.repository.save(updated, expected_version=expected_version)
        await self.publisher.publish(
            "investment_candidate.source_added",
            {
                "candidate_id": str(updated.id),
                "source_id": str(source.id),
                "source_kind": source.kind.value,
                "actor_id": actor_id,
            },
        )
        return updated

    async def resolve_gap(
        self,
        *,
        candidate_id: UUID,
        gap_id: UUID,
        actor_id: str,
        notes: str,
        expected_version: int,
    ) -> InvestmentCandidate:
        candidate = await self.repository.get(candidate_id)
        found = False
        gaps = []
        for gap in candidate.gaps:
            if gap.id == gap_id:
                found = True
                gaps.append(gap.resolve(actor_id, notes))
            else:
                gaps.append(gap)
        if not found:
            raise LookupError(str(gap_id))
        updated = candidate.with_gaps(tuple(gaps))
        await self.repository.save(updated, expected_version=expected_version)
        await self.publisher.publish(
            "investment_candidate.gap_resolved",
            {
                "candidate_id": str(candidate_id),
                "gap_id": str(gap_id),
                "actor_id": actor_id,
            },
        )
        return updated

    async def request_reanalysis(
        self,
        *,
        candidate_id: UUID,
        actor_id: str,
        request: CandidateReanalysisRequest,
        expected_version: int,
    ) -> tuple[InvestmentCandidate, AnalysisRun, str]:
        candidate = await self.repository.get(candidate_id)
        readiness = self.readiness.evaluate(
            sources=candidate.sources,
            open_gaps=candidate.open_gaps,
            identity_resolved=bool(
                candidate.identity.cvm_code or candidate.identity.cnpj or candidate.identity.issuer_id
            ),
        )
        if readiness.blocker_codes and not request.allow_incomplete:
            raise ValueError("candidate still has blocking gaps: " + ", ".join(readiness.blocker_codes))
        run = AnalysisRun(
            id=uuid4(),
            candidate_id=candidate.id,
            run_number=len(candidate.analysis_runs) + 1,
            trigger=request.trigger,
            status=AnalysisRunStatus.QUEUED,
            requested_by=actor_id,
            requested_at=utcnow(),
            data_as_of=request.data_as_of,
            blocker_codes=readiness.blocker_codes,
        )
        updated = candidate.with_analysis_run(run)
        if candidate.status in {
            CandidateStatus.AWAITING_USER_INPUT,
            CandidateStatus.REJECTED,
            CandidateStatus.WATCHLIST,
        }:
            target = CandidateStatus.SOURCE_DISCOVERY
            require_transition(candidate.status, target)
            updated = replace(
                updated,
                status=target,
                updated_at=utcnow(),
                lock_version=updated.lock_version + 1,
            )
        await self.repository.save(updated, expected_version=expected_version)
        workflow_id = await self.workflow_starter.start_candidate_analysis(
            candidate_id=candidate.id,
            analysis_run_id=run.id,
            trigger=run.trigger,
            data_as_of=request.data_as_of,
            allow_incomplete=request.allow_incomplete,
        )
        await self.publisher.publish(
            "investment_candidate.reanalysis_requested",
            {
                "candidate_id": str(candidate.id),
                "analysis_run_id": str(run.id),
                "workflow_id": workflow_id,
                "allow_incomplete": request.allow_incomplete,
            },
        )
        return updated, run, workflow_id

    async def apply_decision(
        self,
        *,
        candidate_id: UUID,
        decision: CandidateDecision,
        reason: str,
        expected_version: int,
    ) -> InvestmentCandidate:
        candidate = await self.repository.get(candidate_id)
        target_by_decision = {
            CandidateDecision.APPROVE: CandidateStatus.APPROVED,
            CandidateDecision.REJECT: CandidateStatus.REJECTED,
            CandidateDecision.PENDING: CandidateStatus.AWAITING_USER_INPUT,
            CandidateDecision.WATCHLIST: CandidateStatus.WATCHLIST,
        }
        target = target_by_decision[decision]
        require_transition(candidate.status, target)
        if decision is CandidateDecision.APPROVE:
            readiness = self.readiness.evaluate(
                sources=candidate.sources,
                open_gaps=candidate.open_gaps,
                identity_resolved=True,
                latest_documents_collected=True,
                financial_data_validated=True,
                fundamental_analysis_complete=True,
                risk_analysis_complete=True,
                committee_pack_complete=True,
            )
            if not readiness.ready_for_committee:
                raise ValueError("candidate cannot be approved without complete readiness")
        updated = replace(
            candidate,
            status=target,
            final_decision=decision,
            final_decision_reason=reason.strip(),
            approved_portfolio_eligible=(decision is CandidateDecision.APPROVE),
            updated_at=utcnow(),
            lock_version=candidate.lock_version + 1,
        )
        await self.repository.save(updated, expected_version=expected_version)
        return updated


class ExplorationService:
    def __init__(
        self,
        *,
        exploration_repository: ExplorationRepository,
        candidate_repository: CandidateRepository,
        workflow_starter: WorkflowStarter,
        publisher: EventPublisher | None = None,
    ) -> None:
        self.exploration_repository = exploration_repository
        self.candidate_repository = candidate_repository
        self.workflow_starter = workflow_starter
        self.publisher = publisher or NullEventPublisher()

    async def create_run(
        self,
        *,
        organization_id: UUID,
        actor_id: str,
        strategy_codes: tuple[str, ...],
        data_as_of: datetime,
        minimum_liquidity: Decimal,
        maximum_suggestions: int,
        excluded_instrument_ids: tuple[UUID, ...] = (),
    ) -> tuple[ExplorationRun, str]:
        run = ExplorationRun(
            id=uuid4(),
            organization_id=organization_id,
            status=ExplorationRunStatus.QUEUED,
            strategy_codes=strategy_codes,
            requested_by=actor_id,
            created_at=utcnow(),
            data_as_of=data_as_of,
            minimum_liquidity=minimum_liquidity,
            maximum_suggestions=maximum_suggestions,
            excluded_instrument_ids=excluded_instrument_ids,
        )
        await self.exploration_repository.add_run(run)
        workflow_id = await self.workflow_starter.start_exploration(exploration_run_id=run.id)
        run = replace(run, workflow_id=workflow_id)
        await self.exploration_repository.save_run(run)
        await self.publisher.publish(
            "equity_exploration.requested",
            {
                "exploration_run_id": str(run.id),
                "organization_id": str(organization_id),
                "workflow_id": workflow_id,
            },
        )
        return run, workflow_id

    async def promote_suggestion(
        self,
        *,
        suggestion_id: UUID,
        actor_id: str,
    ) -> InvestmentCandidate:
        suggestion = await self.exploration_repository.get_suggestion(suggestion_id)
        if suggestion.status is not SuggestionStatus.NEW:
            raise ValueError("only new suggestions can be promoted")
        duplicate = await self.candidate_repository.find_active_by_ticker(
            suggestion.organization_id,
            suggestion.identity.ticker,
            suggestion.identity.exchange,
        )
        if duplicate is not None:
            await self.exploration_repository.save_suggestion(replace(suggestion, status=SuggestionStatus.DUPLICATE))
            return duplicate
        candidate = InvestmentCandidate.create_from_explorer(
            organization_id=suggestion.organization_id,
            identity=suggestion.identity,
            actor_id=actor_id,
            suggestion_id=suggestion.id,
            rationale=suggestion.rationale,
        )
        for source in suggestion.discovered_sources:
            candidate = candidate.with_source(replace(source, candidate_id=candidate.id))
        await self.candidate_repository.add(candidate)
        await self.exploration_repository.save_suggestion(
            replace(
                suggestion,
                status=SuggestionStatus.PROMOTED,
                promoted_candidate_id=candidate.id,
            )
        )
        await self.publisher.publish(
            "equity_exploration.suggestion_promoted",
            {
                "suggestion_id": str(suggestion.id),
                "candidate_id": str(candidate.id),
                "ticker": candidate.identity.ticker,
            },
        )
        return candidate
