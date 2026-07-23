"""Point-in-time ranking materialization workflow.

The workflow only accepts a bundle already produced by deterministic analytics.
It does not ask an LLM to score a portfolio.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from ia_investing.orchestration.policies import DEFAULT_ACTIVITY_RETRY_POLICY


@workflow.defn(name="PortfolioRankingWorkflow")
class PortfolioRankingWorkflow:
    @workflow.run
    async def run(self, evidence_bundle: dict[str, Any]) -> str:
        return await workflow.execute_activity(  # type: ignore[no-any-return]
            "persist_portfolio_ranking_snapshot",
            evidence_bundle,
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=DEFAULT_ACTIVITY_RETRY_POLICY,
        )
