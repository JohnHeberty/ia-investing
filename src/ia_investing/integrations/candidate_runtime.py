from __future__ import annotations

from ia_investing.integrations.production_runtime import create_production_runtime
from ia_investing.orchestration.activities.candidate_intelligence import (
    CallbackCandidateActivityRuntime,
    CandidateCheckpoint,
    CandidateWorkflowInput,
    CandidateWorkflowResult,
)
from ia_investing.platform.database.runtime import DatabaseRuntime


async def create_runtime(db: DatabaseRuntime) -> CallbackCandidateActivityRuntime:
    runtime = await create_production_runtime(db)

    async def complete_run(
        command: CandidateWorkflowInput,
        checkpoint: CandidateCheckpoint,
    ) -> CandidateWorkflowResult:
        return await runtime.complete_candidate_analysis_run(command, checkpoint)

    return CallbackCandidateActivityRuntime(
        resolve_identity=runtime.resolve_candidate_identity,
        discover_sources=runtime.discover_candidate_sources,
        persist_sources=runtime.persist_candidate_sources_and_gaps,
        validate_supplied_source=runtime.validate_supplied_candidate_source,
        evaluate_readiness=runtime.evaluate_candidate_readiness,
        validate_sources=runtime.validate_candidate_sources,
        collect_documents=runtime.collect_candidate_documents,
        validate_financials=runtime.validate_candidate_financial_data,
        analyze_fundamentals=runtime.run_candidate_fundamental_analysis,
        analyze_risk=runtime.run_candidate_risk_analysis,
        build_committee_pack=runtime.create_committee_pack,
        complete_run=complete_run,
        screen_universe=runtime.screen_equity_universe,
        explore_shortlist=runtime.run_equity_explorer_agent,
        persist_suggestions=runtime.persist_exploration_suggestions,
    )
