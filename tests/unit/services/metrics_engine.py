from __future__ import annotations

import pytest

from metrics.engine import (
    PILLARS,
    _safe_div,
    calculate_all,
    calculate_pillar,
    get_metric_names,
    get_pillar_names,
)


class TestSafeDiv:
    @pytest.mark.parametrize(
        "num, den, expected",
        [
            (10.0, 2.0, 5.0),
            (0.0, 5.0, 0.0),
            (10.0, 0.0, None),
            (None, 5.0, None),
            (10.0, None, None),
            (None, None, None),
        ],
    )
    def test_safe_div(self, num, den, expected):
        assert _safe_div(num, den) == expected


class TestCalculatePillar:
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

    def test_unknown_pillar_returns_empty_dict(self):
        result = calculate_pillar("nonexistent", {}, {})
        assert result == {}

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


class TestCalculateAll:
    def test_returns_all_pillar_names(self):
        result = calculate_all(
            {"receita_liquida": 100, "ebitda": 50, "lucro_liquido": 20, "patrimonio_liquido": 200},
            {"price": 10, "market_cap": 500},
        )
        assert set(result.keys()) == set(PILLARS.keys())

    def test_pillar_values_are_dicts(self):
        result = calculate_all({}, {})
        for _pillar_name, metrics in result.items():
            assert isinstance(metrics, dict)


class TestGetPillarNames:
    def test_returns_list(self):
        names = get_pillar_names()
        assert isinstance(names, list)
        assert len(names) > 0


class TestGetMetricNames:
    def test_all_metrics(self):
        names = get_metric_names()
        assert isinstance(names, list)
        assert len(names) > 0

    def test_filtered_by_pillar(self):
        names = get_metric_names("valuation")
        assert isinstance(names, list)
        assert "pe_ttm" in names

    def test_unknown_pillar_returns_empty(self):
        names = get_metric_names("nonexistent")
        assert names == []
