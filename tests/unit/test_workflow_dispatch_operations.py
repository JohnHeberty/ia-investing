"""Unit tests for workflows._dispatch_operations — DispatchOperationsWorkflow."""

from __future__ import annotations

from typing import Any

import pytest
from temporalio import activity
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from workflows._dispatch_operations import DispatchOperationsWorkflow

TASK_QUEUE = "test-dispatch-ops"


def _make_dispatch_activities(dispatch_result: dict[str, int] | None = None):
    captured_record: list[dict[str, Any]] = []

    @activity.defn(name="dispatch_pending_operations")
    async def fake_dispatch(input: dict) -> dict[str, int]:
        return dispatch_result or {}

    @activity.defn(name="record_schedule_run")
    async def fake_record(input: dict) -> None:
        captured_record.append(input)

    return [fake_dispatch, fake_record], captured_record


@pytest.mark.unit
class TestDispatchOperationsWorkflow:
    @pytest.mark.asyncio
    async def test_happy_path_no_schedule(self):
        acts, record = _make_dispatch_activities(dispatch_result={"dispatched": 5, "failed": 0})

        async with await WorkflowEnvironment.start_local() as env:
            async with Worker(env.client, task_queue=TASK_QUEUE, activities=acts, workflows=[DispatchOperationsWorkflow]):
                result = await env.client.execute_workflow(
                    DispatchOperationsWorkflow.run,
                    None,
                    id="test-dispatch-1",
                    task_queue=TASK_QUEUE,
                )

        assert result == {"dispatched": 5, "failed": 0}

    @pytest.mark.asyncio
    async def test_happy_path_with_command(self):
        acts, record = _make_dispatch_activities(dispatch_result={"dispatched": 10})

        async with await WorkflowEnvironment.start_local() as env:
            async with Worker(env.client, task_queue=TASK_QUEUE, activities=acts, workflows=[DispatchOperationsWorkflow]):
                result = await env.client.execute_workflow(
                    DispatchOperationsWorkflow.run,
                    {"batch_size": 100},
                    id="test-dispatch-2",
                    task_queue=TASK_QUEUE,
                )

        assert result == {"dispatched": 10}

    @pytest.mark.asyncio
    async def test_schedule_id_records_run(self):
        acts, record = _make_dispatch_activities(dispatch_result={"dispatched": 3})

        async with await WorkflowEnvironment.start_local() as env:
            async with Worker(env.client, task_queue=TASK_QUEUE, activities=acts, workflows=[DispatchOperationsWorkflow]):
                await env.client.execute_workflow(
                    DispatchOperationsWorkflow.run,
                    {"batch_size": 50, "schedule_id": "sch-42"},
                    id="test-dispatch-3",
                    task_queue=TASK_QUEUE,
                )

        assert len(record) == 1
        assert record[0]["schedule_id"] == "sch-42"
        assert record[0]["status"] == "completed"

    @pytest.mark.asyncio
    async def test_no_schedule_id_skips_record(self):
        acts, record = _make_dispatch_activities(dispatch_result={"dispatched": 0})

        async with await WorkflowEnvironment.start_local() as env:
            async with Worker(env.client, task_queue=TASK_QUEUE, activities=acts, workflows=[DispatchOperationsWorkflow]):
                await env.client.execute_workflow(
                    DispatchOperationsWorkflow.run,
                    {"batch_size": 50},
                    id="test-dispatch-4",
                    task_queue=TASK_QUEUE,
                )

        assert record == []

    @pytest.mark.asyncio
    async def test_empty_command_uses_default(self):
        acts, record = _make_dispatch_activities(dispatch_result={})

        async with await WorkflowEnvironment.start_local() as env:
            async with Worker(env.client, task_queue=TASK_QUEUE, activities=acts, workflows=[DispatchOperationsWorkflow]):
                await env.client.execute_workflow(
                    DispatchOperationsWorkflow.run,
                    {},
                    id="test-dispatch-5",
                    task_queue=TASK_QUEUE,
                )

        assert record == []
