from __future__ import annotations

import pytest

from connectors.cvm._financials import (
    FinancialEntry,
    StatementType,
    _parse_valor,
    parse_value_status,
)


class TestParseValor:
    @pytest.mark.parametrize(
        "raw, expected",
        [
            ("1.234.567,89", 1234567.89),
            ("1234.56", 1234.56),
            ("0,00", 0.0),
            ("1.234.567.890,12", 1234567890.12),
            ("100", 100.0),
            ("0", 0.0),
        ],
    )
    def test_valid_formats(self, raw, expected):
        assert _parse_valor(raw) == pytest.approx(expected)

    def test_empty_string_is_rejected(self):
        with pytest.raises(ValueError, match="empty"):
            _parse_valor("")

    def test_whitespace_only_is_rejected(self):
        with pytest.raises(ValueError, match="empty"):
            _parse_valor("   ")

    def test_non_numeric_is_rejected(self):
        with pytest.raises(ValueError, match="invalid VL_CONTA"):
            _parse_valor("N/A")

    def test_negative_brazilian_format(self):
        assert _parse_valor("-1.234,56") == pytest.approx(-1234.56)

    def test_no_decimal_separator(self):
        assert _parse_valor("500") == 500.0

    def test_single_comma_decimal_only(self):
        assert _parse_valor("99,9") == pytest.approx(99.9)


class TestStatementType:
    def test_all_members_exist(self):
        expected = {
            "BPA_con",
            "BPA_ind",
            "BPP_con",
            "BPP_ind",
            "DRE_con",
            "DRE_ind",
            "DFC_MD_con",
            "DFC_MD_ind",
            "DFC_MI_con",
            "DFC_MI_ind",
            "DMPL_con",
            "DMPL_ind",
            "DVA_con",
            "DVA_ind",
        }
        actual = {s.value for s in StatementType}
        assert actual == expected


@pytest.mark.parametrize(
    "raw,expected,status",
    [
        ("1.234,50", "1234.50", "reported"),
        ("", None, "missing"),
        ("N/A", None, "not_applicable"),
        ("--", None, "suppressed"),
        ("valor inválido", None, "parse_error"),
    ],
)
def test_value_status_is_explicit(raw, expected, status):
    value, actual_status = parse_value_status(raw)
    actual_value = str(value) if value is not None else None
    assert actual_value == expected
    assert actual_status == status


class TestFinancialEntry:
    def test_to_dict(self):
        entry = FinancialEntry(
            cnpj="12.345.678/0001-90",
            nome_empresa="Teste SA",
            cod_cvm="12345",
            dt_referencia="2024-12-31",
            cod_conta="1.01",
            desc_conta="Caixa",
            valor=1000.0,
        )
        d = entry.to_dict()
        assert d["cnpj"] == "12.345.678/0001-90"
        assert d["valor"] == 1000.0
        assert d["moeda"] == "REAL"
        assert d["escala"] == "MIL"

    def test_repr(self):
        entry = FinancialEntry(
            cnpj="00.000.000/0001-00",
            nome_empresa="X",
            cod_cvm="1",
            dt_referencia="2024-01-01",
        )
        r = repr(entry)
        assert "FinancialEntry" in r
