import warnings

warnings.warn(
    "Importing from 'workflows' directly is deprecated. Use 'ia_investing.orchestration' instead.",
    DeprecationWarning,
    stacklevel=2,
)

from workflows._analyze_filing import AnalyzeFilingWorkflow  # noqa: E402
from workflows._analyze_news import AnalyzeNewsWorkflow  # noqa: E402
from workflows._approval_gate import ApprovalGateInput, ApprovalGateResult, ApprovalGateWorkflow  # noqa: E402
from workflows._discover import DiscoverStocksWorkflow  # noqa: E402
from workflows._dispatch_operations import DispatchOperationsWorkflow  # noqa: E402
from workflows._ingest_cvm import IngestCVMInput, IngestCVMOutput, IngestCVMWorkflow  # noqa: E402
from workflows._paper_rebalance import PaperRebalanceInput, PaperRebalanceResult, PaperRebalanceWorkflow  # noqa: E402
from workflows._paper_reconciliation import (  # noqa: E402
    PaperReconciliationInput,
    PaperReconciliationResult,
    PaperReconciliationWorkflow,
)
from workflows._paper_valuation import PaperValuationInput, PaperValuationResult, PaperValuationWorkflow  # noqa: E402
from workflows._policy_event import PolicyEventInput, PolicyEventResult, PolicyEventWorkflow  # noqa: E402
from workflows._portfolio_construction import (  # noqa: E402
    PipelineConfig,
    PortfolioConstructionInput,
    PortfolioConstructionResult,
    PortfolioConstructionWorkflow,
)
from workflows._portfolio_optimization import (  # noqa: E402
    PortfolioOptimizationInput,
    PortfolioOptimizationResult,
    PortfolioOptimizationWorkflow,
)
from workflows._portfolio_ranking import PortfolioRankingWorkflow  # noqa: E402
from workflows._run_agent import RunAgentInput, RunAgentWorkflow  # noqa: E402
from workflows._thesis_review import (  # noqa: E402
    ThesisReviewInput,
    ThesisReviewResult,
    ThesisReviewWorkflow,
)

__all__ = [
    "AnalyzeFilingWorkflow",
    "AnalyzeNewsWorkflow",
    "ApprovalGateInput",
    "ApprovalGateResult",
    "ApprovalGateWorkflow",
    "DiscoverStocksWorkflow",
    "DispatchOperationsWorkflow",
    "IngestCVMInput",
    "IngestCVMOutput",
    "IngestCVMWorkflow",
    "PaperRebalanceInput",
    "PaperRebalanceResult",
    "PaperRebalanceWorkflow",
    "PaperReconciliationInput",
    "PaperReconciliationResult",
    "PaperReconciliationWorkflow",
    "PaperValuationInput",
    "PaperValuationResult",
    "PaperValuationWorkflow",
    "PipelineConfig",
    "PolicyEventInput",
    "PolicyEventResult",
    "PolicyEventWorkflow",
    "PortfolioConstructionInput",
    "PortfolioConstructionResult",
    "PortfolioConstructionWorkflow",
    "PortfolioOptimizationInput",
    "PortfolioOptimizationResult",
    "PortfolioOptimizationWorkflow",
    "PortfolioRankingWorkflow",
    "RunAgentInput",
    "RunAgentWorkflow",
    "ThesisReviewInput",
    "ThesisReviewResult",
    "ThesisReviewWorkflow",
]
