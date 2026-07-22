from __future__ import annotations

import logging

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
    SourceDiscoveryCheckpoint,
)
from ia_investing.platform.database.runtime import DatabaseRuntime

logger = logging.getLogger(__name__)


def _stage_blocked(
    command: CandidateWorkflowInput,
    stage: str,
    reason: str,
    *,
    blocker_codes: tuple[str, ...] = (),
) -> CandidateCheckpoint:
    return CandidateCheckpoint(
        candidate_id=command.candidate_id,
        stage=stage,
        blocked=True,
        decision="pending",
        reason=reason,
        blocker_codes=blocker_codes,
    )


def _stage_passed(command: CandidateWorkflowInput, stage: str, *, reason: str = "ok") -> CandidateCheckpoint:
    return CandidateCheckpoint(
        candidate_id=command.candidate_id,
        stage=stage,
        blocked=False,
        decision="continue",
        reason=reason,
    )


def create_runtime(database_url: str | None = None) -> CallbackCandidateActivityRuntime:
    db = DatabaseRuntime.create(database_url) if database_url else None

    async def resolve_identity(command: CandidateWorkflowInput) -> CandidateCheckpoint:
        if db is None:
            return _stage_blocked(
                command,
                "identity_resolution",
                "Identity resolution requires a database connection; not yet configured.",
                blocker_codes=("identity_resolution",),
            )
        logger.info("resolve_candidate_identity candidate=%s", command.candidate_id)
        return _stage_blocked(
            command,
            "identity_resolution",
            "Identity resolution connector not yet implemented. Requires issuer catalog query.",
            blocker_codes=("identity_resolution",),
        )

    async def discover_sources(command: CandidateWorkflowInput) -> SourceDiscoveryCheckpoint:
        logger.info("discover_candidate_sources candidate=%s", command.candidate_id)
        return SourceDiscoveryCheckpoint(
            command=command,
            output={
                "stage": "source_discovery",
                "sources": [],
                "gaps": [],
                "summary": "Source discovery requires an AI provider integration; not yet wired.",
            },
        )

    async def persist_sources(checkpoint: SourceDiscoveryCheckpoint) -> None:
        logger.info("persist_candidate_sources candidate=%s", checkpoint.command.candidate_id)

    async def validate_supplied_source(
        command: CandidateSourceValidationInput,
    ) -> CandidateSourceValidationResult:
        logger.info("validate_supplied_source candidate=%s source=%s", command.candidate_id, command.source_id)
        return CandidateSourceValidationResult(
            candidate_id=command.candidate_id,
            source_id=command.source_id,
            status="pending",
            official=False,
            reason="URL validation requires SafeHttpClient and connector; not yet wired.",
        )

    async def evaluate_readiness(command: CandidateWorkflowInput) -> CandidateCheckpoint:
        logger.info("evaluate_candidate_readiness candidate=%s", command.candidate_id)
        return _stage_passed(command, "readiness", reason="Readiness evaluation available when data is loaded.")

    async def validate_sources(command: CandidateWorkflowInput) -> CandidateCheckpoint:
        return _stage_blocked(
            command,
            "source_validation",
            "Source validation requires connector verification; not yet implemented.",
            blocker_codes=("source_validation",),
        )

    async def collect_documents(command: CandidateWorkflowInput) -> CandidateCheckpoint:
        return _stage_blocked(
            command,
            "document_collection",
            "Document collection requires CVM/B3/RI connectors; not yet implemented.",
            blocker_codes=("document_collection",),
        )

    async def validate_financials(command: CandidateWorkflowInput) -> CandidateCheckpoint:
        return _stage_blocked(
            command,
            "data_quality",
            "Financial data validation requires financial facts service; not yet wired.",
            blocker_codes=("data_quality",),
        )

    async def analyze_fundamentals(command: CandidateWorkflowInput) -> CandidateCheckpoint:
        return _stage_blocked(
            command,
            "fundamental_analysis",
            "Fundamental analysis requires AI provider integration; not yet wired.",
            blocker_codes=("fundamental_analysis",),
        )

    async def analyze_risk(command: CandidateWorkflowInput) -> CandidateCheckpoint:
        return _stage_blocked(
            command,
            "risk_analysis",
            "Risk analysis requires risk service integration; not yet wired.",
            blocker_codes=("risk_analysis",),
        )

    async def build_committee_pack(command: CandidateWorkflowInput) -> CandidateCheckpoint:
        return _stage_blocked(
            command,
            "committee_review",
            "Committee review requires committee service integration; not yet wired.",
            blocker_codes=("committee_review",),
        )

    async def complete_run(
        command: CandidateWorkflowInput,
        checkpoint: CandidateCheckpoint,
    ) -> CandidateWorkflowResult:
        logger.info("complete_candidate_analysis_run candidate=%s stage=%s", command.candidate_id, checkpoint.stage)
        return CandidateWorkflowResult(
            candidate_id=command.candidate_id,
            analysis_run_id=command.analysis_run_id,
            status="blocked" if checkpoint.blocked else "succeeded",
            decision=checkpoint.decision,
            reason=checkpoint.reason,
            blocker_codes=checkpoint.blocker_codes,
        )

    async def screen_universe(command: ExplorationWorkflowInput) -> ExplorationShortlist:
        logger.info("screen_equity_universe exploration_run=%s", command.exploration_run_id)
        return ExplorationShortlist(
            command=command,
            securities=(),
            universe_size=0,
            eligible_size=0,
        )

    async def explore_shortlist(shortlist: ExplorationShortlist) -> ExplorationFindings:
        return ExplorationFindings(
            shortlist=shortlist,
            suggestions=(),
            limitations=("Equity explorer agent requires AI provider integration; not yet wired.",),
        )

    async def persist_suggestions(findings: ExplorationFindings) -> ExplorationWorkflowResult:
        return ExplorationWorkflowResult(
            exploration_run_id=findings.shortlist.command.exploration_run_id,
            status="blocked",
            universe_size=findings.shortlist.universe_size,
            eligible_size=findings.shortlist.eligible_size,
            suggestion_count=0,
        )

    return CallbackCandidateActivityRuntime(
        resolve_identity=resolve_identity,
        discover_sources=discover_sources,
        persist_sources=persist_sources,
        validate_supplied_source=validate_supplied_source,
        evaluate_readiness=evaluate_readiness,
        validate_sources=validate_sources,
        collect_documents=collect_documents,
        validate_financials=validate_financials,
        analyze_fundamentals=analyze_fundamentals,
        analyze_risk=analyze_risk,
        build_committee_pack=build_committee_pack,
        complete_run=complete_run,
        screen_universe=screen_universe,
        explore_shortlist=explore_shortlist,
        persist_suggestions=persist_suggestions,
    )
