"""Golden tests for Fase 2 financial statement types (F2-PR05.6).

Validate that CVM fixture CSVs parse into expected FinancialEntry objects
per statement type. All tests are offline (no network calls).
"""

from __future__ import annotations

import csv
from decimal import Decimal
from pathlib import Path

import pytest

from connectors.cvm._financials import FinancialEntry, StatementType, _parse, parse_value_status

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "cvm"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_csv(filename: str) -> list[dict[str, str]]:
    path = FIXTURES_DIR / filename
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh, delimiter=";"))


def _parse_fixture(filename: str, cnpj: str | None = None) -> list[FinancialEntry]:
    rows = _load_csv(filename)
    return _parse(rows, cnpj)


def _filter_by_tp(rows: list[dict[str, str]], tp: str) -> list[dict[str, str]]:
    return [r for r in rows if (r.get("TP_CONTA") or "").strip() == tp]


# ---------------------------------------------------------------------------
# DFP (Demonstrativo Financeiro Padronizado) — Anual
# ---------------------------------------------------------------------------


class TestDFPBPA:
    """Golden: Balanço Patrimonial Ativo from DFP fixture."""

    def test_total_entries(self) -> None:
        entries = _parse_fixture("dfp_cia_aberta_sample.csv")
        bpa = [e for e in entries if e.cod_conta.startswith("1") or e.cod_conta.startswith("2")]
        assert len(bpa) == 9

    def test_ativo_total(self) -> None:
        entries = _parse_fixture("dfp_cia_aberta_sample.csv")
        ativo = next(e for e in entries if e.cod_conta == "1")
        assert ativo.cnpj == "33.000.167/0001-01"
        assert ativo.dt_referencia == "2024-12-31"
        assert ativo.versao == 1
        assert ativo.desc_conta == "Ativo Total"
        assert ativo.valor == pytest.approx(898_124_000_000.0)
        assert ativo.moeda == "REAL"
        assert ativo.escala == "MIL"

    def test_ativo_circulante(self) -> None:
        entries = _parse_fixture("dfp_cia_aberta_sample.csv")
        ac = next(e for e in entries if e.cod_conta == "1.01")
        assert ac.desc_conta == "Ativo Circulante"
        assert ac.valor == pytest.approx(215_436_000_000.0)

    def test_caixa(self) -> None:
        entries = _parse_fixture("dfp_cia_aberta_sample.csv")
        caixa = next(e for e in entries if e.cod_conta == "1.01.01")
        assert caixa.desc_conta == "Caixa e Equivalentes de Caixa"
        assert caixa.valor == pytest.approx(100_609_000_000.0)

    def test_ativo_nao_circulante(self) -> None:
        entries = _parse_fixture("dfp_cia_aberta_sample.csv")
        anc = next(e for e in entries if e.cod_conta == "1.02")
        assert anc.desc_conta == "Ativo Não Circulante"
        assert anc.valor == pytest.approx(682_688_000_000.0)

    def test_passivo_e_patrimonio(self) -> None:
        entries = _parse_fixture("dfp_cia_aberta_sample.csv")
        pp = next(e for e in entries if e.cod_conta == "2")
        assert pp.desc_conta == "Passivo e Patrimônio Líquido"
        assert pp.valor == pytest.approx(898_124_000_000.0)

    def test_passivo_circulante(self) -> None:
        entries = _parse_fixture("dfp_cia_aberta_sample.csv")
        pc = next(e for e in entries if e.cod_conta == "2.01")
        assert pc.desc_conta == "Passivo Circulante"
        assert pc.valor == pytest.approx(187_306_000_000.0)

    def test_passivo_nao_circulante(self) -> None:
        entries = _parse_fixture("dfp_cia_aberta_sample.csv")
        pnc = next(e for e in entries if e.cod_conta == "2.02")
        assert pnc.desc_conta == "Passivo Não Circulante"
        assert pnc.valor == pytest.approx(356_498_000_000.0)

    def test_patrimonio_liquido(self) -> None:
        entries = _parse_fixture("dfp_cia_aberta_sample.csv")
        pl = next(e for e in entries if e.cod_conta == "2.03")
        assert pl.desc_conta == "Patrimônio Líquido"
        assert pl.valor == pytest.approx(354_320_000_000.0)


