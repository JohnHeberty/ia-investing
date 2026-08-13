from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest
from fastapi import HTTPException
from temporalio.client import (
    RPCError,
    ScheduleAlreadyRunningError,
    ScheduleOverlapPolicy,
)

from apps.scheduler.temporal_schedules import (
    cvm_schedule_definition,
    news_dedup_schedule_definition,
    outbox_recovery_schedule_definition,
    paper_rebalance_schedule_definition,
    paper_reconciliation_schedule_definition,
    paper_valuation_schedule_definition,
    reconcile_schedules,
)


async def _empty_schedules():
    for item in []:
        yield item


# ---------------------------------------------------------------------------
# Existing tests — temporal_schedules definitions
# ---------------------------------------------------------------------------
def test_cvm_schedule_has_stable_policy_and_queue() -> None:
    definition = cvm_schedule_definition(
        cnpj="02.474.103/0001-19",
        issuer_id="engie-brasil",
        year=2025,
        every=timedelta(hours=12),
    )

    assert definition.schedule_id == "cvm-dfp-engie-brasil-2025-dre_con"
    assert definition.schedule.policy.overlap is ScheduleOverlapPolicy.SKIP
    assert definition.schedule.policy.catchup_window == timedelta(hours=1)
    assert definition.schedule.policy.pause_on_failure is True
    assert definition.schedule.action.task_queue == "data-ingestion"


def test_paper_reconciliation_schedule_is_fail_closed_and_stable() -> None:
    definition = paper_reconciliation_schedule_definition(
        portfolio_id="portfolio-1",
        organization_id="organization-1",
        every=timedelta(hours=24),
    )
    assert definition.schedule_id == "paper-reconciliation-portfolio-1"
    assert definition.schedule.policy.overlap is ScheduleOverlapPolicy.SKIP
    assert definition.schedule.policy.pause_on_failure is True
    assert definition.schedule.action.task_queue == "portfolio-risk"


def test_paper_valuation_and_rebalance_schedules_are_fail_closed_and_stable() -> None:
    valuation = paper_valuation_schedule_definition(
        portfolio_id="portfolio-1",
        portfolio_version_id="version-7",
        organization_id="organization-1",
    )
    rebalance = paper_rebalance_schedule_definition(
        portfolio_id="portfolio-1",
        portfolio_version_id="version-7",
        input_sha256="a" * 64,
    )
    assert valuation.schedule_id == "paper-valuation-portfolio-1"
    assert rebalance.schedule_id == "paper-rebalance-portfolio-1"
    for definition in (valuation, rebalance):
        assert definition.schedule.policy.overlap is ScheduleOverlapPolicy.SKIP
        assert definition.schedule.policy.pause_on_failure is True
        assert definition.schedule.action.task_queue == "portfolio-risk"


@pytest.mark.asyncio
async def test_reconcile_creates_new_schedule() -> None:
    definition = cvm_schedule_definition(cnpj="1", issuer_id="issuer", year=2025)
    client = Mock()
    client.create_schedule = AsyncMock()
    client.list_schedules = AsyncMock(return_value=_empty_schedules())

    result = await reconcile_schedules(client, [definition])

    assert result == {definition.schedule_id: "created"}
    client.create_schedule.assert_awaited_once_with(definition.schedule_id, definition.schedule)


@pytest.mark.asyncio
async def test_reconcile_updates_existing_schedule() -> None:
    definition = cvm_schedule_definition(cnpj="1", issuer_id="issuer", year=2025)
    client = Mock()
    client.create_schedule = AsyncMock(side_effect=ScheduleAlreadyRunningError())
    client.list_schedules = AsyncMock(return_value=_empty_schedules())
    handle = Mock()
    handle.update = AsyncMock()
    client.get_schedule_handle.return_value = handle

    result = await reconcile_schedules(client, [definition])

    assert result == {definition.schedule_id: "updated"}
    handle.update.assert_awaited_once()


