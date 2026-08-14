"""Unit tests for apps.api.routes.policy — alerts, forecasts, stages, regulatory actions."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.api.routes.policy import (
    PolicyAlertResolveRequest,
    PolicyAlertV1,
    PolicyForecastV1,
    PolicyStageEventV1,
    RegulatoryActionV1,
    router,
)
from apps.api.security import AuthContext, get_auth_context
from database.core import get_async_session


def _mock_auth() -> AuthContext:
    return AuthContext(
        subject="user@test.com",
        roles=frozenset({"admin"}),
        permissions=frozenset({"policy:read", "portfolio:read"}),
        authentication_method="test",
        organization_id=uuid4(),
    )


def _mock_auth_no_policy() -> AuthContext:
    return AuthContext(
        subject="user@test.com",
        roles=frozenset({"viewer"}),
        permissions=frozenset(),
        authentication_method="test",
        organization_id=None,
    )


def _mock_session() -> AsyncMock:
    mock = AsyncMock()
    mock.execute = AsyncMock()
    mock.flush = AsyncMock()
    mock.add = MagicMock()
    mock.get = AsyncMock(return_value=None)
    return mock


@pytest.fixture()
def app_instance():
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_auth_context] = _mock_auth
    yield app
    app.dependency_overrides.clear()


@pytest.fixture()
def client(app_instance):
    return TestClient(app_instance, raise_server_exceptions=False)


@pytest.fixture()
def mock_session_dep(app_instance):
    session = _mock_session()
    app_instance.dependency_overrides[get_async_session] = lambda: session
    yield session
    app_instance.dependency_overrides.pop(get_async_session, None)


# ---------------------------------------------------------------------------
# Schema tests
# ---------------------------------------------------------------------------


class TestPolicyAlertV1Schema:
    def test_valid(self) -> None:
        alert = PolicyAlertV1(
            id=uuid4(),
            policy_object_id=uuid4(),
            alert_type="stage_change",
            severity="high",
            title="Bill advanced to Senate",
            description=None,
            fired_at=datetime.now(UTC),
            acknowledged_at=None,
            acknowledged_by=None,
            resolved_at=None,
            resolved_by=None,
        )
        assert alert.alert_type == "stage_change"

    def test_optional_fields_default_none(self) -> None:
        alert = PolicyAlertV1(
            id=uuid4(),
            policy_object_id=uuid4(),
            alert_type="vote",
            severity="low",
            title="Vote recorded",
            fired_at=datetime.now(UTC),
        )
        assert alert.description is None
        assert alert.resolved_at is None


class TestPolicyAlertResolveRequestSchema:
    def test_valid(self) -> None:
        body = PolicyAlertResolveRequest(notes="Policy updated, closing alert")
        assert body.notes == "Policy updated, closing alert"

    def test_too_short(self) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            PolicyAlertResolveRequest(notes="ok")

    def test_too_long(self) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            PolicyAlertResolveRequest(notes="x" * 4001)


class TestPolicyForecastV1Schema:
    def test_valid(self) -> None:
        f = PolicyForecastV1(
            id=uuid4(),
            policy_object_id=uuid4(),
            target_outcome="approval",
            probability=Decimal("0.65"),
            interval_low=Decimal("0.50"),
            interval_high=Decimal("0.80"),
        )
        assert f.probability == Decimal("0.65")


class TestPolicyStageEventV1Schema:
    def test_valid(self) -> None:
        now = datetime.now(UTC)
        e = PolicyStageEventV1(
            id=uuid4(),
            policy_object_id=uuid4(),
            stage="senate_committee",
            occurred_at=now,
            knowledge_at=now,
        )
        assert e.stage == "senate_committee"


class TestRegulatoryActionV1Schema:
    def test_valid(self) -> None:
        a = RegulatoryActionV1(
            id=uuid4(),
            policy_object_id=uuid4(),
            action_type="normative",
            title="CMN Resolution 123",
            issued_at=datetime.now(UTC),
            authority="CMN",
        )
        assert a.action_type == "normative"


# ---------------------------------------------------------------------------
# GET /alerts
# ---------------------------------------------------------------------------


class TestListAlerts:
    def test_returns_empty(self, client: TestClient, mock_session_dep: AsyncMock) -> None:
        mock_scalars = MagicMock()
        mock_scalars.scalars.return_value.all.return_value = []
        mock_session_dep.execute.return_value = mock_scalars

        resp = client.get("/api/v1/policy/alerts")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_auth_required(self, app_instance: FastAPI) -> None:
        app_instance.dependency_overrides[get_auth_context] = _mock_auth_no_policy
        session = _mock_session()
        app_instance.dependency_overrides[get_async_session] = lambda: session
        mock_scalars = MagicMock()
        mock_scalars.scalars.return_value.all.return_value = []
        session.execute.return_value = mock_scalars

        c = TestClient(app_instance, raise_server_exceptions=False)
        resp = c.get("/api/v1/policy/alerts")
        assert resp.status_code == 403

    def test_passes_filters(self, client: TestClient, mock_session_dep: AsyncMock) -> None:
        mock_scalars = MagicMock()
        mock_scalars.scalars.return_value.all.return_value = []
        mock_session_dep.execute.return_value = mock_scalars

        resp = client.get(
            "/api/v1/policy/alerts",
            params={"policy_object_id": str(uuid4()), "status": "resolved"},
        )
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# POST /alerts/{alert_id}/acknowledge
# ---------------------------------------------------------------------------


class TestAcknowledgeAlert:
    def test_not_found(self, client: TestClient, mock_session_dep: AsyncMock) -> None:
        mock_session_dep.get.return_value = None

        resp = client.post(f"/api/v1/policy/alerts/{uuid4()}/acknowledge")
        assert resp.status_code == 404

    def test_success(self, client: TestClient, mock_session_dep: AsyncMock) -> None:
        alert_id = uuid4()
        mock_alert = MagicMock()
        mock_alert.id = alert_id
        mock_alert.policy_object_id = uuid4()
        mock_alert.alert_type = "stage_change"
        mock_alert.severity = "high"
        mock_alert.title = "Bill advanced"
        mock_alert.description = None
        mock_alert.fired_at = datetime.now(UTC)
        mock_alert.acknowledged_at = None
        mock_alert.acknowledged_by = None
        mock_alert.resolved_at = None
        mock_alert.resolved_by = None
        mock_session_dep.get.return_value = mock_alert

        resp = client.post(f"/api/v1/policy/alerts/{alert_id}/acknowledge")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == str(alert_id)

    def test_already_acknowledged(self, client: TestClient, mock_session_dep: AsyncMock) -> None:
        alert_id = uuid4()
        mock_alert = MagicMock()
        mock_alert.acknowledged_at = datetime.now(UTC)
        mock_session_dep.get.return_value = mock_alert

        resp = client.post(f"/api/v1/policy/alerts/{alert_id}/acknowledge")
        assert resp.status_code == 409


# ---------------------------------------------------------------------------
# POST /alerts/{alert_id}/resolve
# ---------------------------------------------------------------------------


class TestResolveAlert:
    def test_not_found(self, client: TestClient, mock_session_dep: AsyncMock) -> None:
        mock_session_dep.get.return_value = None

        resp = client.post(
            f"/api/v1/policy/alerts/{uuid4()}/resolve",
            json={"notes": "Policy updated, closing alert"},
        )
        assert resp.status_code == 404

    def test_success(self, client: TestClient, mock_session_dep: AsyncMock) -> None:
        alert_id = uuid4()
        mock_alert = MagicMock()
        mock_alert.id = alert_id
        mock_alert.policy_object_id = uuid4()
        mock_alert.alert_type = "vote"
        mock_alert.severity = "medium"
        mock_alert.title = "Vote recorded"
        mock_alert.description = None
        mock_alert.fired_at = datetime.now(UTC)
        mock_alert.acknowledged_at = None
        mock_alert.acknowledged_by = None
        mock_alert.resolved_at = None
        mock_alert.resolved_by = None
        mock_alert.resolution_notes = None
        mock_session_dep.get.return_value = mock_alert

        resp = client.post(
            f"/api/v1/policy/alerts/{alert_id}/resolve",
            json={"notes": "Policy updated, closing alert"},
        )
        assert resp.status_code == 200
        assert resp.json()["id"] == str(alert_id)

    def test_invalid_body(self, client: TestClient, mock_session_dep: AsyncMock) -> None:
        resp = client.post(
            f"/api/v1/policy/alerts/{uuid4()}/resolve",
            json={"notes": "ok"},
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /forecasts
# ---------------------------------------------------------------------------


class TestListForecasts:
    def test_returns_empty(self, client: TestClient, mock_session_dep: AsyncMock) -> None:
        mock_scalars = MagicMock()
        mock_scalars.scalars.return_value.all.return_value = []
        mock_session_dep.execute.return_value = mock_scalars

        resp = client.get("/api/v1/policy/forecasts", params={"policy_object_id": str(uuid4())})
        assert resp.status_code == 200
        assert resp.json() == []

    def test_auth_required(self, app_instance: FastAPI) -> None:
        app_instance.dependency_overrides[get_auth_context] = _mock_auth_no_policy
        session = _mock_session()
        app_instance.dependency_overrides[get_async_session] = lambda: session
        mock_scalars = MagicMock()
        mock_scalars.scalars.return_value.all.return_value = []
        session.execute.return_value = mock_scalars

        c = TestClient(app_instance, raise_server_exceptions=False)
        resp = c.get("/api/v1/policy/forecasts", params={"policy_object_id": str(uuid4())})
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# GET /stages/{policy_object_id}
# ---------------------------------------------------------------------------


class TestGetStages:
    def test_returns_empty(self, client: TestClient, mock_session_dep: AsyncMock) -> None:
        mock_scalars = MagicMock()
        mock_scalars.scalars.return_value.all.return_value = []
        mock_session_dep.execute.return_value = mock_scalars

        resp = client.get(f"/api/v1/policy/stages/{uuid4()}")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_auth_required(self, app_instance: FastAPI) -> None:
        app_instance.dependency_overrides[get_auth_context] = _mock_auth_no_policy
        session = _mock_session()
        app_instance.dependency_overrides[get_async_session] = lambda: session
        mock_scalars = MagicMock()
        mock_scalars.scalars.return_value.all.return_value = []
        session.execute.return_value = mock_scalars

        c = TestClient(app_instance, raise_server_exceptions=False)
        resp = c.get(f"/api/v1/policy/stages/{uuid4()}")
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# GET /regulatory-actions
# ---------------------------------------------------------------------------


class TestListRegulatoryActions:
    def test_returns_empty(self, client: TestClient, mock_session_dep: AsyncMock) -> None:
        mock_scalars = MagicMock()
        mock_scalars.scalars.return_value.all.return_value = []
        mock_session_dep.execute.return_value = mock_scalars

        resp = client.get("/api/v1/policy/regulatory-actions")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_filter_by_authority(self, client: TestClient, mock_session_dep: AsyncMock) -> None:
        mock_scalars = MagicMock()
        mock_scalars.scalars.return_value.all.return_value = []
        mock_session_dep.execute.return_value = mock_scalars

        resp = client.get("/api/v1/policy/regulatory-actions", params={"authority": "BCB"})
        assert resp.status_code == 200

    def test_filter_by_policy_object(self, client: TestClient, mock_session_dep: AsyncMock) -> None:
        mock_scalars = MagicMock()
        mock_scalars.scalars.return_value.all.return_value = []
        mock_session_dep.execute.return_value = mock_scalars

        resp = client.get(
            "/api/v1/policy/regulatory-actions",
            params={"policy_object_id": str(uuid4())},
        )
        assert resp.status_code == 200

    def test_auth_required(self, app_instance: FastAPI) -> None:
        app_instance.dependency_overrides[get_auth_context] = _mock_auth_no_policy
        session = _mock_session()
        app_instance.dependency_overrides[get_async_session] = lambda: session
        mock_scalars = MagicMock()
        mock_scalars.scalars.return_value.all.return_value = []
        session.execute.return_value = mock_scalars

        c = TestClient(app_instance, raise_server_exceptions=False)
        resp = c.get("/api/v1/policy/regulatory-actions")
        assert resp.status_code == 403
