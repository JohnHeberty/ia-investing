"""Unit tests for risk_overview routes."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.api.routes.risk_overview import (
    MacroIndicatorItem,
    MacroIndicatorsResponse,
    RiskBreachItem,
    RiskOverviewResponse,
    RiskPoliciesResponse,
    RiskPolicyItem,
    RiskSnapshotItem,
    StressScenarioItem,
    router,
)
from apps.api.security import AuthContext, get_auth_context


def _mock_auth() -> AuthContext:
    return AuthContext(
        subject="test@example.com",
        roles=frozenset({"admin"}),
        permissions=frozenset({"risk:read"}),
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
# Schema validation
# ---------------------------------------------------------------------------
class TestSchemas:
    def test_risk_snapshot_item(self) -> None:
        item = RiskSnapshotItem(
            id=uuid4(),
            portfolio_id="p1",
            as_of=datetime.now(UTC),
            volatility=0.15,
            drawdown=-0.05,
            concentration={"A": 0.5},
            liquidity={"cash": 1000},
            exposures={"eq": 0.8},
            breach_count=2,
        )
        assert item.breach_count == 2

    def test_risk_snapshot_item_null_values(self) -> None:
        item = RiskSnapshotItem(
            id=uuid4(),
            portfolio_id=None,
            as_of=datetime.now(UTC),
            volatility=None,
            drawdown=None,
            concentration=None,
            liquidity=None,
            exposures=None,
            breach_count=0,
        )
        assert item.volatility is None

    def test_risk_overview_response_empty(self) -> None:
        resp = RiskOverviewResponse(
            snapshots=[],
            breaches=[],
            stress_scenarios=[],
            hard_breach_count=0,
            soft_breach_count=0,
            latest_volatility=None,
            latest_drawdown=None,
            total_snapshots=0,
        )
        assert resp.total_snapshots == 0

    def test_risk_policies_response_empty(self) -> None:
        resp = RiskPoliciesResponse(policies=[], count=0)
        assert resp.count == 0

    def test_macro_indicators_response_empty(self) -> None:
        resp = MacroIndicatorsResponse(indicators=[], selic=None, ipca=None, usd_brl=None, count=0)
        assert resp.count == 0

    def test_risk_breach_item(self) -> None:
        item = RiskBreachItem(
            id=uuid4(),
            limit_name="vol",
            limit_type="hard",
            observed_value=0.25,
            limit_value=0.20,
            status="open",
        )
        assert item.limit_type == "hard"

    def test_stress_scenario_item(self) -> None:
        item = StressScenarioItem(
            id=uuid4(),
            name="Covid",
            pnl_impact=-0.15,
            nav_impact_ratio=-0.12,
        )
        assert item.pnl_impact == -0.15

    def test_risk_policy_item(self) -> None:
        item = RiskPolicyItem(
            id=uuid4(),
            mandate_id="m1",
            version=1,
            methodology_version="v1",
            limits={"max_vol": 0.2},
            status="active",
        )
        assert item.status == "active"

    def test_macro_indicator_item(self) -> None:
        item = MacroIndicatorItem(
            id=uuid4(),
            indicator_name="SELIC",
            source="BCB",
            value=13.75,
            unit="p.a.",
            period_date=datetime(2026, 1, 1, tzinfo=UTC),
            published_at=datetime(2026, 1, 5, tzinfo=UTC),
        )
        assert item.value == 13.75


# ---------------------------------------------------------------------------
# Risk overview endpoint — mock SQL execution
# ---------------------------------------------------------------------------
class TestRiskOverviewEndpoint:
    @pytest.mark.asyncio
    async def test_empty_overview(self) -> None:
        mock_result_snap = MagicMock()
        mock_result_snap.fetchall.return_value = []
        mock_result_breach = MagicMock()
        mock_result_breach.fetchall.return_value = []
        mock_result_stress = MagicMock()
        mock_result_stress.fetchall.return_value = []

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(side_effect=[mock_result_snap, mock_result_breach, mock_result_stress])

        from apps.api.routes.risk_overview import get_risk_overview

        auth = _mock_auth()
        result = await get_risk_overview(auth=auth, session=mock_session)
        assert result.total_snapshots == 0
        assert result.hard_breach_count == 0

    @pytest.mark.asyncio
    async def test_with_snapshots_and_breaches(self) -> None:
        snap_id = uuid4()
        mock_snap_result = MagicMock()
        mock_snap_result.fetchall.return_value = [
            (snap_id, "p1", datetime.now(UTC), 0.15, -0.05, {"A": 0.5}, None, None),
        ]
        mock_breach_result = MagicMock()
        mock_breach_result.fetchall.return_value = [
            (uuid4(), snap_id, "vol_limit", "hard", 0.25, 0.20, "open"),
        ]
        mock_stress_result = MagicMock()
        mock_stress_result.fetchall.return_value = []

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(side_effect=[mock_snap_result, mock_breach_result, mock_stress_result])

        from apps.api.routes.risk_overview import get_risk_overview

        auth = _mock_auth()
        result = await get_risk_overview(auth=auth, session=mock_session)
        assert result.total_snapshots == 1
        assert result.hard_breach_count == 1
        assert len(result.breaches) == 1

    @pytest.mark.asyncio
    async def test_breach_fetch_error_returns_empty(self) -> None:
        snap_id = uuid4()
        mock_snap_result = MagicMock()
        mock_snap_result.fetchall.return_value = [
            (snap_id, "p1", datetime.now(UTC), 0.15, -0.05, None, None, None),
        ]
        call_count = 0

        async def _side_effect(query, params=None):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return mock_snap_result
            raise Exception("breach query failed")

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(side_effect=_side_effect)

        from apps.api.routes.risk_overview import get_risk_overview

        auth = _mock_auth()
        result = await get_risk_overview(auth=auth, session=mock_session)
        assert result.total_snapshots == 1
        assert result.breaches == []

    @pytest.mark.asyncio
    async def test_soft_breach_count(self) -> None:
        snap_id = uuid4()
        mock_snap_result = MagicMock()
        mock_snap_result.fetchall.return_value = [
            (snap_id, "p1", datetime.now(UTC), 0.15, -0.05, None, None, None),
        ]
        mock_breach_result = MagicMock()
        mock_breach_result.fetchall.return_value = [
            (uuid4(), snap_id, "concentration", "soft", 0.60, 0.50, "open"),
        ]
        mock_stress_result = MagicMock()
        mock_stress_result.fetchall.return_value = []

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(side_effect=[mock_snap_result, mock_breach_result, mock_stress_result])

        from apps.api.routes.risk_overview import get_risk_overview

        auth = _mock_auth()
        result = await get_risk_overview(auth=auth, session=mock_session)
        assert result.soft_breach_count == 1
        assert result.hard_breach_count == 0


# ---------------------------------------------------------------------------
# Risk policies endpoint
# ---------------------------------------------------------------------------
class TestRiskPoliciesEndpoint:
    @pytest.mark.asyncio
    async def test_empty_policies(self) -> None:
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        from apps.api.routes.risk_overview import get_risk_policies

        auth = _mock_auth()
        result = await get_risk_policies(auth=auth, session=mock_session)
        assert result.count == 0

    @pytest.mark.asyncio
    async def test_with_policies(self) -> None:
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            (uuid4(), "m1", 1, "v1", {"max_vol": 0.2}, "active"),
        ]
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        from apps.api.routes.risk_overview import get_risk_policies

        auth = _mock_auth()
        result = await get_risk_policies(auth=auth, session=mock_session)
        assert result.count == 1

    @pytest.mark.asyncio
    async def test_db_error_returns_empty(self) -> None:
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(side_effect=Exception("db down"))

        from apps.api.routes.risk_overview import get_risk_policies

        auth = _mock_auth()
        result = await get_risk_policies(auth=auth, session=mock_session)
        assert result.count == 0

    @pytest.mark.asyncio
    async def test_null_limits_defaults_to_empty_dict(self) -> None:
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            (uuid4(), "m1", 1, "v1", None, "active"),
        ]
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        from apps.api.routes.risk_overview import get_risk_policies

        auth = _mock_auth()
        result = await get_risk_policies(auth=auth, session=mock_session)
        assert result.policies[0].limits == {}


# ---------------------------------------------------------------------------
# Macro indicators endpoint
# ---------------------------------------------------------------------------
class TestMacroIndicatorsEndpoint:
    @pytest.mark.asyncio
    async def test_empty_indicators(self) -> None:
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        from apps.api.routes.risk_overview import get_macro_indicators

        auth = _mock_auth()
        result = await get_macro_indicators(auth=auth, session=mock_session)
        assert result.count == 0
        assert result.selic is None
        assert result.ipca is None
        assert result.usd_brl is None

    @pytest.mark.asyncio
    async def test_with_selic_indicator(self) -> None:
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            (uuid4(), "Taxa Selic", "BCB", 13.75, "p.a.", datetime.now(UTC), datetime.now(UTC)),
        ]
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        from apps.api.routes.risk_overview import get_macro_indicators

        auth = _mock_auth()
        result = await get_macro_indicators(auth=auth, session=mock_session)
        assert result.count == 1
        assert result.selic is not None
        assert result.selic.indicator_name == "Taxa Selic"

    @pytest.mark.asyncio
    async def test_with_ipca_indicator(self) -> None:
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            (uuid4(), "IPCA acumulado", "IBGE", 4.5, None, None, None),
        ]
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        from apps.api.routes.risk_overview import get_macro_indicators

        auth = _mock_auth()
        result = await get_macro_indicators(auth=auth, session=mock_session)
        assert result.ipca is not None

    @pytest.mark.asyncio
    async def test_with_usd_brl_indicator(self) -> None:
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            (uuid4(), "USD/BRL", "B3", 5.2, None, None, None),
        ]
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        from apps.api.routes.risk_overview import get_macro_indicators

        auth = _mock_auth()
        result = await get_macro_indicators(auth=auth, session=mock_session)
        assert result.usd_brl is not None

    @pytest.mark.asyncio
    async def test_db_error_returns_empty_indicators(self) -> None:
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(side_effect=Exception("db down"))

        from apps.api.routes.risk_overview import get_macro_indicators

        auth = _mock_auth()
        result = await get_macro_indicators(auth=auth, session=mock_session)
        assert result.count == 0

    @pytest.mark.asyncio
    async def test_null_value_indicator(self) -> None:
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            (uuid4(), "UNKNOWN", "source", None, None, None, None),
        ]
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        from apps.api.routes.risk_overview import get_macro_indicators

        auth = _mock_auth()
        result = await get_macro_indicators(auth=auth, session=mock_session)
        assert result.count == 1
        assert result.indicators[0].value is None
        assert result.selic is None

    @pytest.mark.asyncio
    async def test_multiple_indicators_selects_correctly(self) -> None:
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            (uuid4(), "Taxa Selic", "BCB", 13.75, "p.a.", None, None),
            (uuid4(), "IPCA", "IBGE", 4.5, None, None, None),
            (uuid4(), "Dólar PTAX", "BCB", 5.2, "BRL", None, None),
        ]
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        from apps.api.routes.risk_overview import get_macro_indicators

        auth = _mock_auth()
        result = await get_macro_indicators(auth=auth, session=mock_session)
        assert result.count == 3
        assert result.selic is not None
        assert result.ipca is not None
        assert result.usd_brl is not None