@pytest.mark.asyncio
async def test_reconcile_deletes_only_stale_managed_schedules() -> None:
    definition = outbox_recovery_schedule_definition()
    client = Mock()
    client.create_schedule = AsyncMock()
    stale_handle = Mock(delete=AsyncMock())
    custom_handle = Mock(delete=AsyncMock())
    equity_handle = Mock(delete=AsyncMock())
    client.get_schedule_handle.side_effect = lambda schedule_id: {
        "news-collection-stale": stale_handle,
        "custom-report": custom_handle,
        "equity-exploration-org-daily": equity_handle,
    }[schedule_id]

    async def _items():
        for schedule_id in ("news-collection-stale", "custom-report", "equity-exploration-org-daily"):
            yield MagicMock(id=schedule_id)

    client.list_schedules = AsyncMock(return_value=_items())

    result = await reconcile_schedules(client, [definition])

    assert result["news-collection-stale"] == "deleted"
    stale_handle.delete.assert_awaited_once()
    custom_handle.delete.assert_not_awaited()
    equity_handle.delete.assert_not_awaited()


@pytest.mark.asyncio
async def test_reconcile_propagates_cleanup_failure() -> None:
    definition = outbox_recovery_schedule_definition()
    client = Mock()
    client.create_schedule = AsyncMock()
    client.list_schedules = AsyncMock(side_effect=RuntimeError("Temporal unavailable"))

    with pytest.raises(RuntimeError, match="Temporal unavailable"):
        await reconcile_schedules(client, [definition])


def test_schedule_definitions_validate_intervals_and_hashes() -> None:
    with pytest.raises(ValueError, match="positive"):
        outbox_recovery_schedule_definition(every=timedelta(0))
    with pytest.raises(ValueError, match="SHA-256"):
        paper_rebalance_schedule_definition(
            portfolio_id="portfolio-1",
            portfolio_version_id="version-1",
            input_sha256="z" * 64,
        )


def test_news_dedup_uses_dedicated_workflow() -> None:
    definition = news_dedup_schedule_definition()

    assert definition.schedule.action.workflow == "NewsDedupWorkflow"
    assert definition.schedule_id == "news-dedup-cleanup"


# ---------------------------------------------------------------------------
# _safe_get / _safe_str helper tests
# ---------------------------------------------------------------------------
class TestSafeHelpers:
    def test_safe_get_existing_attr(self) -> None:
        from apps.api.routes.schedules import _safe_get

        obj = MagicMock()
        obj.foo = "bar"
        assert _safe_get(obj, "foo") == "bar"

    def test_safe_get_missing_attr_returns_default(self) -> None:
        from apps.api.routes.schedules import _safe_get

        assert _safe_get(None, "foo", "default") == "default"

    def test_safe_get_exception_returns_default(self) -> None:
        from apps.api.routes.schedules import _safe_get

        class BadObj:
            def __getattr__(self, name: str) -> object:
                raise AttributeError("nope")

        assert _safe_get(BadObj(), "foo", "default") == "default"

    def test_safe_str_existing(self) -> None:
        from apps.api.routes.schedules import _safe_str

        obj = MagicMock()
        obj.val = 42
        assert _safe_str(obj, "val") == "42"

    def test_safe_str_none_returns_none(self) -> None:
        from apps.api.routes.schedules import _safe_str

        obj = MagicMock()
        obj.val = None
        assert _safe_str(obj, "val") is None


# ---------------------------------------------------------------------------
# _validate_schedule_id
# ---------------------------------------------------------------------------
class TestValidateScheduleId:
    def test_valid_id(self) -> None:
        from apps.api.routes.schedules import _validate_schedule_id

        assert _validate_schedule_id("my-schedule_123") == "my-schedule_123"

    def test_empty_id_raises(self) -> None:
        from apps.api.routes.schedules import _validate_schedule_id

        with pytest.raises(HTTPException, match="length"):
            _validate_schedule_id("")

    def test_too_long_raises(self) -> None:
        from apps.api.routes.schedules import _validate_schedule_id

        with pytest.raises(HTTPException, match="length"):
            _validate_schedule_id("x" * 201)

    def test_invalid_chars_raises(self) -> None:
        from apps.api.routes.schedules import _validate_schedule_id

        with pytest.raises(HTTPException, match="match"):
            _validate_schedule_id("schedule with spaces")


