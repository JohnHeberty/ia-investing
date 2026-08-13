"""Unit tests for workflows._paper_reconciliation — PaperReconciliationWorkflow."""

from __future__ import annotations

from typing import Any

import pytest
from temporalio import activity
from temporalio.client import WorkflowFailureError
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from workflows._paper_reconciliation import (
    PaperReconciliationInput,
    PaperReconciliationResult,
    PaperReconciliationWorkflow,
)

TASK_QUEUE = "test-paper-recon"


def _make_activities(result: dict[str, Any] | None = None):
    captured: list[dict[str, Any]] = []

    @activity.defn(name="reconcile_paper_portfolio")
    async def fake_reconcile(portfolio_id: str, organization_id: str, as_of: str) -> dict[str, Any]:
        return result or {"portfolio_id": portfolio_id, "break_count": 0, "blocking_count": 0, "as_of": as_of, "environment": "paper"}

    @activity.defn(name="record_schedule_run")
    async def fake_record(input: dict) -> None:
        captured.append(input)

    return [fake_reconcile, fake_record], captured


@pytest.mark.unit
class TestPaperReconciliationInput:
    def test_defaults(self):
        inp = PaperReconciliationInput(portfolio_id="p1", organization_id="o1")
        assert inp.schedule_id == ""

    def test_frozen(self):
        inp = PaperReconciliationInput(portfolio_id="p1", organization_id="o1")
        with pytest.raises(AttributeError):
            inp.portfolio_id = "x"  # type: ignore[misc]


@pytest.mark.unit
class TestPaperReconciliationResult:
    def test_construction(self):
        r = PaperReconciliationResult(
            portfolio_id="p1", as_of="2026-01-01", break_count=2, blocking_count=1, environment="paper"
        )
        assert r.break_count == 2
        assert r.blocking_count == 1


@pytest.mark.unit
class TestPaperReconciliationWorkflow:
    @pytest.mark.asyncio
    async def test_happy_path(self):
        acts, _ = _make_activities({"portfolio_id": "p1", "break_count": 0, "blocking_count": 0, "as_of": "2026-01-01", "environment": "paper"})
        async with await WorkflowEnvironment.start_local() as env:
            async with Worker(env.client, task_queue=TASK_QUEUE, activities=acts, workflows=[PaperReconciliationWorkflow]):
                result = await env.client.execute_workflow(
                    PaperReconciliationWorkflow.run,
                    PaperReconciliationInput(portfolio_id="p1", organization_id="o1", schedule_id="s1"),
                    id="test-paper-recon-1",
                    task_queue=TASK_QUEUE,
                )
        assert isinstance(result, PaperReconciliationResult)
        assert result.break_count == 0

    @pytest.mark.asyncio
    async def test_schedule_records(self):
        acts, captured = _make_activities({"portfolio_id": "p1", "break_count": 0, "blocking_count": 0, "as_of": "2026-01-01", "environment": "paper"})
        async with await WorkflowEnvironment.start_local() as env:
            async with Worker(env.client, task_queue=TASK_QUEUE, activities=acts, workflows=[PaperReconciliationWorkflow]):
                await env.client.execute_workflow(
                    PaperReconciliationWorkflow.run,
                    PaperReconciliationInput(portfolio_id="p1", organization_id="o1", schedule_id="s1"),
                    id="test-paper-recon-2",
                    task_queue=TASK_QUEUE,
                )
        statuses = [e["status"] for e in captured]
        assert statuses == ["running", "completed"]

    @pytest.mark.asyncio
    async def test_exception_records_failure(self):
        @activity.defn(name="reconcile_paper_portfolio")
        async def failing(portfolio_id: str, organization_id: str, as_of: str) -> dict[str, Any]:
            raise RuntimeError("recon error")

        @activity.defn(name="record_schedule_run")
        async def fake_record(input: dict) -> None:
            captured.append(input)

        captured: list[dict[str, Any]] = []
        acts = [failing, fake_record]
        async with await WorkflowEnvironment.start_local() as env:
            async with Worker(env.client, task_queue=TASK_QUEUE, activities=acts, workflows=[PaperReconciliationWorkflow]):
                with pytest.raises(WorkflowFailureError):
                    await env.client.execute_workflow(
                        PaperReconciliationWorkflow.run,
                        PaperReconciliationInput(portfolio_id="p1", organization_id="o1", schedule_id="s1"),
                        id="test-paper-recon-3",
                        task_queue=TASK_QUEUE,
                    )
        assert captured[1]["status"] == "failed"
