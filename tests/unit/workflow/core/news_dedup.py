"""Unit tests for workflows._news_dedup — NewsDedupWorkflow."""

from __future__ import annotations

from typing import Any

import pytest
from temporalio import activity
from temporalio.client import WorkflowFailureError
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from workflows._news_dedup import NewsDedupInput, NewsDedupWorkflow

TASK_QUEUE = "test-news-dedup"


def _make_activities(dedup_result: dict[str, int] | None = None):
    captured: list[dict[str, Any]] = []

    @activity.defn(name="deduplicate_recent_events")
    async def fake_dedup(input: dict) -> dict[str, int]:
        return dedup_result or {"deduplicated": 0}

    @activity.defn(name="record_schedule_run")
    async def fake_record(input: dict) -> None:
        captured.append(input)

    return [fake_dedup, fake_record], captured


@pytest.mark.unit
class TestNewsDedupInput:
    def test_defaults(self):
        inp = NewsDedupInput(schedule_id="sch-1")
        assert inp.lookback_hours == 24
        assert inp.batch_size == 500

    def test_custom(self):
        inp = NewsDedupInput(schedule_id="sch-2", lookback_hours=48, batch_size=100)
        assert inp.lookback_hours == 48
        assert inp.batch_size == 100

    def test_frozen(self):
        inp = NewsDedupInput(schedule_id="sch-1")
        with pytest.raises(AttributeError):
            inp.schedule_id = "x"  # type: ignore[misc]


@pytest.mark.unit
@pytest.mark.skip(reason="Temporal sandbox import issue")
class TestNewsDedupWorkflow:
    @pytest.mark.asyncio
    async def test_happy_path(self):
        acts, _ = _make_activities({"deduplicated": 5})
        async with await WorkflowEnvironment.start_local() as env:
            async with Worker(env.client, task_queue=TASK_QUEUE, activities=acts, workflows=[NewsDedupWorkflow]):
                result = await env.client.execute_workflow(
                    NewsDedupWorkflow.run,
                    NewsDedupInput(schedule_id="sch-1"),
                    id="test-news-dedup-1",
                    task_queue=TASK_QUEUE,
                )
        assert result == {"deduplicated": 5}

    @pytest.mark.asyncio
    async def test_schedule_records(self):
        acts, captured = _make_activities({"deduplicated": 2})
        async with await WorkflowEnvironment.start_local() as env:
            async with Worker(env.client, task_queue=TASK_QUEUE, activities=acts, workflows=[NewsDedupWorkflow]):
                await env.client.execute_workflow(
                    NewsDedupWorkflow.run,
                    NewsDedupInput(schedule_id="sch-99"),
                    id="test-news-dedup-2",
                    task_queue=TASK_QUEUE,
                )
        assert len(captured) == 2
        assert [e["status"] for e in captured] == ["running", "completed"]
        assert all(e["schedule_id"] == "sch-99" for e in captured)

    @pytest.mark.asyncio
    async def test_no_schedule_skips_record(self):
        acts, captured = _make_activities()
        async with await WorkflowEnvironment.start_local() as env:
            async with Worker(env.client, task_queue=TASK_QUEUE, activities=acts, workflows=[NewsDedupWorkflow]):
                await env.client.execute_workflow(
                    NewsDedupWorkflow.run,
                    NewsDedupInput(schedule_id=""),
                    id="test-news-dedup-3",
                    task_queue=TASK_QUEUE,
                )
        assert captured == []

    @pytest.mark.asyncio
    async def test_exception_records_failure(self):
        @activity.defn(name="deduplicate_recent_events")
        async def failing_dedup(input: dict) -> dict[str, int]:
            raise RuntimeError("dedup failed")

        @activity.defn(name="record_schedule_run")
        async def fake_record(input: dict) -> None:
            captured.append(input)

        captured: list[dict[str, Any]] = []
        acts = [failing_dedup, fake_record]
        async with await WorkflowEnvironment.start_local() as env:
            async with Worker(env.client, task_queue=TASK_QUEUE, activities=acts, workflows=[NewsDedupWorkflow]):
                with pytest.raises(WorkflowFailureError):
                    await env.client.execute_workflow(
                        NewsDedupWorkflow.run,
                        NewsDedupInput(schedule_id="sch-err"),
                        id="test-news-dedup-4",
                        task_queue=TASK_QUEUE,
                    )
        assert len(captured) == 2
        assert captured[1]["status"] == "failed"
        assert "dedup failed" in captured[1]["error_message"]
