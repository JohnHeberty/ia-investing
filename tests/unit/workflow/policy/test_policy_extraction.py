"""Unit tests for policy extraction activities and PolicyCollectionWorkflow."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from temporalio import activity
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from workflows._policy_event import (
    PolicyCollectionInput,
    PolicyCollectionResult,
    PolicyCollectionWorkflow,
    PolicyEventInput,
    PolicyEventResult,
    PolicyEventWorkflow,
)
from workflows._schedule_run import _format_error_chain

TASK_QUEUE = "test-policy-collection"


# ---------------------------------------------------------------------------
# Dataclass contract tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestPolicyCollectionInput:
    def test_defaults(self):
        inp = PolicyCollectionInput(authority="camara")
        assert inp.authority == "camara"
        assert inp.schedule_id == ""
        assert inp.since is None

    def test_custom_values(self):
        inp = PolicyCollectionInput(
            authority="senado",
            schedule_id="sch-1",
            since="2026-01-01T00:00:00Z",
        )
        assert inp.schedule_id == "sch-1"
        assert inp.since == "2026-01-01T00:00:00Z"

    def test_frozen(self):
        inp = PolicyCollectionInput(authority="camara")
        with pytest.raises(AttributeError):
            inp.authority = "senado"  # type: ignore[misc]

    def test_equality(self):
        a = PolicyCollectionInput(authority="camara")
        b = PolicyCollectionInput(authority="camara")
        assert a == b

    def test_inequality(self):
        a = PolicyCollectionInput(authority="camara")
        b = PolicyCollectionInput(authority="senado")
        assert a != b


@pytest.mark.unit
class TestPolicyCollectionResult:
    def test_defaults(self):
        res = PolicyCollectionResult(authority="camara")
        assert res.fetched == 0
        assert res.ingested == 0
        assert res.status == "completed"

    def test_custom_values(self):
        res = PolicyCollectionResult(authority="senado", fetched=10, ingested=8)
        assert res.fetched == 10
        assert res.ingested == 8

    def test_frozen(self):
        res = PolicyCollectionResult(authority="camara")
        with pytest.raises(AttributeError):
            res.fetched = 5  # type: ignore[misc]


# ---------------------------------------------------------------------------
# PolicyEventWorkflow tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestPolicyEventWorkflow:
    def test_input_validation(self):
        inp = PolicyEventInput(
            policy_object_id="obj-1",
            version=1,
            input_sha256="a" * 64,
            material=False,
            review_timeout_seconds=0,
        )
        assert inp.review_timeout_seconds == 0

    def test_result_defaults(self):
        res = PolicyEventResult(policy_object_id="obj-1", version=1, decision="approved")
        assert res.thesis_changed is False


# ---------------------------------------------------------------------------
# Activity tests (mocked connectors / services)
# ---------------------------------------------------------------------------


def _make_fetch_activities(
    fetch_result: dict[str, Any] | None = None,
):
    @activity.defn(name="fetch_policy_objects")
    async def fake_fetch(input: dict) -> dict[str, Any]:
        return fetch_result or {"authority": input["authority"], "count": 0, "records": []}

    return [fake_fetch]


def _make_ingest_activities(
    ingest_result: dict[str, Any] | None = None,
):
    @activity.defn(name="ingest_policy_objects")
    async def fake_ingest(input: dict) -> dict[str, Any]:
        return ingest_result or {"authority": input["authority"], "ingested": 0}

    return [fake_ingest]


def _make_schedule_activities(captured: list[dict[str, Any]] | None = None):
    _captured = captured if captured is not None else []

    @activity.defn(name="record_schedule_run")
    async def fake_record(input: dict) -> str:
        _captured.append(input)
        return "recorded"

    return [fake_record], _captured


@pytest.mark.unit
class TestFetchPolicyObjectsActivity:
    @pytest.mark.asyncio
    async def test_unsupported_authority_raises(self):
        from ia_investing.orchestration.activities.policy_extraction import fetch_policy_objects

        with patch(
            "ia_investing.orchestration.activities.policy_extraction.OfficialPolicyClient",
            new_callable=MagicMock,
        ):
            with pytest.raises(ValueError, match="unsupported authority"):
                await fetch_policy_objects({"authority": "invalid_authority"})

    @pytest.mark.asyncio
    async def test_camara_calls_correct_method(self):
        from ia_investing.orchestration.activities.policy_extraction import fetch_policy_objects

        mock_record = MagicMock()
        mock_record.__dict__ = {"id": "1"}
        mock_client = MagicMock()
        mock_client.camara_proposals = AsyncMock(return_value=(MagicMock(), [mock_record], None))

        with patch(
            "ia_investing.orchestration.activities.policy_extraction.OfficialPolicyClient",
            return_value=mock_client,
        ):
            result = await fetch_policy_objects({"authority": "camara", "since": None})

        assert result["authority"] == "camara"
        assert result["count"] == 1
        mock_client.camara_proposals.assert_awaited_once()
        call_kwargs = mock_client.camara_proposals.call_args.kwargs
        assert "start" in call_kwargs
        assert "end" in call_kwargs

    @pytest.mark.asyncio
    async def test_senado_calls_correct_method(self):
        from ia_investing.orchestration.activities.policy_extraction import fetch_policy_objects

        mock_client = MagicMock()
        mock_client.senado_matters_batch = AsyncMock(return_value=[{"id": "a"}, {"id": "b"}])

        with patch(
            "ia_investing.orchestration.activities.policy_extraction.OfficialPolicyClient",
            return_value=mock_client,
        ):
            result = await fetch_policy_objects({"authority": "senado"})

        assert result["count"] == 2
        mock_client.senado_matters_batch.assert_awaited_once_with(since=None)

    @pytest.mark.asyncio
    async def test_dou_calls_correct_method(self):
        from ia_investing.orchestration.activities.policy_extraction import fetch_policy_objects

        mock_payload = MagicMock()
        mock_payload.model_dump.return_value = {"content": "dou act"}
        mock_client = MagicMock()
        mock_client.dou_acts_since = AsyncMock(return_value=[mock_payload])

        with patch(
            "ia_investing.orchestration.activities.policy_extraction.OfficialPolicyClient",
            return_value=mock_client,
        ):
            result = await fetch_policy_objects({"authority": "dou", "since": "2026-01-01"})

        assert result["count"] == 1
        assert result["records"][0]["type"] == "dou_act"
        assert result["records"][0]["payload"]["content"] == "dou act"


@pytest.mark.unit
class TestIngestPolicyObjectsActivity:
    @pytest.mark.asyncio
    async def test_happy_path(self):
        from ia_investing.orchestration.activities.policy_extraction import ingest_policy_objects

        mock_service = AsyncMock()
        mock_service.ingest = AsyncMock(return_value=(MagicMock(), MagicMock(), True))

        mock_session = AsyncMock()

        with patch(
            "ia_investing.orchestration.activities.policy_extraction.session_scope"
        ) as mock_scope:
            mock_scope.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_scope.return_value.__aexit__ = AsyncMock(return_value=False)
            with patch(
                "ia_investing.orchestration.activities.policy_extraction.PolicyIngestionService",
                return_value=mock_service,
            ):
                result = await ingest_policy_objects(
                    {
                        "authority": "camara",
                        "records": [
                            {
                                "object_type": "proposta",
                                "external_id": "ext-1",
                                "title": "Test Proposal",
                                "text_content": "content",
                                "metadata": {},
                                "published_at": datetime.now(timezone.utc),
                                "source_object_version_id": "00000000-0000-0000-0000-000000000001",
                            }
                        ],
                    }
                )

        assert result["authority"] == "camara"
        assert result["ingested"] == 1
        mock_service.ingest.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_partial_failure(self):
        from ia_investing.orchestration.activities.policy_extraction import ingest_policy_objects

        mock_service = AsyncMock()
        call_count = 0

        async def side_effect(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return (MagicMock(), MagicMock(), True)
            raise ValueError("duplicate")

        mock_service.ingest = AsyncMock(side_effect=side_effect)

        mock_session = AsyncMock()

        with patch(
            "ia_investing.orchestration.activities.policy_extraction.session_scope"
        ) as mock_scope:
            mock_scope.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_scope.return_value.__aexit__ = AsyncMock(return_value=False)
            with patch(
                "ia_investing.orchestration.activities.policy_extraction.PolicyIngestionService",
                return_value=mock_service,
            ):
                result = await ingest_policy_objects(
                    {
                        "authority": "senado",
                        "records": [
                            {
                                "object_type": "projeto",
                                "external_id": "ext-1",
                                "title": "First",
                                "text_content": "c1",
                                "metadata": {},
                                "published_at": datetime.now(timezone.utc),
                                "source_object_version_id": "00000000-0000-0000-0000-000000000002",
                            },
                            {
                                "object_type": "projeto",
                                "external_id": "ext-2",
                                "title": "Second",
                                "text_content": "c2",
                                "metadata": {},
                                "published_at": datetime.now(timezone.utc),
                                "source_object_version_id": "00000000-0000-0000-0000-000000000003",
                            },
                        ],
                    }
                )

        assert result["ingested"] == 1
        assert mock_service.ingest.await_count == 2


# ---------------------------------------------------------------------------
# Workflow tests (using Temporal test environment)
# ---------------------------------------------------------------------------


def _build_policy_collection_activities(
    fetch_result: dict[str, Any] | None = None,
    ingest_result: dict[str, Any] | None = None,
):
    captured: list[dict[str, Any]] = []

    @activity.defn(name="fetch_policy_objects")
    async def fake_fetch(input: dict) -> dict[str, Any]:
        return fetch_result or {"authority": input["authority"], "count": 0, "records": []}

    @activity.defn(name="ingest_policy_objects")
    async def fake_ingest(input: dict) -> dict[str, Any]:
        return ingest_result or {"authority": input["authority"], "ingested": 0}

    @activity.defn(name="record_schedule_run")
    async def fake_record(input: dict) -> str:
        captured.append(input)
        return "recorded"

    return [fake_fetch, fake_ingest, fake_record], captured


@pytest.mark.unit
@pytest.mark.skip(reason="Temporal sandbox import issue")
class TestPolicyCollectionWorkflow:
    @pytest.mark.asyncio
    async def test_happy_path(self):
        acts, _record = _build_policy_collection_activities(
            fetch_result={"authority": "camara", "count": 3, "records": [{"id": "1"}, {"id": "2"}, {"id": "3"}]},
            ingest_result={"authority": "camara", "ingested": 3},
        )

        async with await WorkflowEnvironment.start_local() as env:
            async with Worker(
                env.client, task_queue=TASK_QUEUE, activities=acts, workflows=[PolicyCollectionWorkflow]
            ):
                result = await env.client.execute_workflow(
                    PolicyCollectionWorkflow.run,
                    PolicyCollectionInput(authority="camara"),
                    id="test-policy-collection-1",
                    task_queue=TASK_QUEUE,
                )

        assert result.authority == "camara"
        assert result.fetched == 3
        assert result.ingested == 3
        assert result.status == "completed"

    @pytest.mark.asyncio
    async def test_fetch_failure_propagates(self):
        @activity.defn(name="fetch_policy_objects")
        async def failing_fetch(input: dict) -> dict[str, Any]:
            raise RuntimeError("connection refused")

        @activity.defn(name="ingest_policy_objects")
        async def never_called(input: dict) -> dict[str, Any]:
            raise AssertionError("should not be called")

        @activity.defn(name="record_schedule_run")
        async def fake_record(input: dict) -> str:
            return "recorded"

        acts = [failing_fetch, never_called, fake_record]

        async with await WorkflowEnvironment.start_local() as env:
            async with Worker(
                env.client, task_queue=TASK_QUEUE, activities=acts, workflows=[PolicyCollectionWorkflow]
            ):
                with pytest.raises(RuntimeError, match="connection refused"):
                    await env.client.execute_workflow(
                        PolicyCollectionWorkflow.run,
                        PolicyCollectionInput(authority="camara", schedule_id="sch-fail"),
                        id="test-policy-collection-fail-1",
                        task_queue=TASK_QUEUE,
                    )

    @pytest.mark.asyncio
    async def test_ingest_failure_propagates(self):
        @activity.defn(name="fetch_policy_objects")
        async def ok_fetch(input: dict) -> dict[str, Any]:
            return {"authority": input["authority"], "count": 1, "records": [{"id": "1"}]}

        @activity.defn(name="ingest_policy_objects")
        async def failing_ingest(input: dict) -> dict[str, Any]:
            raise ValueError("ingest failed")

        @activity.defn(name="record_schedule_run")
        async def fake_record(input: dict) -> str:
            return "recorded"

        acts = [ok_fetch, failing_ingest, fake_record]

        async with await WorkflowEnvironment.start_local() as env:
            async with Worker(
                env.client, task_queue=TASK_QUEUE, activities=acts, workflows=[PolicyCollectionWorkflow]
            ):
                with pytest.raises(ValueError, match="ingest failed"):
                    await env.client.execute_workflow(
                        PolicyCollectionWorkflow.run,
                        PolicyCollectionInput(authority="senado"),
                        id="test-policy-collection-fail-2",
                        task_queue=TASK_QUEUE,
                    )

    @pytest.mark.asyncio
    async def test_schedule_id_triggers_record(self):
        acts, record = _build_policy_collection_activities(
            fetch_result={"authority": "dou", "count": 1, "records": [{"id": "1"}]},
            ingest_result={"authority": "dou", "ingested": 1},
        )

        async with await WorkflowEnvironment.start_local() as env:
            async with Worker(
                env.client, task_queue=TASK_QUEUE, activities=acts, workflows=[PolicyCollectionWorkflow]
            ):
                await env.client.execute_workflow(
                    PolicyCollectionWorkflow.run,
                    PolicyCollectionInput(authority="dou", schedule_id="sch-dou-1"),
                    id="test-policy-collection-2",
                    task_queue=TASK_QUEUE,
                )

        assert len(record) == 2
        assert [entry["status"] for entry in record] == ["running", "completed"]
        assert {entry["schedule_id"] for entry in record} == {"sch-dou-1"}

    @pytest.mark.asyncio
    async def test_no_schedule_id_skips_record(self):
        acts, record = _build_policy_collection_activities(
            fetch_result={"authority": "camara", "count": 0, "records": []},
            ingest_result={"authority": "camara", "ingested": 0},
        )

        async with await WorkflowEnvironment.start_local() as env:
            async with Worker(
                env.client, task_queue=TASK_QUEUE, activities=acts, workflows=[PolicyCollectionWorkflow]
            ):
                await env.client.execute_workflow(
                    PolicyCollectionWorkflow.run,
                    PolicyCollectionInput(authority="camara"),
                    id="test-policy-collection-3",
                    task_queue=TASK_QUEUE,
                )

        assert record == []

    @pytest.mark.asyncio
    async def test_empty_records(self):
        acts, _record = _build_policy_collection_activities(
            fetch_result={"authority": "camara", "count": 0, "records": []},
            ingest_result={"authority": "camara", "ingested": 0},
        )

        async with await WorkflowEnvironment.start_local() as env:
            async with Worker(
                env.client, task_queue=TASK_QUEUE, activities=acts, workflows=[PolicyCollectionWorkflow]
            ):
                result = await env.client.execute_workflow(
                    PolicyCollectionWorkflow.run,
                    PolicyCollectionInput(authority="camara"),
                    id="test-policy-collection-4",
                    task_queue=TASK_QUEUE,
                )

        assert result.fetched == 0
        assert result.ingested == 0


# ---------------------------------------------------------------------------
# Schedule definition tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestPolicyCollectionScheduleDefinition:
    def test_creates_schedule_with_defaults(self):
        from apps.scheduler.temporal_schedules import policy_collection_schedule_definition

        defn = policy_collection_schedule_definition(authority="camara")
        assert defn.schedule_id == "policy-collection-camara"

    def test_creates_schedule_for_senado(self):
        from apps.scheduler.temporal_schedules import policy_collection_schedule_definition

        defn = policy_collection_schedule_definition(authority="senado")
        assert defn.schedule_id == "policy-collection-senado"

    def test_creates_schedule_for_dou(self):
        from apps.scheduler.temporal_schedules import policy_collection_schedule_definition

        defn = policy_collection_schedule_definition(authority="dou")
        assert defn.schedule_id == "policy-collection-dou"

    def test_empty_authority_raises(self):
        from apps.scheduler.temporal_schedules import policy_collection_schedule_definition

        with pytest.raises(ValueError, match="authority is required"):
            policy_collection_schedule_definition(authority="")

    def test_custom_interval(self):
        from apps.scheduler.temporal_schedules import policy_collection_schedule_definition

        defn = policy_collection_schedule_definition(authority="camara", every=timedelta(hours=12))
        assert defn.schedule_id == "policy-collection-camara"

    def test_zero_interval_raises(self):
        from apps.scheduler.temporal_schedules import policy_collection_schedule_definition

        with pytest.raises(ValueError, match="schedule interval must be positive"):
            policy_collection_schedule_definition(authority="camara", every=timedelta(0))


# ---------------------------------------------------------------------------
# Registry tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestPolicyRegistryWiring:
    def test_research_agents_has_policy_workflow(self):
        from ia_investing.orchestration.registry import CAPABILITIES

        research = CAPABILITIES["research-agents"]
        workflow_names = [w.__name__ for w in research.workflows]
        assert "PolicyCollectionWorkflow" in workflow_names
        assert "PolicyEventWorkflow" in workflow_names

    def test_research_agents_has_policy_activities(self):
        from ia_investing.orchestration.registry import CAPABILITIES

        research = CAPABILITIES["research-agents"]
        activity_names = [getattr(a, "__name__", getattr(a, "name", str(a))) for a in research.activities]
        assert "fetch_policy_objects" in activity_names
        assert "ingest_policy_objects" in activity_names


# ---------------------------------------------------------------------------
# Settings tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestPolicySchedulerSettings:
    def test_default_authorities(self):
        from ia_investing.settings import SchedulerSettings

        settings = SchedulerSettings()
        assert settings.policy_authorities == ["camara", "senado", "dou"]

    def test_default_interval(self):
        from ia_investing.settings import SchedulerSettings

        settings = SchedulerSettings()
        assert settings.policy_collection_interval_hours == 6

    def test_custom_authorities(self):
        from ia_investing.settings import SchedulerSettings

        settings = SchedulerSettings(policy_authorities=["camara"], policy_collection_interval_hours=12)
        assert settings.policy_authorities == ["camara"]
        assert settings.policy_collection_interval_hours == 12


# ---------------------------------------------------------------------------
# Schedule policy tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestManagedSchedulePrefix:
    def test_policy_collection_is_managed(self):
        from apps.scheduler.policy import is_managed_schedule_id

        assert is_managed_schedule_id("policy-collection-camara") is True
        assert is_managed_schedule_id("policy-collection-senado") is True
        assert is_managed_schedule_id("policy-collection-dou") is True

    def test_non_policy_not_managed(self):
        from apps.scheduler.policy import is_managed_schedule_id

        assert is_managed_schedule_id("policy-collection-unknown-authority") is True
        assert is_managed_schedule_id("random-schedule") is False
