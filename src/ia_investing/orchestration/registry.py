"""Explicit Temporal worker capability registry.

Only workflows and activities listed here are executable. Phase-one mock
activities are intentionally excluded from all production-capable workers.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ia_investing.orchestration.activities.agent_runtime import AGENT_RUNTIME_ACTIVITIES
from ia_investing.candidate_intelligence.bootstrap import candidate_intelligence_enabled
from ia_investing.orchestration.activities.candidate_dispatch import CANDIDATE_DISPATCH_ACTIVITIES
from ia_investing.orchestration.activities.candidate_intelligence import CANDIDATE_INTELLIGENCE_ACTIVITIES
from ia_investing.orchestration.activities.data_ingestion import DATA_INGESTION_ACTIVITIES
from ia_investing.orchestration.activities.notifications import NOTIFICATION_ACTIVITIES
from ia_investing.orchestration.activities.operation_dispatch import OPERATION_DISPATCH_ACTIVITIES
from ia_investing.orchestration.activities.paper_operations import PAPER_OPERATION_ACTIVITIES
from ia_investing.orchestration.activities.portfolio_construction import (
    PORTFOLIO_CONSTRUCTION_ACTIVITIES,
)
from ia_investing.orchestration.activities.portfolio_ranking import PORTFOLIO_RANKING_ACTIVITIES
from workflows.candidate_dispatch import CandidateOutboxDispatchWorkflow
from workflows.candidate_intelligence import (
    AutonomousEquityExplorationWorkflow,
    CandidateAnalysisWorkflow,
    CandidateSourceValidationWorkflow,
    ScheduledEquityExplorationWorkflow,
)
from workflows._dispatch_operations import DispatchOperationsWorkflow
from workflows._ingest_cvm import IngestCVMWorkflow
from workflows._paper_rebalance import PaperRebalanceWorkflow
from workflows._paper_reconciliation import PaperReconciliationWorkflow
from workflows._paper_valuation import PaperValuationWorkflow
from workflows._portfolio_construction import PortfolioConstructionWorkflow
from workflows._portfolio_optimization import PortfolioOptimizationWorkflow
from workflows._portfolio_ranking import PortfolioRankingWorkflow
from workflows._run_agent import RunAgentWorkflow


@dataclass(frozen=True, slots=True)
class CapabilityDefinition:
    task_queue: str
    workflows: tuple[type[Any], ...]
    activities: tuple[Any, ...]



_CANDIDATE_WORKFLOWS = (
    CandidateOutboxDispatchWorkflow,
    CandidateAnalysisWorkflow,
    CandidateSourceValidationWorkflow,
    AutonomousEquityExplorationWorkflow,
    ScheduledEquityExplorationWorkflow,
) if candidate_intelligence_enabled() else ()

_CANDIDATE_ACTIVITIES = (
    CANDIDATE_DISPATCH_ACTIVITIES + CANDIDATE_INTELLIGENCE_ACTIVITIES
) if candidate_intelligence_enabled() else ()

CAPABILITIES: dict[str, CapabilityDefinition] = {
    "data-ingestion": CapabilityDefinition(
        task_queue="data-ingestion",
        workflows=(IngestCVMWorkflow,),
        # IngestCVMWorkflow publishes its completion event without overriding
        # the activity task queue, so publish_event must be registered here.
        activities=DATA_INGESTION_ACTIVITIES + NOTIFICATION_ACTIVITIES,
    ),
    "research-agents": CapabilityDefinition(
        task_queue="research-agents",
        workflows=(RunAgentWorkflow, DispatchOperationsWorkflow) + _CANDIDATE_WORKFLOWS,
        activities=AGENT_RUNTIME_ACTIVITIES + OPERATION_DISPATCH_ACTIVITIES + _CANDIDATE_ACTIVITIES,
    ),
    "portfolio-risk": CapabilityDefinition(
        task_queue="portfolio-risk",
        workflows=(
            PortfolioConstructionWorkflow,
            PortfolioOptimizationWorkflow,
            PaperValuationWorkflow,
            PaperRebalanceWorkflow,
            PaperReconciliationWorkflow,
            PortfolioRankingWorkflow,
        ),
        activities=(
            PORTFOLIO_CONSTRUCTION_ACTIVITIES
            + PAPER_OPERATION_ACTIVITIES
            + PORTFOLIO_RANKING_ACTIVITIES
        ),
    ),
    "notifications": CapabilityDefinition(
        task_queue="notifications",
        workflows=(),
        activities=NOTIFICATION_ACTIVITIES,
    ),
}


def definitions_for(capability: str) -> tuple[str, list[type[Any]], list[Any]]:
    try:
        definition = CAPABILITIES[capability]
    except KeyError as exc:
        raise ValueError(f"unknown worker capability: {capability!r}") from exc
    if definition.workflows and not definition.activities:
        raise RuntimeError(f"capability {capability!r} has workflows but no activities")
    return definition.task_queue, list(definition.workflows), list(definition.activities)