class TestDFPDRE:
    """Golden: Demonstração de Resultado do Exercício from DFP fixture."""

    def test_total_dre_entries(self) -> None:
        entries = _parse_fixture("dfp_cia_aberta_sample.csv")
        dre_codes = {"3", "3.01", "3.02", "4", "5", "6", "6.01"}
        dre = [e for e in entries if e.cod_conta in dre_codes]
        assert len(dre) == 7

    def test_receita_liquida(self) -> None:
        entries = _parse_fixture("dfp_cia_aberta_sample.csv")
        rl = next(e for e in entries if e.cod_conta == "3")
        assert rl.cnpj == "33.000.167/0001-01"
        assert rl.dt_referencia == "2024-12-31"
        assert rl.versao == 1
        assert rl.desc_conta == "Receita Líquida"
        assert rl.valor == pytest.approx(389_383_000_000.0)

    def test_receita_vendas(self) -> None:
        entries = _parse_fixture("dfp_cia_aberta_sample.csv")
        rv = next(e for e in entries if e.cod_conta == "3.01")
        assert rv.desc_conta == "Receita de Vendas e de Prestação de Serviços"
        assert rv.valor == pytest.approx(425_601_000_000.0)

    def test_impostos_sobre_receita(self) -> None:
        entries = _parse_fixture("dfp_cia_aberta_sample.csv")
        imp = next(e for e in entries if e.cod_conta == "3.02")
        assert imp.desc_conta == "(-) Impostos sobre Receita"
        assert imp.valor == pytest.approx(36_218_000_000.0)

    def test_lucro_bruto(self) -> None:
        entries = _parse_fixture("dfp_cia_aberta_sample.csv")
        lb = next(e for e in entries if e.cod_conta == "4")
        assert lb.desc_conta == "Lucro Bruto"
        assert lb.valor == pytest.approx(239_876_000_000.0)

    def test_lucro_antes_ir_cs(self) -> None:
        entries = _parse_fixture("dfp_cia_aberta_sample.csv")
        la = next(e for e in entries if e.cod_conta == "5")
        assert la.desc_conta == "Lucro (Prejuízo) Antes do IR e CS"
        assert la.valor == pytest.approx(135_349_000_000.0)

    def test_lucro_liquido(self) -> None:
        entries = _parse_fixture("dfp_cia_aberta_sample.csv")
        ll = next(e for e in entries if e.cod_conta == "6")
        assert ll.desc_conta == "Lucro (Prejuízo) Líquido do Exercício"
        assert ll.valor == pytest.approx(102_918_000_000.0)

    def test_lucro_consolidado(self) -> None:
        entries = _parse_fixture("dfp_cia_aberta_sample.csv")
        lc = next(e for e in entries if e.cod_conta == "6.01")
        assert lc.desc_conta == "Lucro (Prejuízo) Consolidado do Exercício"
        assert lc.valor == pytest.approx(102_918_000_000.0)


# ---------------------------------------------------------------------------
# ITR (Informações Trimestrais) — Quarterly
# ---------------------------------------------------------------------------


