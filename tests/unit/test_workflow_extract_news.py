"""Unit tests for workflows._extract_news — ExtractNewsWorkflow."""

from __future__ import annotations

from typing import Any

import pytest
from temporalio import activity
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from workflows._extract_news import ExtractNewsInput, ExtractNewsWorkflow

TASK_QUEUE = "test-extract-news"


@pytest.mark.unit
class TestExtractNewsInput:
    def test_defaults(self):
        inp = ExtractNewsInput(issuer_id="PETR4")
        assert inp.issuer_id == "PETR4"
        assert inp.max_results == 20
        assert inp.analyze_limit == 10
        assert inp.organization_id == ""
        assert inp.schedule_id == ""

    def test_custom_values(self):
        inp = ExtractNewsInput(
            issuer_id="VALE3", max_results=50, analyze_limit=20,
            organization_id="org-1", schedule_id="sch-1",
        )
        assert inp.max_results == 50
        assert inp.analyze_limit == 20

    def test_frozen(self):
        inp = ExtractNewsInput(issuer_id="PETR4")
        with pytest.raises(AttributeError):
            inp.issuer_id = "VALE3"  # type: ignore[misc]

    def test_equality(self):
        a = ExtractNewsInput(issuer_id="PETR4")
        b = ExtractNewsInput(issuer_id="PETR4")
        assert a == b


def _make_extract_activities(
    fetch_result: Any = None,
    analyze_result: Any = None,
):
    captured_record: list[dict[str, Any]] = []

    @activity.defn(name="fetch_news_items")
    async def fake_fetch(input: dict) -> Any:
        return fetch_result if fetch_result is not None else {}

    @activity.defn(name="batch_analyze_news")
    async def fake_analyze(input: dict) -> Any:
        return analyze_result if analyze_result is not None else {}

    @activity.defn(name="record_schedule_run")
    async def fake_record(input: dict) -> None:
        captured_record.append(input)

    return [fake_fetch, fake_analyze, fake_record], captured_record


@pytest.mark.unit
class TestExtractNewsWorkflow:
    @pytest.mark.asyncio
    async def test_happy_path_dict_fetched(self):
        acts, record = _make_extract_activities(
            fetch_result={"items": [{"title": "News 1"}, {"title": "News 2"}]},
            analyze_result={"analyzed": 2, "results": [{"impact": "high"}]},
        )

        async with await WorkflowEnvironment.start_local() as env:
            async with Worker(env.client, task_queue=TASK_QUEUE, activities=acts, workflows=[ExtractNewsWorkflow]):
                result = await env.client.execute_workflow(
                    ExtractNewsWorkflow.run,
                    ExtractNewsInput(issuer_id="PETR4"),
                    id="test-extract-news-1",
                    task_queue=TASK_QUEUE,
                )

        assert result["issuer_id"] == "PETR4"
        assert result["fetched_count"] == 2
        assert result["analyzed_count"] == 2
        assert result["results"] == [{"impact": "high"}]

    @pytest.mark.asyncio
    async def test_list_fetched_count(self):
        acts, record = _make_extract_activities(
            fetch_result=[{"title": "A"}, {"title": "B"}, {"title": "C"}],
            analyze_result={"analyzed": 3, "results": []},
        )

        async with await WorkflowEnvironment.start_local() as env:
            async with Worker(env.client, task_queue=TASK_QUEUE, activities=acts, workflows=[ExtractNewsWorkflow]):
                result = await env.client.execute_workflow(
                    ExtractNewsWorkflow.run,
                    ExtractNewsInput(issuer_id="VALE3"),
                    id="test-extract-news-2",
                    task_queue=TASK_QUEUE,
                )

        assert result["fetched_count"] == 3

    @pytest.mark.asyncio
    async def test_non_dict_non_list_fetched(self):
        acts, record = _make_extract_activities(
            fetch_result="unexpected",
            analyze_result={"analyzed": 0, "results": []},
        )

        async with await WorkflowEnvironment.start_local() as env:
            async with Worker(env.client, task_queue=TASK_QUEUE, activities=acts, workflows=[ExtractNewsWorkflow]):
                result = await env.client.execute_workflow(
                    ExtractNewsWorkflow.run,
                    ExtractNewsInput(issuer_id="ITUB4"),
                    id="test-extract-news-3",
                    task_queue=TASK_QUEUE,
                )

        assert result["fetched_count"] == 0

    @pytest.mark.asyncio
    async def test_non_dict_analysis(self):
        acts, record = _make_extract_activities(
            fetch_result={"items": []},
            analyze_result="not a dict",
        )

        async with await WorkflowEnvironment.start_local() as env:
            async with Worker(env.client, task_queue=TASK_QUEUE, activities=acts, workflows=[ExtractNewsWorkflow]):
                result = await env.client.execute_workflow(
                    ExtractNewsWorkflow.run,
                    ExtractNewsInput(issuer_id="BBDC4"),
                    id="test-extract-news-4",
                    task_queue=TASK_QUEUE,
                )

        assert result["analyzed_count"] == 0
        assert result["results"] == []

    @pytest.mark.asyncio
    async def test_schedule_id_triggers_record(self):
        acts, record = _make_extract_activities(
            fetch_result={"items": []},
            analyze_result={"analyzed": 0, "results": []},
        )

        async with await WorkflowEnvironment.start_local() as env:
            async with Worker(env.client, task_queue=TASK_QUEUE, activities=acts, workflows=[ExtractNewsWorkflow]):
                await env.client.execute_workflow(
                    ExtractNewsWorkflow.run,
                    ExtractNewsInput(issuer_id="PETR4", schedule_id="sch-123"),
                    id="test-extract-news-5",
                    task_queue=TASK_QUEUE,
                )

        assert len(record) == 1
        assert record[0]["schedule_id"] == "sch-123"
        assert record[0]["status"] == "completed"

    @pytest.mark.asyncio
    async def test_no_schedule_id_skips_record(self):
        acts, record = _make_extract_activities(
            fetch_result={"items": []},
            analyze_result={"analyzed": 0, "results": []},
        )

        async with await WorkflowEnvironment.start_local() as env:
            async with Worker(env.client, task_queue=TASK_QUEUE, activities=acts, workflows=[ExtractNewsWorkflow]):
                await env.client.execute_workflow(
                    ExtractNewsWorkflow.run,
                    ExtractNewsInput(issuer_id="PETR4"),
                    id="test-extract-news-6",
                    task_queue=TASK_QUEUE,
                )

        assert record == []

    @pytest.mark.asyncio
    async def test_empty_dict_fetched(self):
        acts, record = _make_extract_activities(
            fetch_result={},
            analyze_result={"analyzed": 0, "results": []},
        )

        async with await WorkflowEnvironment.start_local() as env:
            async with Worker(env.client, task_queue=TASK_QUEUE, activities=acts, workflows=[ExtractNewsWorkflow]):
                result = await env.client.execute_workflow(
                    ExtractNewsWorkflow.run,
                    ExtractNewsInput(issuer_id="PETR4"),
                    id="test-extract-news-7",
                    task_queue=TASK_QUEUE,
                )

        assert result["fetched_count"] == 0
