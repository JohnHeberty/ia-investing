from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from ia_investing.orchestration.policies import DEFAULT_ACTIVITY_RETRY_POLICY


@dataclass(frozen=True, slots=True)
class PortfolioOptimizationInput:
    portfolio_id: str
    organization_id: str
    as_of: str
    timeout_seconds: int = 45


@dataclass(frozen=True, slots=True)
class PortfolioOptimizationResult:
    portfolio_id: str
    optimization_run_id: str
    as_of: str
    input_sha256: str
    status: str
    solver: str
    weights: dict[str, float]
    diagnostics: dict[str, object]
    environment: str


@workflow.defn
class PortfolioOptimizationWorkflow:
    """Execute CPU-heavy portfolio optimization with durable timeout/cancellation."""

    @workflow.run
    async def run(self, command: PortfolioOptimizationInput) -> PortfolioOptimizationResult:
        if command.timeout_seconds <= 0 or command.timeout_seconds > 300:
            raise ValueError("optimization timeout must be between 1 and 300 seconds")
        result = await workflow.execute_activity(
            "optimize_model_portfolio",
            args=[command.portfolio_id, command.organization_id, command.as_of],
            start_to_close_timeout=timedelta(seconds=command.timeout_seconds),
            heartbeat_timeout=timedelta(seconds=min(command.timeout_seconds, 30)),
            retry_policy=DEFAULT_ACTIVITY_RETRY_POLICY,
        )
        return PortfolioOptimizationResult(**result)
