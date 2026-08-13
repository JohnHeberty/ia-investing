"""Tests for ia_investing.application.mission_control — dashboard builder."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from ia_investing.application.mission_control import (
    MissionControlService,
    _decimal,
    _p95,
)


def _mock_session() -> AsyncMock:
    session = AsyncMock()
    session.execute = AsyncMock(return_value=MagicMock())
    session.scalar = AsyncMock(return_value=0)
    return session


def _make_row(
    *,
    ranking_as_of: datetime | None = datetime(2026, 1, 1, tzinfo=UTC),
    name: str = "Port A",
    category: str = "equity",
    currency: str = "BRL",
    environment: str = "paper",
    stage: str = "paper_live",
    **overrides: object,
) -> dict[str, object]:
    base = {
        "portfolio_id": uuid4(),
        "name": name,
        "currency": currency,
        "environment": environment,
        "stage": stage,
        "portfolio_version_id": uuid4(),
        "ranking_as_of": ranking_as_of,
        "category": category,
        "benchmark": "IBOV",
        "risk_class": "aggressive",
        "inception_at": datetime(2025, 1, 1, tzinfo=UTC),
        "nav_reconciled": True,
        "backtest_point_in_time_verified": True,
        "approved_version": True,
        "open_hard_breaches": 0,
        "open_soft_breaches": 0,
        "expired_theses": 0,
        "thesis_coverage": Decimal("0.90"),
        "data_confidence": Decimal("0.95"),
        "low_liquidity": False,
        "high_turnover": False,
        "excess_return": Decimal("0.05"),
        "sortino": Decimal("1.2"),
        "drawdown_control": Decimal("0.8"),
        "regime_stability": Decimal("0.7"),
        "walk_forward_robustness": Decimal("0.6"),
        "risk_compliance": Decimal("0.9"),
        "thesis_health": Decimal("0.85"),
        "cost_capacity": Decimal("0.5"),
        "data_model_confidence": Decimal("0.8"),
        "nav": Decimal("1000000"),
        "nav_as_of": datetime(2026, 1, 1, tzinfo=UTC),
        "reconciled": True,
        "volatility": Decimal("0.15"),
        "drawdown": Decimal("0.08"),
    }
    base.update(overrides)
    return base


def _make_result_mock(
    portfolio_id: UUID,
    score: Decimal = Decimal("75"),
    rank: int = 1,
    eligible: bool = True,
) -> MagicMock:
    r = MagicMock()
    r.portfolio_id = str(portfolio_id)
    r.score = score
    r.rank = rank
    r.eligible = eligible
    r.cohort_key = "equity|IBOV|BRL|aggressive|paper"
    r.reasons = frozenset()
    return r


# --- Unit tests for helpers ---


@pytest.mark.unit
def test_decimal_none_returns_default() -> None:
    assert _decimal(None) == Decimal("0")


@pytest.mark.unit
def test_decimal_none_custom_default() -> None:
    assert _decimal(None, "99") == Decimal("99")


@pytest.mark.unit
def test_decimal_with_value() -> None:
    assert _decimal(Decimal("3.14")) == Decimal("3.14")


@pytest.mark.unit
def test_decimal_with_string() -> None:
    assert _decimal("42") == Decimal("42")


@pytest.mark.unit
def test_p95_empty() -> None:
    assert _p95([]) is None


@pytest.mark.unit
def test_p95_single_element() -> None:
    assert _p95([100]) == 100


@pytest.mark.unit
def test_p95_small_list() -> None:
    values = list(range(1, 21))  # 1..20
    result = _p95(values)
    assert result is not None
    assert result >= 19


@pytest.mark.unit
def test_p95_with_nones() -> None:
    result = _p95([None, 10, 20, 30])  # type: ignore[list-item]
    assert result == 30


@pytest.mark.unit
def test_p95_large_list() -> None:
    import random

    rng = random.Random(42)
    values = [rng.randint(1, 1000) for _ in range(100)]
    result = _p95(values)
    assert result is not None
    assert 850 <= result <= 1000


# --- Service build tests ---


@pytest.mark.unit
@pytest.mark.asyncio
async def test_build_empty_portfolios() -> None:
    session = _mock_session()
    # Portfolio input returns empty rows
    result_mock = MagicMock()
    result_mock.mappings.return_value.all.return_value = []
    # Research funnel
    funnel_mock = MagicMock()
    funnel_mock.mappings.return_value.return_value = []
    # Agent ops
    ops_mock = MagicMock()
    ops_mock.mappings.return_value.one.return_value = {
        "running": 0,
        "succeeded_24h": 0,
        "failed_24h": 0,
        "evidence_coverage": None,
        "cost_usd_24h": 0,
        "durations": [],
    }
    # Source health
    source_mock = MagicMock()
    source_mock.mappings.return_value.all.return_value = []
    # Candidate pipeline
    pipeline_mock = MagicMock()
    pipeline_mock.mappings.return_value.return_value = []
    # Risk summary (breach count)
    risk_mock = MagicMock()
    risk_mock.mappings.return_value.one.return_value = {
        "hard": 0,
        "soft": 0,
        "portfolios": 0,
    }
    # Risk summary (stale snapshots) - via scalar, not execute

    session.execute = AsyncMock(
        side_effect=[result_mock, funnel_mock, ops_mock, source_mock, pipeline_mock, risk_mock]
    )
    session.scalar = AsyncMock(return_value=0)

    service = MissionControlService(session)
    response = await service.build(organization_id=uuid4())

    assert response.top_portfolios == []
    assert response.excluded_portfolios == []
    assert response.critical_alerts == 0
    assert response.pending_approvals == 0


@pytest.mark.unit
@pytest.mark.asyncio
async def test_build_with_missing_snapshot_goes_to_excluded() -> None:
    session = _mock_session()
    row = _make_row(ranking_as_of=None)

    result_mock = MagicMock()
    result_mock.mappings.return_value.all.return_value = [row]
    funnel_mock = MagicMock()
    funnel_mock.mappings.return_value.return_value = []
    ops_mock = MagicMock()
    ops_mock.mappings.return_value.one.return_value = {
        "running": 0, "succeeded_24h": 0, "failed_24h": 0,
        "evidence_coverage": None, "cost_usd_24h": 0, "durations": [],
    }
    source_mock = MagicMock()
    source_mock.mappings.return_value.all.return_value = []
    pipeline_mock = MagicMock()
    pipeline_mock.mappings.return_value.return_value = []
    risk_mock = MagicMock()
    risk_mock.mappings.return_value.one.return_value = {
        "hard": 0, "soft": 0, "portfolios": 0,
    }

    session.execute = AsyncMock(
        side_effect=[result_mock, funnel_mock, ops_mock, source_mock, pipeline_mock, risk_mock]
    )
    session.scalar = AsyncMock(return_value=0)

    service = MissionControlService(session)
    response = await service.build(organization_id=uuid4())

    assert len(response.excluded_portfolios) == 1
    assert response.excluded_portfolios[0].exclusion_reasons == ["ranking_snapshot_missing"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_build_eligible_portfolios_ranked() -> None:
    session = _mock_session()
    row_a = _make_row(name="Port A")
    row_b = _make_row(name="Port B")
    row_a["portfolio_id"] = uuid4()
    row_b["portfolio_id"] = uuid4()

    result_mock = MagicMock()
    result_mock.mappings.return_value.all.return_value = [row_a, row_b]

    with patch(
        "ia_investing.application.mission_control.rank_portfolios",
        return_value=[
            _make_result_mock(row_a["portfolio_id"], score=Decimal("80"), rank=1),  # type: ignore[arg-type]
            _make_result_mock(row_b["portfolio_id"], score=Decimal("60"), rank=2),  # type: ignore[arg-type]
        ],
    ):
        funnel_mock = MagicMock()
        funnel_mock.mappings.return_value.return_value = []
        ops_mock = MagicMock()
        ops_mock.mappings.return_value.one.return_value = {
            "running": 0, "succeeded_24h": 0, "failed_24h": 0,
            "evidence_coverage": None, "cost_usd_24h": 0, "durations": [],
        }
        source_mock = MagicMock()
        source_mock.mappings.return_value.all.return_value = []
        pipeline_mock = MagicMock()
        pipeline_mock.mappings.return_value.return_value = []
        risk_mock = MagicMock()
        risk_mock.mappings.return_value.one.return_value = {
            "hard": 0, "soft": 0, "portfolios": 0,
        }

        session.execute = AsyncMock(
            side_effect=[result_mock, funnel_mock, ops_mock, source_mock, pipeline_mock, risk_mock]
        )
        session.scalar = AsyncMock(return_value=0)

        service = MissionControlService(session)
        response = await service.build(organization_id=uuid4())

        assert len(response.top_portfolios) == 2
        assert response.top_portfolios[0].rank == 1
        assert response.top_portfolios[1].rank == 2


@pytest.mark.unit
@pytest.mark.asyncio
async def test_build_critical_alerts_from_breach_and_source() -> None:
    session = _mock_session()
    row = _make_row()
    result_mock = MagicMock()
    result_mock.mappings.return_value.all.return_value = [row]

    with patch(
        "ia_investing.application.mission_control.rank_portfolios",
        return_value=[_make_result_mock(row["portfolio_id"])],  # type: ignore[arg-type]
    ):
        funnel_mock = MagicMock()
        funnel_mock.mappings.return_value.return_value = []
        ops_mock = MagicMock()
        ops_mock.mappings.return_value.one.return_value = {
            "running": 0, "succeeded_24h": 0, "failed_24h": 0,
            "evidence_coverage": None, "cost_usd_24h": 0, "durations": [],
        }
        source_mock = MagicMock()
        failed_at = datetime(2026, 1, 2, tzinfo=UTC)
        success_at = datetime(2026, 1, 1, tzinfo=UTC)
        source_item = {
            "source_id": uuid4(),
            "code": "B3",
            "name": "B3 Market Data",
            "last_success_at": success_at,
            "last_failure_at": failed_at,
            "expected_frequency_minutes": 60,
            "freshness_grace_minutes": 30,
            "last_error_code": "TIMEOUT",
        }
        source_mock.mappings.return_value.all.return_value = [source_item]
        pipeline_mock = MagicMock()
        pipeline_mock.mappings.return_value.return_value = []
        risk_mock = MagicMock()
        risk_mock.mappings.return_value.one.return_value = {
            "hard": 2, "soft": 1, "portfolios": 1,
        }

        session.execute = AsyncMock(
            side_effect=[result_mock, funnel_mock, ops_mock, source_mock, pipeline_mock, risk_mock]
        )
        session.scalar = AsyncMock(return_value=0)

        service = MissionControlService(session)
        response = await service.build(organization_id=uuid4())

        # 2 hard breaches + 1 failed source = 3
        assert response.critical_alerts == 3


@pytest.mark.unit
@pytest.mark.asyncio
async def test_build_candidate_pipeline_exception_returns_none() -> None:
    session = _mock_session()
    row = _make_row()
    result_mock = MagicMock()
    result_mock.mappings.return_value.all.return_value = [row]

    with patch(
        "ia_investing.application.mission_control.rank_portfolios",
        return_value=[_make_result_mock(row["portfolio_id"])],  # type: ignore[arg-type]
    ):
        funnel_mock = MagicMock()
        funnel_mock.mappings.return_value.return_value = []
        ops_mock = MagicMock()
        ops_mock.mappings.return_value.one.return_value = {
            "running": 0, "succeeded_24h": 0, "failed_24h": 0,
            "evidence_coverage": None, "cost_usd_24h": 0, "durations": [],
        }
        source_mock = MagicMock()
        source_mock.mappings.return_value.all.return_value = []
        risk_mock = MagicMock()
        risk_mock.mappings.return_value.one.return_value = {
            "hard": 0, "soft": 0, "portfolios": 0,
        }

        call_count = 0
        async def _side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return result_mock
            elif call_count == 2:
                return funnel_mock
            elif call_count == 3:
                return ops_mock
            elif call_count == 4:
                return source_mock
            elif call_count == 5:
                raise Exception("table not found")
            elif call_count == 6:
                return risk_mock
            raise Exception("unexpected")

        session.execute = AsyncMock(side_effect=_side_effect)
        session.scalar = AsyncMock(return_value=0)

        service = MissionControlService(session)
        response = await service.build(organization_id=uuid4())

        assert response.candidate_pipeline is None
