"""Tests for metrics helpers, engine, and metric pillar modules."""

from __future__ import annotations

import pytest

from metrics._dividend import DIVIDEND_METRICS
from metrics._helpers import _get, _md, _pct_change, _safe_div
from metrics._macro import MACRO_METRICS
from metrics._quality_growth import QUALITY_GROWTH_METRICS
from metrics.engine import calculate_all, calculate_pillar, get_metric_names, get_pillar_names


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