# ---------------------------------------------------------------------------
# _handle_temporal_error
# ---------------------------------------------------------------------------
class TestHandleTemporalError:
    def test_not_found_rpc_error(self) -> None:
        from apps.api.routes.schedules import _handle_temporal_error

        exc = RPCError("not found", "not_found", None)
        with pytest.raises(HTTPException, match="404"):
            _handle_temporal_error(exc, "sched-1")

    def test_deadline_exceeded_rpc_error(self) -> None:
        from apps.api.routes.schedules import _handle_temporal_error

        exc = RPCError("timeout", "deadline_exceeded", None)
        with pytest.raises(HTTPException, match="503"):
            _handle_temporal_error(exc, "sched-1")

    def test_unavailable_rpc_error(self) -> None:
        from apps.api.routes.schedules import _handle_temporal_error

        exc = RPCError("down", "unavailable", None)
        with pytest.raises(HTTPException, match="503"):
            _handle_temporal_error(exc, "sched-1")

    def test_other_rpc_error(self) -> None:
        from apps.api.routes.schedules import _handle_temporal_error

        exc = RPCError("unknown", "internal", None)
        with pytest.raises(HTTPException, match="502"):
            _handle_temporal_error(exc, "sched-1")

    def test_non_rpc_error(self) -> None:
        from apps.api.routes.schedules import _handle_temporal_error

        with pytest.raises(HTTPException, match="500"):
            _handle_temporal_error(RuntimeError("oops"), "sched-1")


# ---------------------------------------------------------------------------
# _enrich_schedule
# ---------------------------------------------------------------------------
class TestEnrichSchedule:
    def test_known_prefix_news(self) -> None:
        from apps.api.routes.schedules import _enrich_schedule

        data = {"schedule_id": "news-collection-daily"}
        result = _enrich_schedule(data)
        assert result["category"] == "news"
        assert "noticias" in result["description"]

    def test_known_prefix_operations(self) -> None:
        from apps.api.routes.schedules import _enrich_schedule

        data = {"schedule_id": "operation-outbox-dispatch"}
        result = _enrich_schedule(data)
        assert result["category"] == "operations"

    def test_known_prefix_data(self) -> None:
        from apps.api.routes.schedules import _enrich_schedule

        data = {"schedule_id": "cvm-dfp-engie"}
        result = _enrich_schedule(data)
        assert result["category"] == "data"

    def test_known_prefix_portfolio(self) -> None:
        from apps.api.routes.schedules import _enrich_schedule

        data = {"schedule_id": "paper-reconciliation-p1"}
        result = _enrich_schedule(data)
        assert result["category"] == "portfolio"

    def test_known_prefix_research(self) -> None:
        from apps.api.routes.schedules import _enrich_schedule

        data = {"schedule_id": "equity-exploration-petra"}
        result = _enrich_schedule(data)
        assert result["category"] == "research"

    def test_unknown_prefix_other(self) -> None:
        from apps.api.routes.schedules import _enrich_schedule

        data = {"schedule_id": "custom-schedule-xyz"}
        result = _enrich_schedule(data)
        assert result["category"] == "other"
        assert result["description"] == "custom-schedule-xyz"

    def test_managed_schedule_is_default(self) -> None:
        from apps.api.routes.schedules import _enrich_schedule

        data = {"schedule_id": "news-dedup-cleanup"}
        result = _enrich_schedule(data)
        assert result["is_default"] is True

    def test_exact_match_without_trailing_dash(self) -> None:
        from apps.api.routes.schedules import _enrich_schedule

        data = {"schedule_id": "news-dedup-cleanup"}
        result = _enrich_schedule(data)
        assert result["category"] == "news"