class TestITRBPA:
    """Golden: Balanço Patrimonial Ativo from ITR fixture."""

    def test_total_entries(self) -> None:
        entries = _parse_fixture("itr_cia_aberta_sample.csv")
        bpa = [e for e in entries if e.cod_conta.startswith("1") or e.cod_conta.startswith("2")]
        assert len(bpa) == 7

    def test_ativo_total(self) -> None:
        entries = _parse_fixture("itr_cia_aberta_sample.csv")
        ativo = next(e for e in entries if e.cod_conta == "1")
        assert ativo.cnpj == "60.872.504/0001-12"
        assert ativo.dt_referencia == "2024-09-30"
        assert ativo.versao == 1
        assert ativo.desc_conta == "Ativo Total"
        assert ativo.valor == pytest.approx(2_701_523_000_000.0)
        assert ativo.moeda == "REAL"
        assert ativo.escala == "MIL"

    def test_ativo_circulante(self) -> None:
        entries = _parse_fixture("itr_cia_aberta_sample.csv")
        ac = next(e for e in entries if e.cod_conta == "1.01")
        assert ac.desc_conta == "Ativo Circulante"
        assert ac.valor == pytest.approx(1_003_727_000_000.0)

    def test_ativo_nao_circulante(self) -> None:
        entries = _parse_fixture("itr_cia_aberta_sample.csv")
        anc = next(e for e in entries if e.cod_conta == "1.02")
        assert anc.desc_conta == "Ativo Não Circulante"
        assert anc.valor == pytest.approx(1_697_796_000_000.0)

    def test_passivo_circulante(self) -> None:
        entries = _parse_fixture("itr_cia_aberta_sample.csv")
        pc = next(e for e in entries if e.cod_conta == "2.01")
        assert pc.desc_conta == "Passivo Circulante"
        assert pc.valor == pytest.approx(652_899_000_000.0)

    def test_passivo_nao_circulante(self) -> None:
        entries = _parse_fixture("itr_cia_aberta_sample.csv")
        pnc = next(e for e in entries if e.cod_conta == "2.02")
        assert pnc.desc_conta == "Passivo Não Circulante"
        assert pnc.valor == pytest.approx(1_165_448_000_000.0)

    def test_patrimonio_liquido(self) -> None:
        entries = _parse_fixture("itr_cia_aberta_sample.csv")
        pl = next(e for e in entries if e.cod_conta == "2.03")
        assert pl.desc_conta == "Patrimônio Líquido"
        assert pl.valor == pytest.approx(883_176_000_000.0)


class TestITRDRE:
    """Golden: Demonstração de Resultado do Exercício from ITR fixture."""

    def test_total_dre_entries(self) -> None:
        entries = _parse_fixture("itr_cia_aberta_sample.csv")
        dre_codes = {"3", "6"}
        dre = [e for e in entries if e.cod_conta in dre_codes]
        assert len(dre) == 2

    def test_receita_liquida(self) -> None:
        entries = _parse_fixture("itr_cia_aberta_sample.csv")
        rl = next(e for e in entries if e.cod_conta == "3")
        assert rl.cnpj == "60.872.504/0001-12"
        assert rl.dt_referencia == "2024-09-30"
        assert rl.versao == 1
        assert rl.desc_conta == "Receita Líquida"
        assert rl.valor == pytest.approx(1_795_354_000_000.0)

    def test_lucro_liquido(self) -> None:
        entries = _parse_fixture("itr_cia_aberta_sample.csv")
        ll = next(e for e in entries if e.cod_conta == "6")
        assert ll.desc_conta == "Lucro (Prejuízo) Líquido do Exercício"
        assert ll.valor == pytest.approx(374_060_000_000.0)


# ---------------------------------------------------------------------------
# Scope: individual vs consolidated
# ---------------------------------------------------------------------------


class TestScopeFiltering:
    """Validate that _parse respects CNPJ filtering (scope control)."""

    def test_cnpj_filter_returns_only_matching(self) -> None:
        entries_dfp = _parse_fixture("dfp_cia_aberta_sample.csv")
        entries_filtered = _parse_fixture("dfp_cia_aberta_sample.csv", cnpj="33.000.167/0001-01")
        assert len(entries_filtered) == len(entries_dfp)

    def test_cnpj_filter_excludes_non_matching(self) -> None:
        entries = _parse_fixture("dfp_cia_aberta_sample.csv", cnpj="99.999.999/0001-99")
        assert entries == []

    def test_itr_cnpj_filter(self) -> None:
        entries = _parse_fixture("itr_cia_aberta_sample.csv", cnpj="60.872.504/0001-12")
        assert len(entries) == 9

    def test_itr_cnpj_filter_no_match(self) -> None:
        entries = _parse_fixture("itr_cia_aberta_sample.csv", cnpj="00.000.000/0001-00")
        assert entries == []


# ---------------------------------------------------------------------------
# parse_value_status — edge cases
# ---------------------------------------------------------------------------


