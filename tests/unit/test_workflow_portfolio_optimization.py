"""Unit tests for workflows._portfolio_optimization — PortfolioOptimizationWorkflow."""

from __future__ import annotations

from typing import Any

import pytest
from temporalio import activity
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from workflows._portfolio_optimization import (
    PortfolioOptimizationInput,
    PortfolioOptimizationWorkflow,
)

TASK_QUEUE = "test-portfolio-opt"


def _make_activities(result: dict[str, Any] | None = None):
    @activity.defn(name="optimize_model_portfolio")
    async def fake_optimize(portfolio_id: str, organization_id: str, as_of: str) -> dict[str, Any]:
        return result or {
            "portfolio_id": portfolio_id,
            "optimization_run_id": "run-1",
            "as_of": as_of,
            "input_sha256": "abc",
            "status": "completed",
            "solver": "scipy",
            "weights": {"PETR4": 0.5, "VALE3": 0.5},
            "diagnostics": {},
            "environment": "paper",
        }

    return [fake_optimize]


@pytest.mark.unit
class TestPortfolioOptimizationInput:
    def test_defaults(self):
        inp = PortfolioOptimizationInput(portfolio_id="p1", organization_id="o1", as_of="2026-01-01")
        assert inp.timeout_seconds == 45

    def test_frozen(self):
        inp = PortfolioOptimizationInput(portfolio_id="p1", organization_id="o1", as_of="2026-01-01")
        with pytest.raises(AttributeError):
            inp.timeout_seconds = 10  # type: ignore[misc]


@pytest.mark.unit
class TestPortfolioOptimizationWorkflow:
    @pytest.mark.asyncio
    async def test_happy_path(self):
        acts = _make_activities()
        async with await WorkflowEnvironment.start_local() as env:
            async with Worker(env.client, task_queue=TASK_QUEUE, activities=acts, workflows=[PortfolioOptimizationWorkflow]):
                result = await env.client.execute_workflow(
                    PortfolioOptimizationWorkflow.run,
                    PortfolioOptimizationInput(portfolio_id="p1", organization_id="o1", as_of="2026-01-01"),
                    id="test-portfolio-opt-1",
                    task_queue=TASK_QUEUE,
                )
        assert result.status == "completed"
        assert result.solver == "scipy"

    @pytest.mark.asyncio
    async def test_timeout_zero_raises(self):
        acts = _make_activities()
        async with await WorkflowEnvironment.start_local() as env:
            async with Worker(env.client, task_queue=TASK_QUEUE, activities=acts, workflows=[PortfolioOptimizationWorkflow]):
                with pytest.raises(ValueError, match="optimization timeout"):
                    await env.client.execute_workflow(
                        PortfolioOptimizationWorkflow.run,
                        PortfolioOptimizationInput(portfolio_id="p1", organization_id="o1", as_of="2026-01-01", timeout_seconds=0),
                        id="test-portfolio-opt-2",
                        task_queue=TASK_QUEUE,
                    )

    @pytest.mark.asyncio
    async def test_timeout_too_large_raises(self):
        acts = _make_activities()
        async with await WorkflowEnvironment.start_local() as env:
            async with Worker(env.client, task_queue=TASK_QUEUE, activities=acts, workflows=[PortfolioOptimizationWorkflow]):
                with pytest.raises(ValueError, match="optimization timeout"):
                    await env.client.execute_workflow(
                        PortfolioOptimizationWorkflow.run,
                        PortfolioOptimizationInput(portfolio_id="p1", organization_id="o1", as_of="2026-01-01", timeout_seconds=301),
                        id="test-portfolio-opt-3",
                        task_queue=TASK_QUEUE,
                    )

    @pytest.mark.asyncio
    async def test_timeout_boundary(self):
        acts = _make_activities()
        async with await WorkflowEnvironment.start_local() as env:
            async with Worker(env.client, task_queue=TASK_QUEUE, activities=acts, workflows=[PortfolioOptimizationWorkflow]):
                result = await env.client.execute_workflow(
                    PortfolioOptimizationWorkflow.run,
                    PortfolioOptimizationInput(portfolio_id="p1", organization_id="o1", as_of="2026-01-01", timeout_seconds=300),
                    id="test-portfolio-opt-4",
                    task_queue=TASK_QUEUE,
                )
        assert result.status == "completed"
