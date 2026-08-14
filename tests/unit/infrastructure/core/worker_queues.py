from apps.worker.main import ACTIVITIES_BY_CAPABILITY, WORKFLOWS_BY_CAPABILITY
from ia_investing.orchestration import TASK_QUEUES, Capability
from workflows import (
    DispatchOperationsWorkflow,
    ExtractNewsWorkflow,
    IngestCVMWorkflow,
    NewsDedupWorkflow,
    PaperRebalanceWorkflow,
    PaperReconciliationWorkflow,
    PaperValuationWorkflow,
    PolicyCollectionWorkflow,
    PolicyEventWorkflow,
    PortfolioConstructionWorkflow,
    PortfolioOptimizationWorkflow,
    PortfolioRankingWorkflow,
    RunAgentWorkflow,
)
from workflows._policy_source_collection import PolicySourceCollectionWorkflow
from workflows.candidate_dispatch import CandidateOutboxDispatchWorkflow
from workflows.candidate_intelligence import (
    AutonomousEquityExplorationWorkflow,
    CandidateAnalysisWorkflow,
    CandidateSourceValidationWorkflow,
    ScheduledEquityExplorationWorkflow,
)


def test_capability_queues_are_stable_and_unique() -> None:
    assert set(TASK_QUEUES.values()) == {
        "data-ingestion",
        "document-processing",
        "research-agents",
        "portfolio-risk",
        "notifications",
    }


def test_workflows_are_registered_on_expected_capabilities() -> None:
    assert WORKFLOWS_BY_CAPABILITY[Capability.DATA_INGESTION] == (IngestCVMWorkflow,)
    assert WORKFLOWS_BY_CAPABILITY[Capability.RESEARCH_AGENTS] == (
        RunAgentWorkflow,
        DispatchOperationsWorkflow,
        ExtractNewsWorkflow,
        NewsDedupWorkflow,
        PolicyCollectionWorkflow,
        PolicyEventWorkflow,
        PolicySourceCollectionWorkflow,
        CandidateOutboxDispatchWorkflow,
        CandidateAnalysisWorkflow,
        CandidateSourceValidationWorkflow,
        AutonomousEquityExplorationWorkflow,
        ScheduledEquityExplorationWorkflow,
    )
    assert WORKFLOWS_BY_CAPABILITY[Capability.PORTFOLIO_RISK] == (
        PortfolioConstructionWorkflow,
        PortfolioOptimizationWorkflow,
        PaperValuationWorkflow,
        PaperRebalanceWorkflow,
        PaperReconciliationWorkflow,
        PortfolioRankingWorkflow,
    )
    assert {
        activity.__temporal_activity_definition.name for activity in ACTIVITIES_BY_CAPABILITY[Capability.PORTFOLIO_RISK]
    } == {
        "run_scorecard",
        "validate_proposal_constraints",
        "reconcile_paper_portfolio",
        "publish_paper_nav",
        "optimize_model_portfolio",
        "persist_portfolio_ranking_snapshot",
        "record_schedule_run",
    }
    assert {
        activity.__temporal_activity_definition.name for activity in ACTIVITIES_BY_CAPABILITY[Capability.DATA_INGESTION]
    } == {
        "download_cvm_filing",
        "parse_cvm_csv",
        "run_accounting_validations",
        "store_financial_statements",
        "publish_event",
        "record_schedule_run",
    }
    research_activities = {
        activity.__temporal_activity_definition.name
        for activity in ACTIVITIES_BY_CAPABILITY[Capability.RESEARCH_AGENTS]
    }
    assert "record_schedule_run" in research_activities
    assert "fetch_policy_objects" in research_activities
    assert "ingest_policy_objects" in research_activities
    assert "list_active_policy_sources" in research_activities
    assert "collect_from_policy_source" in research_activities
