"""Tests for the normalization package (derived, mappings, normalizers)."""

from __future__ import annotations

import sys
import types
from unittest.mock import MagicMock

import pytest


# ---------------------------------------------------------------------------
# Helpers to build FinancialEntry-like objects without importing connectors
# ---------------------------------------------------------------------------
def _make_entry(**kwargs):
    """Build a mock FinancialEntry with sensible defaults."""
    entry = MagicMock()
    entry.cod_conta = kwargs.get("cod_conta", "1.01")
    entry.desc_conta = kwargs.get("desc_conta", "Caixa e equivalentes de caixa")
    entry.valor = kwargs.get("valor", 100.0)
    return entry


# ---------------------------------------------------------------------------
# _derived.py tests
# ---------------------------------------------------------------------------
from normalization._derived import compute_derived_metrics


class TestComputeDerivedMetrics:
    def test_empty_input(self):
        result = compute_derived_metrics({})
        assert result == {}

    def test_lucro_bruto_computed_when_missing(self):
        result = compute_derived_metrics({"receita_liquida": 1000, "custo_receita": 600})
        assert result["lucro_bruto"] == 400.0

    def test_lucro_bruto_not_overwritten(self):
        result = compute_derived_metrics({"receita_liquida": 1000, "custo_receita": 600, "lucro_bruto": 500})
        assert result.get("lucro_bruto") is None or "lucro_bruto" not in result

    def test_ebitda_from_ebit_plus_da(self):
        result = compute_derived_metrics({"ebit": 200, "depreciacao_amortizacao": 50})
        assert result["ebitda"] == 250.0

    def test_ebitda_from_lucro_bruto_minus_opex(self):
        result = compute_derived_metrics({
            "receita_liquida": 1000,
            "custo_receita": 600,
            "despesas_vendas": 100,
            "despesas_administrativas": 50,
            "outras_despesas_operacionais": 30,
            "outras_receitas_operacionais": 20,
        })
        expected_ebitda = 400 - (100 + 50 + 30 - 20) + 0
        assert "ebitda" in result

    def test_ebit_derived_from_ebitda(self):
        result = compute_derived_metrics({"ebitda": 300, "depreciacao_amortizacao": 50})
        assert result["ebit"] == 250.0

    def test_margins_computed(self):
        result = compute_derived_metrics({
            "receita_liquida": 1000,
            "lucro_bruto": 400,
            "ebitda": 200,
            "lucro_liquido": 100,
        })
        assert result["margem_bruta"] == pytest.approx(0.4)
        assert result["margem_ebitda"] == pytest.approx(0.2)
        assert result["margem_liquida"] == pytest.approx(0.1)

    def test_roe_and_roa(self):
        result = compute_derived_metrics({
            "receita_liquida": 1000,
            "lucro_liquido": 100,
            "patrimonio_liquido": 500,
            "total_ativos": 2000,
        })
        assert result["roe"] == pytest.approx(0.2)
        assert result["roa"] == pytest.approx(0.05)
        assert result["giro_ativo"] == pytest.approx(0.5)

    def test_zero_receita_no_margins(self):
        result = compute_derived_metrics({"receita_liquida": 0, "lucro_liquido": 100})
        assert "margem_bruta" not in result

    def test_no_margin_fields(self):
        result = compute_derived_metrics({})
        assert "margem_bruta" not in result


# ---------------------------------------------------------------------------
# _mappings.py tests
# ---------------------------------------------------------------------------
from normalization._mappings import CVM_ACCOUNT_MAP, _DESCRIPTION_PATTERNS


class TestMappings:
    def test_cvm_account_map_keys(self):
        assert "1.01" in CVM_ACCOUNT_MAP
        assert "6.01" in CVM_ACCOUNT_MAP
        assert "11.01" in CVM_ACCOUNT_MAP

    def test_description_patterns_structure(self):
        for canonical, patterns in _DESCRIPTION_PATTERNS.items():
            assert isinstance(patterns, list)
            assert all(isinstance(p, str) for p in patterns)


# ---------------------------------------------------------------------------
# _normalizers.py tests (using mocked FinancialEntry)
# ---------------------------------------------------------------------------
from normalization._normalizers import (
    _resolve_canonical,
    _to_entries,
    normalize_bpa,
    normalize_bpp,
    normalize_dfc,
    normalize_dre,
    normalize_dmpl,
    normalize_dva,
)


class TestResolveCanonical:
    def test_exact_code_match(self):
        entry = _make_entry(cod_conta="1.01", desc_conta="anything")
        assert _resolve_canonical(entry) == "caixa"

    def test_description_pattern_match(self):
        entry = _make_entry(cod_conta="9.99", desc_conta="lucro bruto")
        assert _resolve_canonical(entry) == "lucro_bruto"

    def test_no_match_returns_none(self):
        entry = _make_entry(cod_conta="9.99", desc_conta="unknown account")
        assert _resolve_canonical(entry) is None


