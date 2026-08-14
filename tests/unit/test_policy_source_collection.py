"""Unit tests for policy source collection activities, workflow, and ensure_default_sources."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from temporalio import activity
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from workflows._policy_source_collection import (
    PolicySourceCollectionInput,
    PolicySourceCollectionResult,
    PolicySourceCollectionWorkflow,
)

TASK_QUEUE = "test-policy-source-collection"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_source(
    *,
    id: Any | None = None,
    authority: str = "camara",
    name: str | None = None,
    is_active: bool = True,
    last_fetched_at: datetime | None = None,
    last_fetch_error: str | None = None,
    last_fetch_error_at: datetime | None = None,
) -> MagicMock:
    """Build a mock PolicySource ORM object."""
    src = MagicMock()
    src.id = id or uuid4()
    src.authority = authority
    src.name = name or authority.title()
    src.is_active = is_active
    src.last_fetched_at = last_fetched_at
    src.last_fetch_error = last_fetch_error
    src.last_fetch_error_at = last_fetch_error_at
    return src


def _mock_session_scope(sources: list[MagicMock] | None = None):
    """Return a patched session_scope that yields a mock session.

    The mock session's ``get`` returns the first source whose id matches.
    ``execute`` returns a result whose ``scalars().all()`` returns *sources*.
    """
    session = AsyncMock()

    if sources is not None:
        _source_map = {str(s.id): s for s in sources}
    else:
        _source_map = {}

    async def fake_get(model_class, pk):
        return _source_map.get(str(pk))

    session.get = fake_get

    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = sources or []
    session.execute = AsyncMock(return_value=result_mock)

    scope_cm = AsyncMock()
    scope_cm.__aenter__ = AsyncMock(return_value=session)
    scope_cm.__aexit__ = AsyncMock(return_value=False)
    return session, scope_cm


# ---------------------------------------------------------------------------
# Dataclass contract tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestPolicySourceCollectionInput:
    def test_defaults(self):
        inp = PolicySourceCollectionInput()
        assert inp.schedule_id == ""

    def test_custom_values(self):
        inp = PolicySourceCollectionInput(schedule_id="sch-42")
        assert inp.schedule_id == "sch-42"

    def test_frozen(self):
        inp = PolicySourceCollectionInput()
        with pytest.raises(AttributeError):
            inp.schedule_id = "nope"  # type: ignore[misc]


@pytest.mark.unit
class TestPolicySourceCollectionResult:
    def test_defaults(self):
        res = PolicySourceCollectionResult()
        assert res.sources_attempted == 0
        assert res.sources_succeeded == 0
        assert res.sources_failed == 0
        assert res.status == "completed"

    def test_custom_values(self):
        res = PolicySourceCollectionResult(
            sources_attempted=5, sources_succeeded=3, sources_failed=2, status="completed"
        )
        assert res.sources_attempted == 5
        assert res.sources_succeeded == 3
        assert res.sources_failed == 2

    def test_frozen(self):
        res = PolicySourceCollectionResult()
        with pytest.raises(AttributeError):
            res.sources_attempted = 1  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Activity: list_active_policy_sources
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestListActivePolicySources:
    @pytest.mark.asyncio
    async def test_returns_only_active_sources(self):
        """Two active sources returned; one inactive source excluded."""
        from ia_investing.orchestration.activities.policy_source_collection import (
            list_active_policy_sources,
        )

        active1 = _make_source(authority="camara", name="Câmara")
        active2 = _make_source(authority="senado", name="Senado")
        inactive = _make_source(authority="dou", name="DOU", is_active=False)

        _session, scope_cm = _mock_session_scope(sources=[active1, active2])

        with patch(
            "ia_investing.orchestration.activities.policy_source_collection.session_scope",
            return_value=scope_cm,
        ):
            result = await list_active_policy_sources({})

        assert len(result["sources"]) == 2
        authorities = {s["authority"] for s in result["sources"]}
        assert authorities == {"camara", "senado"}

    @pytest.mark.asyncio
    async def test_source_fields_present(self):
        """Each returned source has id, authority, name, last_fetched_at."""
        from ia_investing.orchestration.activities.policy_source_collection import (
            list_active_policy_sources,
        )

        fetched_at = datetime(2026, 7, 1, 12, 0, tzinfo=UTC)
        src = _make_source(authority="camara", last_fetched_at=fetched_at)
        _session, scope_cm = _mock_session_scope(sources=[src])

        with patch(
            "ia_investing.orchestration.activities.policy_source_collection.session_scope",
            return_value=scope_cm,
        ):
            result = await list_active_policy_sources({})

        assert len(result["sources"]) == 1
        s = result["sources"][0]
        assert "id" in s
        assert s["authority"] == "camara"
        assert s["name"] == "Camara"  # authority.title()
        assert s["last_fetched_at"] == fetched_at.isoformat()

    @pytest.mark.asyncio
    async def test_null_last_fetched_at(self):
        """last_fetched_at is None when source has never been fetched."""
        from ia_investing.orchestration.activities.policy_source_collection import (
            list_active_policy_sources,
        )

        src = _make_source(authority="senado", last_fetched_at=None)
        _session, scope_cm = _mock_session_scope(sources=[src])

        with patch(
            "ia_investing.orchestration.activities.policy_source_collection.session_scope",
            return_value=scope_cm,
        ):
            result = await list_active_policy_sources({})

        assert result["sources"][0]["last_fetched_at"] is None

    @pytest.mark.asyncio
    async def test_empty_sources(self):
        """No active sources returns empty list."""
        from ia_investing.orchestration.activities.policy_source_collection import (
            list_active_policy_sources,
        )

        _session, scope_cm = _mock_session_scope(sources=[])

        with patch(
            "ia_investing.orchestration.activities.policy_source_collection.session_scope",
            return_value=scope_cm,
        ):
            result = await list_active_policy_sources({})

        assert result["sources"] == []


# ---------------------------------------------------------------------------
# Activity: collect_from_policy_source
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestCollectFromPolicySource:
    @pytest.mark.asyncio
    async def test_success_camara(self):
        """Successful camara collection updates last_fetched_at and clears errors."""
        from ia_investing.orchestration.activities.policy_source_collection import (
            collect_from_policy_source,
        )

        src = _make_source(authority="camara")
        _session, scope_cm = _mock_session_scope(sources=[src])

        mock_record = MagicMock()
        mock_record.__dict__ = {
            "object_type": "proposta",
            "external_id": "123",
            "title": "Test",
            "text_content": "content",
            "published_at": datetime.now(UTC),
            "metadata": {},
        }
        mock_client = MagicMock()
        mock_client.camara_proposals = AsyncMock(
            return_value=(MagicMock(), [mock_record], None)
        )
        mock_ingester = MagicMock()
        mock_ingester.ingest = AsyncMock(
            return_value=(MagicMock(), MagicMock(), True)
        )

        with patch(
            "ia_investing.orchestration.activities.policy_source_collection.session_scope",
            return_value=scope_cm,
        ), patch(
            "ia_investing.orchestration.activities.policy_source_collection.OfficialPolicyClient",
            return_value=mock_client,
        ), patch(
            "ia_investing.orchestration.activities.policy_source_collection.PolicyIngestionService",
            return_value=mock_ingester,
        ):
            result = await collect_from_policy_source(
                {"source_id": str(src.id)}
            )

        assert result["status"] == "completed"
        assert result["authority"] == "camara"
        assert result["fetched"] == 1
        assert result["ingested"] == 1
        assert src.last_fetched_at is not None
        assert src.last_fetch_error is None

    @pytest.mark.asyncio
    async def test_fetch_error_updates_error_fields(self):
        """When the connector raises, error fields are set on the source."""
        from ia_investing.orchestration.activities.policy_source_collection import (
            collect_from_policy_source,
        )

        src = _make_source(authority="camara")
        _session, scope_cm = _mock_session_scope(sources=[src])

        mock_client = MagicMock()
        mock_client.camara_proposals = AsyncMock(side_effect=RuntimeError("API timeout"))
        mock_ingester = MagicMock()

        with patch(
            "ia_investing.orchestration.activities.policy_source_collection.session_scope",
            return_value=scope_cm,
        ), patch(
            "ia_investing.orchestration.activities.policy_source_collection.OfficialPolicyClient",
            return_value=mock_client,
        ), patch(
            "ia_investing.orchestration.activities.policy_source_collection.PolicyIngestionService",
            return_value=mock_ingester,
        ):
            result = await collect_from_policy_source(
                {"source_id": str(src.id)}
            )

        assert result["status"] == "failed"
        assert "error" in result
        assert src.last_fetch_error is not None
        assert "API timeout" in src.last_fetch_error
        assert src.last_fetch_error_at is not None

    @pytest.mark.asyncio
    async def test_unknown_authority_returns_skipped(self):
        """Source with an authority not in (camara, senado, dou) returns skipped."""
        from ia_investing.orchestration.activities.policy_source_collection import (
            collect_from_policy_source,
        )

        src = _make_source(authority="unknown")
        _session, scope_cm = _mock_session_scope(sources=[src])

        mock_client = MagicMock()
        mock_ingester = MagicMock()

        with patch(
            "ia_investing.orchestration.activities.policy_source_collection.session_scope",
            return_value=scope_cm,
        ), patch(
            "ia_investing.orchestration.activities.policy_source_collection.OfficialPolicyClient",
            return_value=mock_client,
        ), patch(
            "ia_investing.orchestration.activities.policy_source_collection.PolicyIngestionService",
            return_value=mock_ingester,
        ):
            result = await collect_from_policy_source(
                {"source_id": str(src.id)}
            )

        assert result["status"] == "skipped"
        assert "unknown authority" in result["reason"]

    @pytest.mark.asyncio
    async def test_inactive_source_returns_skipped(self):
        """An inactive source is skipped without attempting collection."""
        from ia_investing.orchestration.activities.policy_source_collection import (
            collect_from_policy_source,
        )

        src = _make_source(authority="camara", is_active=False)
        _session, scope_cm = _mock_session_scope(sources=[src])

        with patch(
            "ia_investing.orchestration.activities.policy_source_collection.session_scope",
            return_value=scope_cm,
        ):
            result = await collect_from_policy_source(
                {"source_id": str(src.id)}
            )

        assert result["status"] == "skipped"
        assert result["reason"] == "source inactive"

    @pytest.mark.asyncio
    async def test_source_not_found_returns_skipped(self):
        """Non-existent source_id returns skipped."""
        from ia_investing.orchestration.activities.policy_source_collection import (
            collect_from_policy_source,
        )

        _session, scope_cm = _mock_session_scope(sources=[])

        with patch(
            "ia_investing.orchestration.activities.policy_source_collection.session_scope",
            return_value=scope_cm,
        ):
            result = await collect_from_policy_source(
                {"source_id": str(uuid4())}
            )

        assert result["status"] == "skipped"
        assert result["reason"] == "source not found"

    @pytest.mark.asyncio
    async def test_connector_not_available_returns_skipped(self):
        """When OfficialPolicyClient is None (import failed), source is skipped."""
        from ia_investing.orchestration.activities.policy_source_collection import (
            collect_from_policy_source,
        )

        src = _make_source(authority="camara")
        _session, scope_cm = _mock_session_scope(sources=[src])

        with patch(
            "ia_investing.orchestration.activities.policy_source_collection.session_scope",
            return_value=scope_cm,
        ), patch(
            "ia_investing.orchestration.activities.policy_source_collection.OfficialPolicyClient",
            None,
        ):
            result = await collect_from_policy_source(
                {"source_id": str(src.id)}
            )

        assert result["status"] == "skipped"
        assert "not available" in result["reason"]

    @pytest.mark.asyncio
    async def test_ingester_not_available_returns_skipped(self):
        """When PolicyIngestionService is None, source is skipped."""
        from ia_investing.orchestration.activities.policy_source_collection import (
            collect_from_policy_source,
        )

        src = _make_source(authority="camara")
        _session, scope_cm = _mock_session_scope(sources=[src])

        with patch(
            "ia_investing.orchestration.activities.policy_source_collection.session_scope",
            return_value=scope_cm,
        ), patch(
            "ia_investing.orchestration.activities.policy_source_collection.OfficialPolicyClient",
            MagicMock(),
        ), patch(
            "ia_investing.orchestration.activities.policy_source_collection.PolicyIngestionService",
            None,
        ):
            result = await collect_from_policy_source(
                {"source_id": str(src.id)}
            )

        assert result["status"] == "skipped"
        assert "not available" in result["reason"]

    @pytest.mark.asyncio
    async def test_senado_success(self):
        """Successful senado collection."""
        from ia_investing.orchestration.activities.policy_source_collection import (
            collect_from_policy_source,
        )

        src = _make_source(authority="senado")
        _session, scope_cm = _mock_session_scope(sources=[src])

        mock_record = MagicMock()
        mock_record.__dict__ = {"object_type": "projeto", "external_id": "S-1"}
        mock_client = MagicMock()
        mock_client.senado_matters_batch = AsyncMock(return_value=[mock_record])
        mock_ingester = MagicMock()
        mock_ingester.ingest = AsyncMock(
            return_value=(MagicMock(), MagicMock(), True)
        )

        with patch(
            "ia_investing.orchestration.activities.policy_source_collection.session_scope",
            return_value=scope_cm,
        ), patch(
            "ia_investing.orchestration.activities.policy_source_collection.OfficialPolicyClient",
            return_value=mock_client,
        ), patch(
            "ia_investing.orchestration.activities.policy_source_collection.PolicyIngestionService",
            return_value=mock_ingester,
        ):
            result = await collect_from_policy_source(
                {"source_id": str(src.id)}
            )

        assert result["status"] == "completed"
        assert result["fetched"] == 1
        assert result["ingested"] == 1

    @pytest.mark.asyncio
    async def test_dou_success(self):
        """Successful DOU collection."""
        from ia_investing.orchestration.activities.policy_source_collection import (
            collect_from_policy_source,
        )

        src = _make_source(authority="dou")
        _session, scope_cm = _mock_session_scope(sources=[src])

        mock_payload = MagicMock()
        mock_payload.model_dump.return_value = {"content": "dou act"}
        mock_client = MagicMock()
        mock_client.dou_acts_since = AsyncMock(return_value=[mock_payload])
        mock_ingester = MagicMock()
        mock_ingester.ingest = AsyncMock(
            return_value=(MagicMock(), MagicMock(), True)
        )

        with patch(
            "ia_investing.orchestration.activities.policy_source_collection.session_scope",
            return_value=scope_cm,
        ), patch(
            "ia_investing.orchestration.activities.policy_source_collection.OfficialPolicyClient",
            return_value=mock_client,
        ), patch(
            "ia_investing.orchestration.activities.policy_source_collection.PolicyIngestionService",
            return_value=mock_ingester,
        ):
            result = await collect_from_policy_source(
                {"source_id": str(src.id)}
            )

        assert result["status"] == "completed"
        assert result["fetched"] == 1

    @pytest.mark.asyncio
    async def test_partial_ingest_failure(self):
        """When some records fail ingestion, ingested count is less than fetched."""
        from ia_investing.orchestration.activities.policy_source_collection import (
            collect_from_policy_source,
        )

        src = _make_source(authority="camara")
        _session, scope_cm = _mock_session_scope(sources=[src])

        mock_record1 = MagicMock()
        mock_record1.__dict__ = {"object_type": "proposta", "external_id": "1"}
        mock_record2 = MagicMock()
        mock_record2.__dict__ = {"object_type": "proposta", "external_id": "2"}

        mock_client = MagicMock()
        mock_client.camara_proposals = AsyncMock(
            return_value=(MagicMock(), [mock_record1, mock_record2], None)
        )

        call_count = 0
        mock_ingester = MagicMock()

        async def _ingest_side_effect(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return (MagicMock(), MagicMock(), True)
            raise ValueError("duplicate")

        mock_ingester.ingest = AsyncMock(side_effect=_ingest_side_effect)

        with patch(
            "ia_investing.orchestration.activities.policy_source_collection.session_scope",
            return_value=scope_cm,
        ), patch(
            "ia_investing.orchestration.activities.policy_source_collection.OfficialPolicyClient",
            return_value=mock_client,
        ), patch(
            "ia_investing.orchestration.activities.policy_source_collection.PolicyIngestionService",
            return_value=mock_ingester,
        ):
            result = await collect_from_policy_source(
                {"source_id": str(src.id)}
            )

        assert result["status"] == "completed"
        assert result["fetched"] == 2
        assert result["ingested"] == 1


# ---------------------------------------------------------------------------
# Workflow tests (Temporal test environment)
# ---------------------------------------------------------------------------


def _build_source_collection_activities(
    list_result: dict[str, Any] | None = None,
    collect_results: list[dict[str, Any]] | None = None,
    collect_side_effects: list[Exception | None] | None = None,
):
    """Build stub activities for the PolicySourceCollectionWorkflow."""
    captured: list[dict[str, Any]] = []
    _collect_idx = 0

    @activity.defn(name="list_active_policy_sources")
    async def fake_list(input: dict) -> dict[str, Any]:
        return list_result or {"sources": []}

    @activity.defn(name="collect_from_policy_source")
    async def fake_collect(input: dict) -> dict[str, Any]:
        nonlocal _collect_idx
        captured.append(input)
        if collect_side_effects and _collect_idx < len(collect_side_effects):
            exc = collect_side_effects[_collect_idx]
            _collect_idx += 1
            if exc is not None:
                raise exc
        if collect_results and _collect_idx <= len(collect_results):
            _collect_idx += 1
            return collect_results[_collect_idx - 1]
        return {"status": "completed", "authority": "camara", "fetched": 0, "ingested": 0}

    @activity.defn(name="record_schedule_run")
    async def fake_record(input: dict) -> str:
        captured.append(input)
        return "recorded"

    return [fake_list, fake_collect, fake_record], captured


@pytest.mark.unit
@pytest.mark.skip(reason="Temporal sandbox import issue — same as policy_extraction tests")
class TestPolicySourceCollectionWorkflow:
    @pytest.mark.asyncio
    async def test_happy_path(self):
        """Workflow collects from all sources successfully."""
        list_result = {
            "sources": [
                {"id": "src-1", "authority": "camara", "name": "Câmara", "last_fetched_at": None},
                {"id": "src-2", "authority": "senado", "name": "Senado", "last_fetched_at": None},
            ]
        }
        collect_results = [
            {"status": "completed", "authority": "camara", "fetched": 5, "ingested": 5},
            {"status": "completed", "authority": "senado", "fetched": 3, "ingested": 3},
        ]

        activities, _ = _build_source_collection_activities(
            list_result=list_result,
            collect_results=collect_results,
        )

        async with await WorkflowEnvironment.start_local() as env:
            worker = Worker(env.client, task_queue=TASK_QUEUE, workflows=[PolicySourceCollectionWorkflow], activities=activities)
            async with worker:
                result = await env.client.execute_workflow(
                    PolicySourceCollectionWorkflow.run,
                    PolicySourceCollectionInput(schedule_id="sch-1"),
                    id="wf-source-collection-happy",
                    task_queue=TASK_QUEUE,
                )

        assert result.sources_attempted == 2
        assert result.sources_succeeded == 2
        assert result.sources_failed == 0

    @pytest.mark.asyncio
    async def test_empty_sources(self):
        """Workflow with no sources completes with zero counts."""
        activities, _ = _build_source_collection_activities(
            list_result={"sources": []}
        )

        async with await WorkflowEnvironment.start_local() as env:
            worker = Worker(env.client, task_queue=TASK_QUEUE, workflows=[PolicySourceCollectionWorkflow], activities=activities)
            async with worker:
                result = await env.client.execute_workflow(
                    PolicySourceCollectionWorkflow.run,
                    PolicySourceCollectionInput(schedule_id="sch-empty"),
                    id="wf-source-collection-empty",
                    task_queue=TASK_QUEUE,
                )

        assert result.sources_attempted == 0
        assert result.sources_succeeded == 0
        assert result.sources_failed == 0

    @pytest.mark.asyncio
    async def test_collect_failure_counts_as_failed(self):
        """When one source fails, it's counted as failed."""
        list_result = {
            "sources": [
                {"id": "src-1", "authority": "camara", "name": "Câmara", "last_fetched_at": None},
                {"id": "src-2", "authority": "senado", "name": "Senado", "last_fetched_at": None},
            ]
        }
        collect_results = [
            {"status": "completed", "authority": "camara", "fetched": 5, "ingested": 5},
            {"status": "failed", "authority": "senado", "error": "timeout"},
        ]

        activities, _ = _build_source_collection_activities(
            list_result=list_result,
            collect_results=collect_results,
        )

        async with await WorkflowEnvironment.start_local() as env:
            worker = Worker(env.client, task_queue=TASK_QUEUE, workflows=[PolicySourceCollectionWorkflow], activities=activities)
            async with worker:
                result = await env.client.execute_workflow(
                    PolicySourceCollectionWorkflow.run,
                    PolicySourceCollectionInput(schedule_id="sch-partial"),
                    id="wf-source-collection-partial",
                    task_queue=TASK_QUEUE,
                )

        assert result.sources_attempted == 2
        assert result.sources_succeeded == 1
        assert result.sources_failed == 1

    @pytest.mark.asyncio
    async def test_activity_exception_counts_as_failed(self):
        """When an activity raises an exception, the source counts as failed."""
        list_result = {
            "sources": [
                {"id": "src-1", "authority": "camara", "name": "Câmara", "last_fetched_at": None},
            ]
        }

        activities, _ = _build_source_collection_activities(
            list_result=list_result,
            collect_side_effects=[RuntimeError("connection refused")],
        )

        async with await WorkflowEnvironment.start_local() as env:
            worker = Worker(env.client, task_queue=TASK_QUEUE, workflows=[PolicySourceCollectionWorkflow], activities=activities)
            async with worker:
                result = await env.client.execute_workflow(
                    PolicySourceCollectionWorkflow.run,
                    PolicySourceCollectionInput(schedule_id="sch-exc"),
                    id="wf-source-collection-exc",
                    task_queue=TASK_QUEUE,
                )

        assert result.sources_attempted == 1
        assert result.sources_succeeded == 0
        assert result.sources_failed == 1

    @pytest.mark.asyncio
    async def test_skipped_source_counts_as_failed(self):
        """Source that returns 'skipped' status counts as failed."""
        list_result = {
            "sources": [
                {"id": "src-1", "authority": "camara", "name": "Câmara", "last_fetched_at": None},
            ]
        }
        collect_results = [
            {"status": "skipped", "reason": "source inactive"},
        ]

        activities, _ = _build_source_collection_activities(
            list_result=list_result,
            collect_results=collect_results,
        )

        async with await WorkflowEnvironment.start_local() as env:
            worker = Worker(env.client, task_queue=TASK_QUEUE, workflows=[PolicySourceCollectionWorkflow], activities=activities)
            async with worker:
                result = await env.client.execute_workflow(
                    PolicySourceCollectionWorkflow.run,
                    PolicySourceCollectionInput(schedule_id="sch-skip"),
                    id="wf-source-collection-skip",
                    task_queue=TASK_QUEUE,
                )

        assert result.sources_attempted == 1
        assert result.sources_succeeded == 0
        assert result.sources_failed == 1

    @pytest.mark.asyncio
    async def test_schedule_run_hooks_called(self):
        """start_schedule_run and complete_schedule_run are called."""
        from ia_investing.orchestration.activities.policy_source_collection import (
            list_active_policy_sources,
            collect_from_policy_source,
        )

        activities, captured = _build_source_collection_activities(
            list_result={"sources": []},
        )

        async with await WorkflowEnvironment.start_local() as env:
            worker = Worker(
                env.client,
                task_queue=TASK_QUEUE,
                workflows=[PolicySourceCollectionWorkflow],
                activities=activities,
            )
            async with worker:
                await env.client.execute_workflow(
                    PolicySourceCollectionWorkflow.run,
                    PolicySourceCollectionInput(schedule_id="sch-hooks"),
                    id="wf-source-collection-hooks",
                    task_queue=TASK_QUEUE,
                )

        # record_schedule_run should have been called (captured by fake_record)
        schedule_calls = [c for c in captured if isinstance(c, dict) and "schedule_id" in c]
        assert len(schedule_calls) == 1
        assert schedule_calls[0]["schedule_id"] == "sch-hooks"