# ---------------------------------------------------------------------------
# SCHEDULE_META coverage
# ---------------------------------------------------------------------------
class TestScheduleMeta:
    def test_all_meta_entries_have_required_keys(self) -> None:
        from apps.api.routes.schedules import SCHEDULE_META

        for _prefix, meta in SCHEDULE_META.items():
            assert "category" in meta
            assert "description" in meta


# ---------------------------------------------------------------------------
# Schema tests
# ---------------------------------------------------------------------------
class TestScheduleSchemas:
    def test_schedule_summary_v1(self) -> None:
        from apps.api.routes.schedules import ScheduleSummaryV1

        s = ScheduleSummaryV1(
            schedule_id="s1",
            status="running",
            paused=False,
            category="news",
            description="test",
        )
        assert s.running_workflows == 0

    def test_schedule_detail_v1(self) -> None:
        from apps.api.routes.schedules import ScheduleDetailV1

        d = ScheduleDetailV1(
            schedule_id="s1",
            status="running",
            paused=False,
        )
        assert d.action is None

    def test_update_interval_request(self) -> None:
        from apps.api.routes.schedules import UpdateIntervalRequestV1

        req = UpdateIntervalRequestV1(every_minutes=30)
        assert req.every_minutes == 30

    def test_schedule_run_v1(self) -> None:
        from apps.api.routes.schedules import ScheduleRunV1

        run = ScheduleRunV1(
            id="r1",
            schedule_id="s1",
            status="completed",
            started_at=datetime.now(UTC),
        )
        assert run.error_message is None


