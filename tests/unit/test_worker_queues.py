from apps.worker.main import ACTIVITIES_BY_CAPABILITY, WORKFLOWS_BY_CAPABILITY
from ia_investing.orchestration import TASK_QUEUES, Capability
from workflows import (
    DispatchOperationsWorkflow,
    IngestCVMWorkflow,
    PaperRebalanceWorkflow,
    PaperReconciliationWorkflow,
    PaperValuationWorkflow,
    PortfolioConstructionWorkflow,
    PortfolioOptimizationWorkflow,
    PortfolioRankingWorkflow,
    RunAgentWorkflow,
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
    }
    assert {
        activity.__temporal_activity_definition.name for activity in ACTIVITIES_BY_CAPABILITY[Capability.DATA_INGESTION]
    } == {
        "download_cvm_filing",
        "parse_cvm_csv",
        "run_accounting_validations",
        "store_financial_statements",
        "publish_event",
    }