class TestToEntries:
    def test_empty_rows(self):
        assert _to_entries([]) == []

    def test_financial_entry_passthrough(self):
        from connectors.cvm import FinancialEntry

        entry = FinancialEntry(
            cnpj="123",
            nome_empresa="Test",
            cod_cvm="1",
            dt_referencia="2024-01-01",
            versao=1,
            cod_conta="1.01",
            desc_conta="Caixa",
            valor=100.0,
            moeda="REAL",
            escala="MIL",
            dt_inicio_exercicio="2024-01-01",
            ordem_exercicio="Único",
            grupo_demonstracao="BPA",
            coluna_demonstracao="Colunístico",
        )
        result = _to_entries([entry])
        assert len(result) == 1

    def test_dict_converted(self):
        rows = [{"cod_conta": "1.01", "desc_conta": "Caixa", "valor": "100.5"}]
        entries = _to_entries(rows)
        assert len(entries) == 1

    def test_dict_with_vl_CONTA(self):
        rows = [{"CD_CONTA": "1.01", "DS_CONTA": "Caixa", "VL_CONTA": "200"}]
        entries = _to_entries(rows)
        assert len(entries) == 1

    def test_missing_value_raises(self):
        rows = [{"cod_conta": "1.01", "desc_conta": "Caixa"}]
        with pytest.raises(ValueError, match="no value"):
            _to_entries(rows)

    def test_empty_value_raises(self):
        rows = [{"cod_conta": "1.01", "desc_conta": "Caixa", "valor": ""}]
        with pytest.raises(ValueError, match="no value"):
            _to_entries(rows)


class TestNormalizeBPA:
    def test_basic_assets(self):
        rows = [
            {"cod_conta": "1.01", "desc_conta": "Caixa", "valor": "100"},
            {"cod_conta": "2.02", "desc_conta": "Imobilizado", "valor": "500"},
        ]
        result = normalize_bpa(rows)
        assert result["caixa"] == 100.0
        assert result["imobilizado"] == 500.0
        assert result["ativo_circulante"] == 100.0
        assert result["ativo_nao_circulante"] == 500.0
        assert result["total_ativos"] == 600.0

    def test_empty_rows(self):
        result = normalize_bpa([])
        assert result["total_ativos"] == 0.0

    def test_unresolved_entries_ignored(self):
        rows = [{"cod_conta": "9.99", "desc_conta": "unknown", "valor": "100"}]
        result = normalize_bpa(rows)
        assert result["total_ativos"] == 0.0


class TestNormalizeBPP:
    def test_basic_liabilities_and_equity(self):
        rows = [
            {"cod_conta": "3.01", "desc_conta": "Fornecedores", "valor": "200"},
            {"cod_conta": "4.01", "desc_conta": "Empréstimos não circulantes", "valor": "300"},
            {"cod_conta": "5.01", "desc_conta": "Capital social", "valor": "500"},
        ]
        result = normalize_bpp(rows)
        assert result["passivo_circulante"] == 200.0
        assert result["passivo_nao_circulante"] == 300.0
        assert result["total_passivo"] == 500.0
        assert result["patrimonio_liquido"] == 500.0


class TestNormalizeDRE:
    def test_basic_revenue(self):
        rows = [{"cod_conta": "6.01", "desc_conta": "Receita líquida", "valor": "1000"}]
        result = normalize_dre(rows)
        assert result["receita_liquida"] == 1000.0


class TestNormalizeDFC:
    def test_basic(self):
        rows = [{"cod_conta": "11.01", "desc_conta": "Lucro/prejuízo líquido", "valor": "100"}]
        result = normalize_dfc(rows)
        assert result["lucro_liquido"] == 100.0


class TestNormalizeDMPL:
    def test_delegates_to_dfc(self):
        rows = [{"cod_conta": "11.01", "desc_conta": "Lucro/prejuízo líquido", "valor": "100"}]
        result = normalize_dmpl(rows)
        assert result["lucro_liquido"] == 100.0


class TestNormalizeDVA:
    def test_delegates_to_dfc(self):
        rows = [{"cod_conta": "11.01", "desc_conta": "Lucro/prejuízo líquido", "valor": "100"}]
        result = normalize_dva(rows)
        assert result["lucro_liquido"] == 100.0


# ---------------------------------------------------------------------------
# Package __init__ re-exports
# ---------------------------------------------------------------------------
class TestPackageInit:
    def test_imports(self):
        from normalization import (
            CVM_ACCOUNT_MAP,
            compute_derived_metrics,
            normalize_bpa,
            normalize_bpp,
            normalize_dfc,
            normalize_dre,
        )
        assert callable(compute_derived_metrics)
        assert callable(normalize_bpa)
        assert callable(normalize_bpp)
        assert callable(normalize_dfc)
        assert callable(normalize_dre)
        assert isinstance(CVM_ACCOUNT_MAP, dict)

    def test_financials_reexports(self):
        from normalization._financials import (
            CVM_ACCOUNT_MAP,
            compute_derived_metrics,
            normalize_bpa,
            normalize_bpp,
            normalize_dfc,
            normalize_dre,
        )
        assert callable(compute_derived_metrics)
