"""Unit tests for paper_execution API routes."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.api.routes.paper_execution import (
    CancelTradeIntentV1,
    ChallengerDecisionInputV1,
    ChallengerInputV1,
    CreateTradeIntentV1,
    DecideTradeIntentV1,
    KillSwitchInputV1,
    PostMortemInputV1,
    ResolveAlertV1,
    ResolveBreakV1,
    SimulateOrderV1,
    router,
)
from apps.api.security import AuthContext, get_auth_context


def _mock_auth() -> AuthContext:
    return AuthContext(
        subject="user@test.com",
        roles=frozenset({"admin"}),
        permissions=frozenset({"paper_orders:trade", "portfolio:read", "paper_orders:kill"}),
        authentication_method="test",
        organization_id=uuid4(),
    )


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


# ---------------------------------------------------------------------------
# Schema tests
# ---------------------------------------------------------------------------
class TestSchemas:
    def test_create_trade_intent_valid(self) -> None:
        intent = CreateTradeIntentV1(
            portfolio_version_id=uuid4(),
            instrument_id=uuid4(),
            side="buy",
            quantity=100,
            order_type="market",
            limit_price=None,
            earliest_execution_at=datetime.now(UTC),
            expires_at=datetime.now(UTC) + __import__("datetime").timedelta(hours=1),
            reason="Momentum signal",
        )
        assert intent.side == "buy"

    def test_create_trade_intent_invalid_side(self) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            CreateTradeIntentV1(
                portfolio_version_id=uuid4(),
                instrument_id=uuid4(),
                side="long",
                quantity=100,
                order_type="market",
                limit_price=None,
                earliest_execution_at=datetime.now(UTC),
                expires_at=datetime.now(UTC) + __import__("datetime").timedelta(hours=1),
                reason="Test",
            )

    def test_decide_trade_intent(self) -> None:
        d = DecideTradeIntentV1(approved=True, rationale="Looks good")
        assert d.approved is True

    def test_cancel_trade_intent(self) -> None:
        c = CancelTradeIntentV1(reason="Changed mind")
        assert c.reason == "Changed mind"

    def test_simulate_order(self) -> None:
        s = SimulateOrderV1(execution_model_version_id=uuid4(), seed=42)
        assert s.seed == 42

    def test_kill_switch_input(self) -> None:
        ks = KillSwitchInputV1(reason="Market freeze")
        assert ks.portfolio_id is None

    def test_resolve_break(self) -> None:
        r = ResolveBreakV1(method="manual", evidence="Checked ledger")
        assert r.method == "manual"

    def test_resolve_alert(self) -> None:
        r = ResolveAlertV1(method="investigation", evidence="Found root cause")
        assert r.method == "investigation"

    def test_post_mortem_input(self) -> None:
        pm = PostMortemInputV1(
            period_start=datetime.now(UTC),
            period_end=datetime.now(UTC),
            expected={"return": 0.05},
            realized={"return": 0.03},
            attribution={"model": 0.02},
            findings=[],
        )
        assert pm.dissent == []

    def test_challenger_input(self) -> None:
        ci = ChallengerInputV1(
            champion_portfolio_id=uuid4(),
            challenger_portfolio_id=uuid4(),
            window_start=datetime.now(UTC),
            window_end=datetime.now(UTC),
            methodology_version="v1",
            comparison_config={},
            metrics={},
            evidence={},
        )
        assert ci.methodology_version == "v1"

    def test_challenger_decision(self) -> None:
        cd = ChallengerDecisionInputV1(decision="retained")
        assert cd.decision == "retained"

    def test_challenger_decision_invalid(self) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            ChallengerDecisionInputV1(decision="maybe")


# ---------------------------------------------------------------------------
# Route tests — trade intents
# ---------------------------------------------------------------------------
class TestTradeIntents:
    def test_list_trade_intents_no_permission(self, client: TestClient) -> None:
        no_perm_auth = AuthContext(
            subject="user@test.com",
            roles=frozenset(),
            permissions=frozenset(),
            authentication_method="test",
            organization_id=uuid4(),
        )
        client.app.dependency_overrides[get_auth_context] = lambda: no_perm_auth
        resp = client.get("/api/v1/paper/trade-intents")
        assert resp.status_code == 403

    def test_list_trade_intents_success(self, client: TestClient) -> None:
        with patch("apps.api.routes.paper_execution.PaperExecutionService") as mock_service:
            mock_svc = MagicMock()
            mock_svc.list_trade_intents = AsyncMock(return_value=[])
            mock_service.return_value = mock_svc
            resp = client.get("/api/v1/paper/trade-intents")
            assert resp.status_code == 200

    def test_get_paper_order_not_found(self, client: TestClient) -> None:
        with patch("apps.api.routes.paper_execution.PaperExecutionService") as mock_service:
            mock_svc = MagicMock()
            mock_svc.get_order_with_intent = AsyncMock(return_value=None)
            mock_service.return_value = mock_svc
            resp = client.get(f"/api/v1/paper/orders/{uuid4()}")
            assert resp.status_code == 404

    def test_get_paper_order_no_permission(self, client: TestClient) -> None:
        no_perm_auth = AuthContext(
            subject="user@test.com",
            roles=frozenset(),
            permissions=frozenset(),
            authentication_method="test",
            organization_id=uuid4(),
        )
        client.app.dependency_overrides[get_auth_context] = lambda: no_perm_auth
        with patch("apps.api.routes.paper_execution.PaperExecutionService") as mock_service:
            mock_svc = MagicMock()
            mock_svc.get_order_with_intent = AsyncMock(return_value=(MagicMock(), MagicMock()))
            mock_service.return_value = mock_svc
            resp = client.get(f"/api/v1/paper/orders/{uuid4()}")
            assert resp.status_code == 403

    def test_create_trade_intent_lookup_error(self, client: TestClient) -> None:
        with patch("apps.api.routes.paper_execution.PaperExecutionService") as mock_service:
            mock_svc = MagicMock()
            mock_svc.create_intent = AsyncMock(side_effect=LookupError("not found"))
            mock_service.return_value = mock_svc
            resp = client.post(
                "/api/v1/paper/trade-intents",
                json={
                    "portfolio_version_id": str(uuid4()),
                    "instrument_id": str(uuid4()),
                    "side": "buy",
                    "quantity": "100",
                    "order_type": "market",
                    "earliest_execution_at": datetime.now(UTC).isoformat(),
                    "expires_at": (datetime.now(UTC) + __import__("datetime").timedelta(hours=1)).isoformat(),
                    "reason": "Test",
                },
                headers={"Idempotency-Key": "test-key-123"},
            )
            assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Route tests — alerts
# ---------------------------------------------------------------------------
class TestAlerts:
    def test_list_alerts_empty(self, client: TestClient) -> None:
        with patch("apps.api.routes.paper_execution.PaperExecutionService") as mock_service:
            mock_svc = MagicMock()
            mock_svc.list_alerts = AsyncMock(return_value=[])
            mock_service.return_value = mock_svc
            resp = client.get("/api/v1/paper/alerts")
            assert resp.status_code == 200

    def test_list_alerts_permission_error(self, client: TestClient) -> None:
        with patch("apps.api.routes.paper_execution.PaperExecutionService") as mock_service:
            mock_svc = MagicMock()
            mock_svc.list_alerts = AsyncMock(side_effect=PermissionError("no access"))
            mock_service.return_value = mock_svc
            resp = client.get("/api/v1/paper/alerts")
            assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Route tests — kill switches
# ---------------------------------------------------------------------------
class TestKillSwitchRoutes:
    def test_activate_kill_switch_success(self, client: TestClient) -> None:
        mock_switch = MagicMock()
        mock_switch.id = uuid4()
        mock_switch.organization_id = uuid4()
        mock_switch.active = True
        mock_switch.portfolio_id = None
        mock_switch.reason = "Freeze"
        mock_switch.activated_by = "user@test.com"
        mock_switch.activated_at = datetime.now(UTC)
        mock_switch.released_by = None
        mock_switch.released_at = None

        with patch("apps.api.routes.paper_execution.PaperExecutionService") as mock_service:
            mock_svc = MagicMock()
            mock_svc.activate_kill_switch = AsyncMock(return_value=mock_switch)
            mock_service.return_value = mock_svc
            resp = client.post(
                "/api/v1/paper/kill-switches",
                json={"reason": "Freeze"},
                headers={"Idempotency-Key": "test-key-123"},
            )
            assert resp.status_code == 201

    def test_release_kill_switch_success(self, client: TestClient) -> None:
        mock_switch = MagicMock()
        mock_switch.id = uuid4()
        mock_switch.organization_id = uuid4()
        mock_switch.active = False
        mock_switch.portfolio_id = None
        mock_switch.reason = "Freeze"
        mock_switch.activated_by = "alice@test.com"
        mock_switch.activated_at = datetime.now(UTC)
        mock_switch.released_by = "user@test.com"
        mock_switch.released_at = datetime.now(UTC)

        with patch("apps.api.routes.paper_execution.PaperExecutionService") as mock_service:
            mock_svc = MagicMock()
            mock_svc.release_kill_switch = AsyncMock(return_value=mock_switch)
            mock_service.return_value = mock_svc
            resp = client.post(
                f"/api/v1/paper/kill-switches/{uuid4()}/release",
                headers={"Idempotency-Key": "test-key-123"},
            )
            assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Route tests — reconciliation
# ---------------------------------------------------------------------------
class TestReconciliationRoutes:
    def test_reconcile_portfolio_empty(self, client: TestClient) -> None:
        with patch("apps.api.routes.paper_execution.PaperExecutionService") as mock_service:
            mock_svc = MagicMock()
            mock_svc.reconcile_portfolio = AsyncMock(return_value=[])
            mock_service.return_value = mock_svc
            resp = client.post(
                f"/api/v1/paper/portfolios/{uuid4()}/reconciliations",
                params={"as_of": datetime.now(UTC).isoformat()},
                headers={"Idempotency-Key": "test-key-123"},
            )
            assert resp.status_code == 200

    def test_resolve_break_success(self, client: TestClient) -> None:
        mock_break = MagicMock()
        mock_break.id = uuid4()
        mock_break.organization_id = uuid4()
        mock_break.portfolio_id = uuid4()
        mock_break.as_of = datetime.now(UTC)
        mock_break.rule = "nav_identity"
        mock_break.resource_key = "nav"
        mock_break.expected = {}
        mock_break.actual = {}
        mock_break.severity = "critical"
        mock_break.owner_role = "ops"
        mock_break.status = "resolved"
        mock_break.blocking = True
        mock_break.resolution = {"method": "manual"}
        mock_break.detected_at = datetime.now(UTC)
        mock_break.resolved_at = datetime.now(UTC)

        with patch("apps.api.routes.paper_execution.PaperExecutionService") as mock_service:
            mock_svc = MagicMock()
            mock_svc.resolve_break = AsyncMock(return_value=mock_break)
            mock_service.return_value = mock_svc
            resp = client.post(
                f"/api/v1/paper/reconciliation-breaks/{uuid4()}/resolution",
                json={"method": "manual", "evidence": "Checked"},
                headers={"Idempotency-Key": "test-key-123"},
            )
            assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Route tests — post-mortems
# ---------------------------------------------------------------------------
class TestPostMortemRoutes:
    def test_list_post_mortems_empty(self, client: TestClient) -> None:
        with patch("apps.api.routes.paper_execution.PaperExecutionService") as mock_service:
            mock_svc = MagicMock()
            mock_svc.list_post_mortems = AsyncMock(return_value=[])
            mock_service.return_value = mock_svc
            resp = client.get(f"/api/v1/paper/portfolios/{uuid4()}/post-mortems")
            assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Route tests — challenger evaluations
# ---------------------------------------------------------------------------
class TestChallengerRoutes:
    def test_list_challenger_evaluations_empty(self, client: TestClient) -> None:
        with patch("apps.api.routes.paper_execution.PaperExecutionService") as mock_service:
            mock_svc = MagicMock()
            mock_svc.list_challenger_evaluations = AsyncMock(return_value=[])
            mock_service.return_value = mock_svc
            resp = client.get("/api/v1/paper/challenger-evaluations")
            assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Route tests — dashboard
# ---------------------------------------------------------------------------
class TestDashboardRoute:
    def test_dashboard(self, client: TestClient) -> None:
        with patch("apps.api.routes.paper_execution.PaperExecutionService") as mock_service:
            mock_svc = MagicMock()
            mock_svc.get_operational_dashboard = AsyncMock(return_value={"status": "ok"})
            mock_service.return_value = mock_svc
            resp = client.get("/api/v1/paper/dashboard")
            assert resp.status_code == 200
