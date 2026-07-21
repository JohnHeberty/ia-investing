from apps.worker.main import ACTIVITIES_BY_CAPABILITY, WORKFLOWS_BY_CAPABILITY
from ia_investing.orchestration import TASK_QUEUES, Capability
from workflows import (
    AnalyzeFilingWorkflow,
    AnalyzeNewsWorkflow,
    ApprovalGateWorkflow,
    DiscoverStocksWorkflow,
    IngestCVMWorkflow,
    PaperRebalanceWorkflow,
    PaperReconciliationWorkflow,
    PaperValuationWorkflow,
    PolicyEventWorkflow,
    PortfolioConstructionWorkflow,
    PortfolioOptimizationWorkflow,
    RunAgentWorkflow,
    ThesisReviewWorkflow,
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
        AnalyzeFilingWorkflow,
        AnalyzeNewsWorkflow,
        ApprovalGateWorkflow,
        PolicyEventWorkflow,
        DiscoverStocksWorkflow,
        RunAgentWorkflow,
        ThesisReviewWorkflow,
    )
    assert WORKFLOWS_BY_CAPABILITY[Capability.PORTFOLIO_RISK] == (
        PortfolioConstructionWorkflow,
        PortfolioOptimizationWorkflow,
        PaperRebalanceWorkflow,
        PaperReconciliationWorkflow,
        PaperValuationWorkflow,
    )
    assert {
        activity.__temporal_activity_definition.name for activity in ACTIVITIES_BY_CAPABILITY[Capability.PORTFOLIO_RISK]
    } == {"reconcile_paper_portfolio", "publish_paper_nav", "optimize_model_portfolio", "run_scorecard", "validate_proposal_constraints"}
    assert {
        activity.__temporal_activity_definition.name for activity in ACTIVITIES_BY_CAPABILITY[Capability.DATA_INGESTION]
    } == {
        "download_cvm_filing",
        "parse_cvm_csv",
        "publish_event",
        "run_accounting_validations",
        "store_financial_statements",
    }
