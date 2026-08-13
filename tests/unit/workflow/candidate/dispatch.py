"""Unit tests for workflows.candidate_dispatch — CandidateOutboxDispatchWorkflow."""

from __future__ import annotations

from typing import Any

import pytest
from temporalio import activity
from temporalio.client import WorkflowFailureError
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from workflows.candidate_dispatch import CandidateOutboxDispatchWorkflow

TASK_QUEUE = "test-candidate-dispatch"


def _make_activities(result: dict[str, int] | None = None):
    captured: list[dict[str, Any]] = []

    @activity.defn(name="dispatch_candidate_intelligence_events")
    async def fake_dispatch(input: dict) -> dict[str, int]:
        return result or {"dispatched": 0}

    @activity.defn(name="record_schedule_run")
    async def fake_record(input: dict) -> None:
        captured.append(input)

    return [fake_dispatch, fake_record], captured


@pytest.mark.unit
@pytest.mark.skip(reason="Temporal sandbox import issue")
class TestCandidateOutboxDispatchWorkflow:
    @pytest.mark.asyncio
    async def test_happy_path_with_command(self):
        acts, _ = _make_activities({"dispatched": 3})
        async with await WorkflowEnvironment.start_local() as env:
            async with Worker(env.client, task_queue=TASK_QUEUE, activities=acts, workflows=[CandidateOutboxDispatchWorkflow]):
                result = await env.client.execute_workflow(
                    CandidateOutboxDispatchWorkflow.run,
                    {"schedule_id": "sch-1", "batch_size": 50},
                    id="test-cand-disp-1",
                    task_queue=TASK_QUEUE,
                )
        assert result == {"dispatched": 3}

    @pytest.mark.asyncio
    async def test_none_command(self):
        acts, _ = _make_activities({"dispatched": 0})
        async with await WorkflowEnvironment.start_local() as env:
            async with Worker(env.client, task_queue=TASK_QUEUE, activities=acts, workflows=[CandidateOutboxDispatchWorkflow]):
                result = await env.client.execute_workflow(
                    CandidateOutboxDispatchWorkflow.run,
                    None,
                    id="test-cand-disp-2",
                    task_queue=TASK_QUEUE,
                )
        assert result == {"dispatched": 0}

    @pytest.mark.asyncio
    async def test_schedule_records(self):
        acts, captured = _make_activities({"dispatched": 1})
        async with await WorkflowEnvironment.start_local() as env:
            async with Worker(env.client, task_queue=TASK_QUEUE, activities=acts, workflows=[CandidateOutboxDispatchWorkflow]):
                await env.client.execute_workflow(
                    CandidateOutboxDispatchWorkflow.run,
                    {"schedule_id": "sch-42"},
                    id="test-cand-disp-3",
                    task_queue=TASK_QUEUE,
                )
        assert len(captured) == 2
        assert [e["status"] for e in captured] == ["running", "completed"]
        assert all(e["schedule_id"] == "sch-42" for e in captured)

    @pytest.mark.asyncio
    async def test_no_schedule_skips_record(self):
        acts, captured = _make_activities()
        async with await WorkflowEnvironment.start_local() as env:
            async with Worker(env.client, task_queue=TASK_QUEUE, activities=acts, workflows=[CandidateOutboxDispatchWorkflow]):
                await env.client.execute_workflow(
                    CandidateOutboxDispatchWorkflow.run,
                    {},
                    id="test-cand-disp-4",
                    task_queue=TASK_QUEUE,
                )
        assert captured == []

    @pytest.mark.asyncio
    async def test_exception_records_failure(self):
        @activity.defn(name="dispatch_candidate_intelligence_events")
        async def failing(input: dict) -> dict[str, int]:
            raise RuntimeError("dispatch boom")

        @activity.defn(name="record_schedule_run")
        async def fake_record(input: dict) -> None:
            captured.append(input)

        captured: list[dict[str, Any]] = []
        acts = [failing, fake_record]
        async with await WorkflowEnvironment.start_local() as env:
            async with Worker(env.client, task_queue=TASK_QUEUE, activities=acts, workflows=[CandidateOutboxDispatchWorkflow]):
                with pytest.raises(WorkflowFailureError):
                    await env.client.execute_workflow(
                        CandidateOutboxDispatchWorkflow.run,
                        {"schedule_id": "sch-err"},
                        id="test-cand-disp-5",
                        task_queue=TASK_QUEUE,
                    )
        assert captured[1]["status"] == "failed"
        assert "dispatch boom" in captured[1]["error_message"]