# ---------------------------------------------------------------------------
# Route endpoint tests
# ---------------------------------------------------------------------------
class TestScheduleRoutes:
    def test_list_schedules_empty(self) -> None:
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from apps.api.dependencies import get_temporal_client
        from apps.api.routes.schedules import router
        from apps.api.security import AuthContext, get_auth_context

        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_auth_context] = lambda: AuthContext(
            subject="test@test.com",
            roles=frozenset({"admin"}),
            permissions=frozenset({"schedules:read"}),
            authentication_method="test",
            organization_id=None,
        )

        async def _empty_iter():
            for _ in []:
                yield _

        mock_client = MagicMock()
        mock_client.list_schedules = AsyncMock(return_value=_empty_iter())
        app.dependency_overrides[get_temporal_client] = lambda: mock_client

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/v1/schedules")
        assert resp.status_code == 200

    def test_get_schedule_not_found(self) -> None:
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from apps.api.dependencies import get_temporal_client
        from apps.api.routes.schedules import router
        from apps.api.security import AuthContext, get_auth_context

        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_auth_context] = lambda: AuthContext(
            subject="test@test.com",
            roles=frozenset({"admin"}),
            permissions=frozenset({"schedules:read"}),
            authentication_method="test",
            organization_id=None,
        )

        mock_client = MagicMock()
        mock_handle = MagicMock()
        exc = RPCError("not found", "not_found", None)
        mock_handle.describe = AsyncMock(side_effect=exc)
        mock_client.get_schedule_handle.return_value = mock_handle
        app.dependency_overrides[get_temporal_client] = lambda: mock_client

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/v1/schedules/unknown-schedule")
        assert resp.status_code == 404

    def test_pause_schedule_success(self) -> None:
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from apps.api.dependencies import get_temporal_client
        from apps.api.routes.schedules import router
        from apps.api.security import AuthContext, get_auth_context
        from database.core import get_async_session

        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_auth_context] = lambda: AuthContext(
            subject="test@test.com",
            roles=frozenset({"admin"}),
            permissions=frozenset({"schedules:manage"}),
            authentication_method="test",
            organization_id=None,
        )

        mock_client = MagicMock()
        mock_handle = MagicMock()
        mock_handle.pause = AsyncMock()
        mock_client.get_schedule_handle.return_value = mock_handle
        app.dependency_overrides[get_temporal_client] = lambda: mock_client

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
        app.dependency_overrides[get_async_session] = lambda: mock_session

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/api/v1/schedules/test-schedule/pause")
        assert resp.status_code == 200
        assert "paused" in resp.json()["message"]

    def test_resume_schedule_success(self) -> None:
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from apps.api.dependencies import get_temporal_client
        from apps.api.routes.schedules import router
        from apps.api.security import AuthContext, get_auth_context
        from database.core import get_async_session

        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_auth_context] = lambda: AuthContext(
            subject="test@test.com",
            roles=frozenset({"admin"}),
            permissions=frozenset({"schedules:manage"}),
            authentication_method="test",
            organization_id=None,
        )

        mock_client = MagicMock()
        mock_handle = MagicMock()
        mock_handle.unpause = AsyncMock()
        mock_client.get_schedule_handle.return_value = mock_handle
        app.dependency_overrides[get_temporal_client] = lambda: mock_client

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
        app.dependency_overrides[get_async_session] = lambda: mock_session

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/api/v1/schedules/test-schedule/resume")
        assert resp.status_code == 200
        assert "resumed" in resp.json()["message"]

    def test_trigger_schedule_success(self) -> None:
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from apps.api.dependencies import get_temporal_client
        from apps.api.routes.schedules import router
        from apps.api.security import AuthContext, get_auth_context
        from database.core import get_async_session

        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_auth_context] = lambda: AuthContext(
            subject="test@test.com",
            roles=frozenset({"admin"}),
            permissions=frozenset({"schedules:manage"}),
            authentication_method="test",
            organization_id=None,
        )

        mock_client = MagicMock()
        mock_client.namespace = "default"
        mock_handle = MagicMock()
        description = MagicMock()
        description.info.running_actions = []
        description.schedule.action.task_queue = "research-agents"
        mock_handle.describe = AsyncMock(return_value=description)
        mock_handle.trigger = AsyncMock()
        mock_client.get_schedule_handle.return_value = mock_handle
        mock_client.workflow_service.describe_task_queue = AsyncMock(return_value=MagicMock(pollers=[MagicMock()]))
        app.dependency_overrides[get_temporal_client] = lambda: mock_client

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
        app.dependency_overrides[get_async_session] = lambda: mock_session

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/api/v1/schedules/test-schedule/trigger")
        assert resp.status_code == 200
        assert "triggered" in resp.json()["message"]
        assert resp.json()["triggered_at"] is not None

    @pytest.mark.parametrize(
        ("running_actions", "pollers", "expected_status", "expected_detail"),
        [
            ([MagicMock()], [MagicMock()], 409, "already has a running workflow"),
            ([], [], 503, "No worker is polling task queue"),
        ],
    )
    def test_trigger_schedule_rejects_unprocessable_action(
        self,
        running_actions: list[MagicMock],
        pollers: list[MagicMock],
        expected_status: int,
        expected_detail: str,
    ) -> None:
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from apps.api.dependencies import get_temporal_client
        from apps.api.routes.schedules import router
        from apps.api.security import AuthContext, get_auth_context
        from database.core import get_async_session

        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_auth_context] = lambda: AuthContext(
            subject="test@test.com",
            roles=frozenset({"admin"}),
            permissions=frozenset({"schedules:manage"}),
            authentication_method="test",
            organization_id=None,
        )

        description = MagicMock()
        description.info.running_actions = running_actions
        description.schedule.action.task_queue = "research-agents"
        mock_handle = MagicMock(describe=AsyncMock(return_value=description), trigger=AsyncMock())
        mock_client = MagicMock(namespace="default")
        mock_client.get_schedule_handle.return_value = mock_handle
        mock_client.workflow_service.describe_task_queue = AsyncMock(return_value=MagicMock(pollers=pollers))
        app.dependency_overrides[get_temporal_client] = lambda: mock_client
        app.dependency_overrides[get_async_session] = lambda: AsyncMock()

        response = TestClient(app, raise_server_exceptions=False).post("/api/v1/schedules/test-schedule/trigger")

        assert response.status_code == expected_status
        assert expected_detail in response.json()["detail"]
        mock_handle.trigger.assert_not_awaited()

    def test_delete_schedule_success(self) -> None:
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from apps.api.dependencies import get_temporal_client
        from apps.api.routes.schedules import router
        from apps.api.security import AuthContext, get_auth_context
        from database.core import get_async_session

        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_auth_context] = lambda: AuthContext(
            subject="test@test.com",
            roles=frozenset({"admin"}),
            permissions=frozenset({"schedules:manage"}),
            authentication_method="test",
            organization_id=None,
        )

        mock_client = MagicMock()
        mock_handle = MagicMock()
        mock_handle.delete = AsyncMock()
        mock_client.get_schedule_handle.return_value = mock_handle
        app.dependency_overrides[get_temporal_client] = lambda: mock_client

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
        app.dependency_overrides[get_async_session] = lambda: mock_session

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.delete("/api/v1/schedules/test-schedule")
        assert resp.status_code == 200
        assert "deleted" in resp.json()["message"]

    def test_generic_schedule_creation_is_not_supported(self) -> None:
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from apps.api.dependencies import get_temporal_client
        from apps.api.routes.schedules import router
        from apps.api.security import AuthContext, get_auth_context

        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_auth_context] = lambda: AuthContext(
            subject="test@test.com",
            roles=frozenset({"admin"}),
            permissions=frozenset({"schedules:manage"}),
            authentication_method="test",
            organization_id=None,
        )
        mock_client = MagicMock()
        app.dependency_overrides[get_temporal_client] = lambda: mock_client

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/api/v1/schedules", json={"schedule_id": "test"})
        assert resp.status_code == 405

    def test_update_interval_no_time(self) -> None:
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from apps.api.dependencies import get_temporal_client
        from apps.api.routes.schedules import router
        from apps.api.security import AuthContext, get_auth_context

        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_auth_context] = lambda: AuthContext(
            subject="test@test.com",
            roles=frozenset({"admin"}),
            permissions=frozenset({"schedules:manage"}),
            authentication_method="test",
            organization_id=None,
        )
        mock_client = MagicMock()
        app.dependency_overrides[get_temporal_client] = lambda: mock_client

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.put(
            "/api/v1/schedules/test-schedule/update-interval",
            json={},
        )
        assert resp.status_code == 400

    def test_get_schedule_runs_empty(self) -> None:
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from apps.api.routes.schedules import router
        from apps.api.security import AuthContext, get_auth_context
        from database.core import get_async_session

        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_auth_context] = lambda: AuthContext(
            subject="test@test.com",
            roles=frozenset({"admin"}),
            permissions=frozenset({"schedules:read"}),
            authentication_method="test",
            organization_id=None,
        )

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)
        app.dependency_overrides[get_async_session] = lambda: mock_session

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/v1/schedules/test-schedule/runs")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_pause_schedule_temporal_error(self) -> None:
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from apps.api.dependencies import get_temporal_client
        from apps.api.routes.schedules import router
        from apps.api.security import AuthContext, get_auth_context

        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_auth_context] = lambda: AuthContext(
            subject="test@test.com",
            roles=frozenset({"admin"}),
            permissions=frozenset({"schedules:manage"}),
            authentication_method="test",
            organization_id=None,
        )

        mock_client = MagicMock()
        mock_handle = MagicMock()
        mock_handle.pause = AsyncMock(side_effect=RPCError("not found", "not_found", None))
        mock_client.get_schedule_handle.return_value = mock_handle
        app.dependency_overrides[get_temporal_client] = lambda: mock_client

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/api/v1/schedules/test-schedule/pause")
        assert resp.status_code == 404