class TestParseValueStatus:
    """Golden: parse_value_status returns (value, status) tuples."""

    def test_valid_number(self) -> None:
        val, status = parse_value_status("1.234.567,89")
        assert val == Decimal("1234567.89")
        assert status == "reported"

    def test_simple_decimal(self) -> None:
        val, status = parse_value_status("1234.56")
        assert val == Decimal("1234.56")
        assert status == "reported"

    def test_integer_value(self) -> None:
        val, status = parse_value_status("100")
        assert val == Decimal("100")
        assert status == "reported"

    def test_empty_string(self) -> None:
        val, status = parse_value_status("")
        assert val is None
        assert status == "missing"

    def test_whitespace_only(self) -> None:
        val, status = parse_value_status("   ")
        assert val is None
        assert status == "missing"

    def test_na_value(self) -> None:
        val, status = parse_value_status("N/A")
        assert val is None
        assert status == "not_applicable"

    def test_na_lowercase(self) -> None:
        val, status = parse_value_status("na")
        assert val is None
        assert status == "not_applicable"

    def test_nao_aplicavel(self) -> None:
        val, status = parse_value_status("não aplicável")
        assert val is None
        assert status == "not_applicable"

    def test_suppressed_single_dash(self) -> None:
        val, status = parse_value_status("-")
        assert val is None
        assert status == "suppressed"

    def test_suppressed_double_dash(self) -> None:
        val, status = parse_value_status("--")
        assert val is None
        assert status == "suppressed"

    def test_parse_error_non_numeric(self) -> None:
        val, status = parse_value_status("abc")
        assert val is None
        assert status == "parse_error"

    def test_brazilian_format_thousands(self) -> None:
        val, status = parse_value_status("1.234.567")
        assert val == Decimal("1234567")
        assert status == "reported"

    def test_negative_value(self) -> None:
        val, status = parse_value_status("-1.234,56")
        assert val == Decimal("-1234.56")
        assert status == "reported"

    def test_zero_value(self) -> None:
        val, status = parse_value_status("0")
        assert val == Decimal("0")
        assert status == "reported"


# ---------------------------------------------------------------------------
# FinancialEntry defaults and to_dict
# ---------------------------------------------------------------------------


class TestFinancialEntry:
    """Golden: FinancialEntry dataclass construction and serialization."""

    def test_default_values(self) -> None:
        e = FinancialEntry(
            cnpj="00.000.000/0001-00",
            nome_empresa="Test",
            cod_cvm="0",
            dt_referencia="2024-12-31",
        )
        assert e.versao == 0
        assert e.cod_conta == ""
        assert e.desc_conta == ""
        assert e.valor == 0.0
        assert e.moeda == "REAL"
        assert e.escala == "MIL"
        assert e.dt_inicio_exercicio == ""
        assert e.ordem_exercicio == ""
        assert e.grupo_demonstracao == ""
        assert e.coluna_demonstracao == ""

    def test_to_dict_roundtrip(self) -> None:
        e = FinancialEntry(
            cnpj="33.000.167/0001-01",
            nome_empresa="Petrobras",
            cod_cvm="9512",
            dt_referencia="2024-12-31",
            versao=1,
            cod_conta="1",
            desc_conta="Ativo Total",
            valor=898_124_000_000.0,
        )
        d = e.to_dict()
        assert d["cnpj"] == "33.000.167/0001-01"
        assert d["cod_conta"] == "1"
        assert d["valor"] == 898_124_000_000.0
        assert len(d) == 14


# ---------------------------------------------------------------------------
# StatementType enum
# ---------------------------------------------------------------------------


class TestStatementType:
    """Golden: StatementType enum values."""

    def test_bpa_con(self) -> None:
        assert StatementType.BPA_CON == "BPA_con"

    def test_bpp_ind(self) -> None:
        assert StatementType.BPP_IND == "BPP_ind"

    def test_dre_con(self) -> None:
        assert StatementType.DRE_CON == "DRE_con"

    def test_all_types_unique(self) -> None:
        values = [s.value for s in StatementType]
        assert len(values) == len(set(values))