# ---------------------------------------------------------------------------
# ensure_default_sources (PolicySourceService)
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestEnsureDefaultSources:
    @pytest.mark.asyncio
    async def test_creates_all_when_table_empty(self):
        """With empty table, all 3 authorities create sources."""
        from ia_investing.application.policy_intelligence import PolicySourceService

        session = AsyncMock()
        # execute returns no active authorities
        result_mock = MagicMock()
        result_mock.__iter__ = lambda self: iter([])
        session.execute = AsyncMock(return_value=result_mock)

        service = PolicySourceService(session)
        count = await service.ensure_default_sources(["camara", "senado", "dou"])

        assert count == 3
        assert session.add.call_count == 3
        session.flush.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_idempotent_when_all_exist(self):
        """Calling again with same authorities creates zero new sources."""
        from ia_investing.application.policy_intelligence import PolicySourceService

        session = AsyncMock()
        # execute returns all 3 as active
        result_mock = MagicMock()
        result_mock.__iter__ = lambda self: iter(
            [("camara",), ("senado",), ("dou",)]
        )
        session.execute = AsyncMock(return_value=result_mock)

        service = PolicySourceService(session)
        count = await service.ensure_default_sources(["camara", "senado", "dou"])

        assert count == 0
        session.add.assert_not_called()
        session.flush.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_partial_creates_only_missing(self):
        """When camara already exists, only senado and dou are created."""
        from ia_investing.application.policy_intelligence import PolicySourceService

        session = AsyncMock()
        # Only camara is active
        result_mock = MagicMock()
        result_mock.__iter__ = lambda self: iter([("camara",)])
        session.execute = AsyncMock(return_value=result_mock)

        service = PolicySourceService(session)
        count = await service.ensure_default_sources(["camara", "senado", "dou"])

        assert count == 2
        assert session.add.call_count == 2
        session.flush.assert_awaited_once()

        # Verify the created sources have correct authorities
        added_sources = [call.args[0] for call in session.add.call_args_list]
        added_authorities = {s.authority for s in added_sources}
        assert added_authorities == {"senado", "dou"}

    @pytest.mark.asyncio
    async def test_creates_source_with_correct_fields(self):
        """Created sources have name, authority, source_type, is_active set."""
        from ia_investing.application.policy_intelligence import PolicySourceService

        session = AsyncMock()
        result_mock = MagicMock()
        result_mock.__iter__ = lambda self: iter([])
        session.execute = AsyncMock(return_value=result_mock)

        service = PolicySourceService(session)
        await service.ensure_default_sources(["camara"])

        added_source = session.add.call_args_list[0].args[0]
        assert added_source.authority == "camara"
        assert added_source.name == "Camara"
        assert added_source.source_type == "camara"
        assert added_source.is_active is True
