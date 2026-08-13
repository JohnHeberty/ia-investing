"""Tests for metrics helpers, engine, metric pillar modules, and MetricService."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from metrics._dividend import DIVIDEND_METRICS
from metrics._helpers import _get, _md, _pct_change, _safe_div
from metrics._macro import MACRO_METRICS
from metrics._quality_growth import QUALITY_GROWTH_METRICS
from metrics.engine import PILLARS, calculate_all, calculate_pillar, get_metric_names, get_pillar_names
from ia_investing.application.metrics import (
    MetricBundleV1,
    MetricService,
    calculate_known_metric,
)


# ---------------------------------------------------------------------------
# _helpers.py
# ---------------------------------------------------------------------------
class TestSafeDiv:
    def test_normal(self):
        assert _safe_div(10.0, 2.0) == 5.0

    def test_zero_denominator(self):
        assert _safe_div(10.0, 0.0) is None

    def test_none_numerator(self):
        assert _safe_div(None, 2.0) is None

    def test_none_denominator(self):
        assert _safe_div(10.0, None) is None

    def test_infinite_result(self):
        assert _safe_div(float("inf"), 1.0) is None

    def test_nan_result(self):
        assert _safe_div(float("nan"), 1.0) is None

    def test_both_zero(self):
        assert _safe_div(0.0, 0.0) is None


class TestPctChange:
    def test_normal(self):
        assert _pct_change(120, 100) == pytest.approx(20.0)

    def test_none_current(self):
        assert _pct_change(None, 100) is None

    def test_none_previous(self):
        assert _pct_change(100, None) is None

    def test_zero_previous(self):
        assert _pct_change(100, 0.0) is None

    def test_negative_change(self):
        assert _pct_change(80, 100) == pytest.approx(-20.0)


class TestGet:
    def test_returns_float(self):
        assert _get({"revenue": 1000}, "revenue") == 1000.0

    def test_missing(self):
        assert _get({}, "revenue") is None

    def test_string_value(self):
        assert _get({"revenue": "1000"}, "revenue") == 1000.0

    def test_non_numeric(self):
        assert _get({"revenue": "abc"}, "revenue") is None


class TestMd:
    def test_returns_float(self):
        assert _md({"price": 50.0}, "price") == 50.0

    def test_missing(self):
        assert _md({}, "price") is None


# ---------------------------------------------------------------------------
# engine.py
# ---------------------------------------------------------------------------
class TestEngine:
    def test_get_pillar_names(self):
        names = get_pillar_names()
        assert "quality_growth" in names
        assert "dividend" in names
        assert "macro" in names

    def test_get_metric_names_all(self):
        names = get_metric_names()
        assert len(names) > 20

    def test_get_metric_names_by_pillar(self):
        names = get_metric_names("quality_growth")
        assert "roe" in names

    def test_calculate_pillar_unknown(self):
        result = calculate_pillar("nonexistent", {}, {})
        assert result == {}

    def test_calculate_pillar_quality_growth(self):
        li = {"receita_liquida": 1000, "lucro_liquido": 100, "patrimonio_liquido": 500}
        md = {"market_cap": 10000}
        result = calculate_pillar("quality_growth", li, md)
        assert "roe" in result
        assert result["roe"] == pytest.approx(0.2)

    def test_calculate_all(self):
        li = {"receita_liquida": 1000}
        md = {"price": 50.0}
        result = calculate_all(li, md)
        assert "quality_growth" in result
        assert "dividend" in result

    def test_valuation_pillar_returns_metrics(self):
        line_items = {
            "lucro_por_acao_ttm": 5.0,
            "valor_patrimonial_por_acao": 20.0,
            "ebitda": 1_000_000.0,
            "ebit": 800_000.0,
            "receita_liquida": 5_000_000.0,
            "patrimonio_liquido": 3_000_000.0,
            "dividendo_por_acao": 2.0,
            "lucro_por_acao": 5.0,
            "fluxo_caixa_livre": 400_000.0,
        }
        market_data = {
            "price": 50.0,
            "enterprise_value": 8_000_000.0,
            "market_cap": 10_000_000.0,
        }

        result = calculate_pillar("valuation", line_items, market_data)

        assert isinstance(result, dict)
        assert "pe_ttm" in result
        assert result["pe_ttm"] == pytest.approx(10.0)
        assert result["pb"] == pytest.approx(2.5)
        assert result["dividend_yield"] == pytest.approx(0.04)

    def test_leverage_pillar(self):
        line_items = {
            "divida_liquida": 2_000_000.0,
            "ebitda": 1_000_000.0,
            "patrimonio_liquido": 3_000_000.0,
            "ativo_circulante": 1_500_000.0,
            "passivo_circulante": 1_000_000.0,
            "passivo_nao_circulante": 500_000.0,
            "ebit": 800_000.0,
            "despesas_financeiras": 100_000.0,
            "divida_total": 2_500_000.0,
            "total_ativos": 6_000_000.0,
        }
        result = calculate_pillar("leverage_debt", line_items, {})
        assert result["net_debt_ebitda"] == pytest.approx(2.0)
        assert result["net_debt_equity"] == pytest.approx(2_000_000 / 3_000_000)
        assert result["current_ratio"] == pytest.approx(1.5)
        assert result["interest_coverage"] == pytest.approx(8.0)

    def test_missing_keys_return_none(self):
        result = calculate_pillar("valuation", {}, {})
        for val in result.values():
            assert val is None


# ---------------------------------------------------------------------------
# _dividend.py
# ---------------------------------------------------------------------------
class TestDividendMetrics:
    def test_div_yield(self):
        li = {"dividendos_por_acao_12m": 5.0}
        md = {"price": 100.0}
        assert DIVIDEND_METRICS["div_yield_12m"](li, md) == pytest.approx(0.05)

    def test_div_growth(self):
        li = {"dividendos_por_acao_atual": 5.0, "dividendos_por_acao_3y_atras": 3.0}
        result = DIVIDEND_METRICS["div_growth_3y"](li, {})
        assert result == pytest.approx(66.666, rel=1e-2)

    def test_payout_avg(self):
        li = {"payout_medio_3y": 0.6}
        assert DIVIDEND_METRICS["payout_avg_3y"](li, {}) == 0.6

    def test_div_consistency(self):
        li = {"consistencia_dividendos": 0.9}
        assert DIVIDEND_METRICS["div_consistency"](li, {}) == 0.9

    def test_jcp_ratio(self):
        li = {"jcp_por_acao": 2.0, "dividendos_por_acao_12m": 10.0}
        assert DIVIDEND_METRICS["jcp_ratio"](li, {}) == pytest.approx(0.2)


# ---------------------------------------------------------------------------
# _macro.py
# ---------------------------------------------------------------------------
class TestMacroMetrics:
    def test_real_interest(self):
        md = {"selic": 12.0, "ipca": 5.0}
        assert MACRO_METRICS["real_interest"]({}, md) == pytest.approx(7.0)

    def test_real_interest_none(self):
        assert MACRO_METRICS["real_interest"]({}, {}) is None

    def test_usd_brl(self):
        md = {"usd_brl": 5.2}
        assert MACRO_METRICS["usd_brl"]({}, md) == 5.2


# ---------------------------------------------------------------------------
# _quality_growth.py
# ---------------------------------------------------------------------------
class TestQualityGrowthMetrics:
    def test_revenue_yoy(self):
        li = {"receita_liquida": 1200, "receita_liquida_anterior": 1000}
        assert QUALITY_GROWTH_METRICS["revenue_yoy"](li, {}) == pytest.approx(20.0)

    def test_gross_margin(self):
        li = {"lucro_bruto": 400, "receita_liquida": 1000}
        assert QUALITY_GROWTH_METRICS["gross_margin"](li, {}) == pytest.approx(0.4)

    def test_roe(self):
        li = {"lucro_liquido": 100, "patrimonio_liquido": 500}
        assert QUALITY_GROWTH_METRICS["roe"](li, {}) == pytest.approx(0.2)

    def test_roa(self):
        li = {"lucro_liquido": 100, "total_ativos": 2000}
        assert QUALITY_GROWTH_METRICS["roa"](li, {}) == pytest.approx(0.05)

    def test_roic(self):
        li = {"ebit": 200, "aliquota_imposto": 0.3, "capital_investido": 1000}
        result = QUALITY_GROWTH_METRICS["roic"](li, {})
        assert result == pytest.approx(0.14)

    def test_roic_none_when_missing(self):
        assert QUALITY_GROWTH_METRICS["roic"]({}, {}) is None

    def test_fcf_yield(self):
        li = {"fluxo_caixa_livre": 50}
        md = {"market_cap": 1000}
        assert QUALITY_GROWTH_METRICS["fcf_yield"](li, md) == pytest.approx(0.05)


# ---------------------------------------------------------------------------
# calculate_known_metric
# ---------------------------------------------------------------------------
@pytest.mark.unit
def test_known_metric_current_ratio() -> None:
    result = calculate_known_metric(
        "current_ratio",
        {"current_assets": Decimal("200"), "current_liabilities": Decimal("100")},
    )
    assert result == Decimal("2")


@pytest.mark.unit
def test_known_metric_net_margin() -> None:
    result = calculate_known_metric(
        "net_margin",
        {"net_income": Decimal("50"), "revenue": Decimal("200")},
    )
    assert result == Decimal("0.25")


@pytest.mark.unit
def test_known_metric_debt_to_equity() -> None:
    result = calculate_known_metric(
        "debt_to_equity",
        {"total_debt": Decimal("300"), "equity": Decimal("100")},
    )
    assert result == Decimal("3")


@pytest.mark.unit
def test_known_metric_unregistered_raises() -> None:
    with pytest.raises(ValueError, match="not registered"):
        calculate_known_metric("unknown_metric", {})


@pytest.mark.unit
def test_known_metric_zero_denominator_raises() -> None:
    with pytest.raises(ValueError, match="denominator"):
        calculate_known_metric(
            "current_ratio",
            {"current_assets": Decimal("100"), "current_liabilities": Decimal("0")},
        )


# ---------------------------------------------------------------------------
# MetricBundleV1
# ---------------------------------------------------------------------------
@pytest.mark.unit
def test_metric_bundle_v1_defaults() -> None:
    bundle = MetricBundleV1(
        observation_id=uuid4(),
        issuer_id=uuid4(),
        reporting_period_id=uuid4(),
        metric_name="test",
        definition_version=1,
        formula="x / y",
        unit="ratio",
        value=Decimal("1.5"),
        value_status="calculated",
        data_as_of=datetime.now(UTC),
        quality_score=Decimal("0.9"),
        coverage_ratio=Decimal("1.0"),
        calculation_version="test:v1",
        lineage_ids=[],
    )
    assert bundle.schema_version == "1.0"


@pytest.mark.unit
def test_metric_bundle_v1_forbids_extra() -> None:
    with pytest.raises(Exception):
        MetricBundleV1(
            observation_id=uuid4(),
            issuer_id=uuid4(),
            reporting_period_id=uuid4(),
            metric_name="test",
            definition_version=1,
            formula="x / y",
            unit="ratio",
            value=None,
            value_status="missing",
            data_as_of=datetime.now(UTC),
            quality_score=Decimal("0"),
            coverage_ratio=Decimal("0"),
            calculation_version="test:v1",
            lineage_ids=[],
            extra_field="bad",  # type: ignore[call-arg]
        )


# ---------------------------------------------------------------------------
# MetricService.calculate
# ---------------------------------------------------------------------------
def _mock_session() -> AsyncMock:
    session = AsyncMock()
    session.execute = AsyncMock(return_value=MagicMock())
    session.scalar = AsyncMock(return_value=None)
    session.add = MagicMock()
    session.flush = AsyncMock()
    return session


def _capture_add_id(obj: object) -> None:
    """Assign a uuid4 to ORM objects missing a real id (post-flush simulation)."""
    if isinstance(getattr(obj, "id", None), MagicMock) or getattr(obj, "id", None) is None:
        obj.id = uuid4()  # type: ignore[union-attr]


def _make_definition(
    name: str = "current_ratio",
    version: int = 1,
    deps: list[str] | None = None,
) -> MagicMock:
    defn = MagicMock()
    defn.id = uuid4()
    defn.name = name
    defn.version = version
    defn.formula = "current_assets / current_liabilities"
    defn.unit = "ratio"
    if deps is None:
        defn.dependencies = ["current_assets", "current_liabilities"]
    else:
        defn.dependencies = deps
    return defn


@pytest.mark.unit
@pytest.mark.asyncio
async def test_calculate_rejects_naive_datetime() -> None:
    session = _mock_session()
    service = MetricService(session)
    with pytest.raises(ValueError, match="timezone"):
        await service.calculate(
            "current_ratio", uuid4(), uuid4(), datetime(2026, 1, 1)
        )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_calculate_definition_not_found() -> None:
    session = _mock_session()
    session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
    service = MetricService(session)
    with pytest.raises(LookupError, match="not found"):
        await service.calculate(
            "current_ratio", uuid4(), uuid4(), datetime.now(UTC)
        )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_calculate_no_dependencies_skips_facts_query() -> None:
    """When definition has no deps, facts query is skipped; usable empty → calculate on empty dict."""
    session = _mock_session()
    defn = _make_definition(deps=[])
    exec1 = MagicMock()
    exec1.scalar_one_or_none.return_value = defn

    session.execute = AsyncMock(side_effect=[exec1])
    session.add = MagicMock(side_effect=_capture_add_id)

    service = MetricService(session)
    with pytest.raises(KeyError):
        await service.calculate(
            "current_ratio", uuid4(), uuid4(), datetime.now(UTC)
        )
    assert session.execute.call_count == 1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_calculate_missing_facts() -> None:
    session = _mock_session()
    defn = _make_definition(deps=["current_assets", "current_liabilities"])

    exec1 = MagicMock()
    exec1.scalar_one_or_none.return_value = defn

    fact_mock = MagicMock()
    fact_mock.value = Decimal("100")
    fact_mock.value_status = "reported"
    fact_mock.id = uuid4()
    exec2 = MagicMock()
    exec2.all.return_value = [(fact_mock, "current_assets")]

    exec3 = MagicMock()
    exec3.scalar_one_or_none.return_value = None

    exec4 = MagicMock()
    exec4.scalars.return_value = []

    session.execute = AsyncMock(side_effect=[exec1, exec2, exec3, exec4])
    session.add = MagicMock(side_effect=_capture_add_id)

    service = MetricService(session)
    result = await service.calculate(
        "current_ratio", uuid4(), uuid4(), datetime.now(UTC)
    )
    assert result.value is None
    assert result.value_status == "missing"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_calculate_full_coverage() -> None:
    session = _mock_session()
    defn = _make_definition(deps=["current_assets", "current_liabilities"])

    exec1 = MagicMock()
    exec1.scalar_one_or_none.return_value = defn

    facts = []
    for code in ["current_assets", "current_liabilities"]:
        fact = MagicMock()
        fact.value = Decimal("200") if code == "current_assets" else Decimal("100")
        fact.value_status = "reported"
        fact.id = uuid4()
        facts.append((fact, code))
    exec2 = MagicMock()
    exec2.all.return_value = facts

    exec3 = MagicMock()
    exec3.scalar_one_or_none.return_value = None

    exec4 = MagicMock()
    exec4.scalars.return_value = []

    session.execute = AsyncMock(side_effect=[exec1, exec2, exec3, exec4])
    session.add = MagicMock(side_effect=_capture_add_id)

    service = MetricService(session)
    result = await service.calculate(
        "current_ratio", uuid4(), uuid4(), datetime.now(UTC)
    )
    assert result.value == Decimal("2")
    assert result.value_status == "calculated"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_calculate_reuses_existing_observation() -> None:
    session = _mock_session()
    defn = _make_definition(deps=["current_assets", "current_liabilities"])

    exec1 = MagicMock()
    exec1.scalar_one_or_none.return_value = defn

    facts = []
    for code in ["current_assets", "current_liabilities"]:
        fact = MagicMock()
        fact.value = Decimal("200") if code == "current_assets" else Decimal("100")
        fact.value_status = "reported"
        fact.id = uuid4()
        facts.append((fact, code))
    exec2 = MagicMock()
    exec2.all.return_value = facts

    existing = MagicMock()
    existing.id = uuid4()
    existing.value = Decimal("2")
    existing.value_status = "calculated"
    existing.quality_score = Decimal("1")
    existing.coverage_ratio = Decimal("1")
    existing.data_as_of = datetime.now(UTC)
    existing.calculation_version = "current_ratio:v1"
    exec3 = MagicMock()
    exec3.scalar_one_or_none.return_value = existing

    exec4 = MagicMock()
    exec4.scalars.return_value = [uuid4()]

    session.execute = AsyncMock(side_effect=[exec1, exec2, exec3, exec4])

    service = MetricService(session)
    result = await service.calculate(
        "current_ratio", uuid4(), uuid4(), datetime.now(UTC)
    )
    assert result.observation_id == existing.id
    session.add.assert_not_called()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_calculate_suppressed_fact_not_usable() -> None:
    session = _mock_session()
    defn = _make_definition(deps=["current_assets", "current_liabilities"])

    exec1 = MagicMock()
    exec1.scalar_one_or_none.return_value = defn

    fact1 = MagicMock()
    fact1.value = Decimal("200")
    fact1.value_status = "reported"
    fact1.id = uuid4()
    fact2 = MagicMock()
    fact2.value = None
    fact2.value_status = "suppressed"
    fact2.id = uuid4()
    exec2 = MagicMock()
    exec2.all.return_value = [(fact1, "current_assets"), (fact2, "current_liabilities")]

    exec3 = MagicMock()
    exec3.scalar_one_or_none.return_value = None
    exec4 = MagicMock()
    exec4.scalars.return_value = []

    session.execute = AsyncMock(side_effect=[exec1, exec2, exec3, exec4])
    session.add = MagicMock(side_effect=_capture_add_id)

    service = MetricService(session)
    result = await service.calculate(
        "current_ratio", uuid4(), uuid4(), datetime.now(UTC)
    )
    assert result.value is None
    assert result.value_status == "missing"
