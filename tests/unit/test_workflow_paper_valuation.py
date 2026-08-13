"""Unit tests for workflows._paper_valuation — PaperValuationWorkflow."""

from __future__ import annotations

from typing import Any

import pytest
from temporalio import activity
from temporalio.client import WorkflowFailureError
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from workflows._paper_valuation import PaperValuationInput, PaperValuationWorkflow

TASK_QUEUE = "test-paper-val"


def _make_activities(pub_result: dict[str, Any] | None = None):
    captured: list[dict[str, Any]] = []

    @activity.defn(name="reconcile_paper_portfolio")
    async def fake_reconcile(portfolio_id: str, organization_id: str, as_of: str) -> dict[str, Any]:
        return {"blocking_count": 0, "break_count": 0}

    @activity.defn(name="publish_paper_nav")
    async def fake_publish(portfolio_version_id: str, organization_id: str, as_of: str) -> dict[str, Any]:
        return pub_result or {
            "portfolio_id": "p1",
            "portfolio_version_id": portfolio_version_id,
            "nav_publication_id": "np-1",
            "as_of": as_of,
            "revision": 1,
            "input_sha256": "abc",
            "nav": "1000.00",
            "reconciled": True,
            "environment": "paper",
        }

    @activity.defn(name="record_schedule_run")
    async def fake_record(input: dict) -> None:
        captured.append(input)

    return [fake_reconcile, fake_publish, fake_record], captured


@pytest.mark.unit
class TestPaperValuationInput:
    def test_defaults(self):
        inp = PaperValuationInput(portfolio_id="p1", portfolio_version_id="pv1", organization_id="o1")
        assert inp.schedule_id == ""

    def test_frozen(self):
        inp = PaperValuationInput(portfolio_id="p1", portfolio_version_id="pv1", organization_id="o1")
        with pytest.raises(AttributeError):
            inp.portfolio_id = "x"  # type: ignore[misc]


@pytest.mark.unit
class TestPaperValuationWorkflow:
    @pytest.mark.asyncio
    async def test_happy_path(self):
        acts, _ = _make_activities()
        async with await WorkflowEnvironment.start_local() as env:
            async with Worker(env.client, task_queue=TASK_QUEUE, activities=acts, workflows=[PaperValuationWorkflow]):
                result = await env.client.execute_workflow(
                    PaperValuationWorkflow.run,
                    PaperValuationInput(portfolio_id="p1", portfolio_version_id="pv1", organization_id="o1", schedule_id="s1"),
                    id="test-paper-val-1",
                    task_queue=TASK_QUEUE,
                )
        assert result.nav == "1000.00"
        assert result.reconciled is True

    @pytest.mark.asyncio
    async def test_blocking_reconciliation_raises(self):
        @activity.defn(name="reconcile_paper_portfolio")
        async def blocking_reconcile(portfolio_id: str, organization_id: str, as_of: str) -> dict[str, Any]:
            return {"blocking_count": 3, "break_count": 5}

        @activity.defn(name="publish_paper_nav")
        async def fake_publish(portfolio_version_id: str, organization_id: str, as_of: str) -> dict[str, Any]:
            return {"nav": "0"}

        @activity.defn(name="record_schedule_run")
        async def fake_record(input: dict) -> None:
            captured.append(input)

        captured: list[dict[str, Any]] = []
        acts = [blocking_reconcile, fake_publish, fake_record]
        async with await WorkflowEnvironment.start_local() as env:
            async with Worker(env.client, task_queue=TASK_QUEUE, activities=acts, workflows=[PaperValuationWorkflow]):
                with pytest.raises(WorkflowFailureError):
                    await env.client.execute_workflow(
                        PaperValuationWorkflow.run,
                        PaperValuationInput(portfolio_id="p1", portfolio_version_id="pv1", organization_id="o1", schedule_id="s1"),
                        id="test-paper-val-2",
                        task_queue=TASK_QUEUE,
                    )
        assert captured[1]["status"] == "failed"

    @pytest.mark.asyncio
    async def test_no_schedule_skips_record(self):
        acts, captured = _make_activities()
        async with await WorkflowEnvironment.start_local() as env:
            async with Worker(env.client, task_queue=TASK_QUEUE, activities=acts, workflows=[PaperValuationWorkflow]):
                await env.client.execute_workflow(
                    PaperValuationWorkflow.run,
                    PaperValuationInput(portfolio_id="p1", portfolio_version_id="pv1", organization_id="o1"),
                    id="test-paper-val-3",
                    task_queue=TASK_QUEUE,
                )
        assert captured == []
