"""Tests for connectors.cvm — parser, financials, directory, cad, fca."""

from __future__ import annotations

import io
import zipfile
from unittest.mock import AsyncMock, patch

import pytest

from connectors.cvm._cad import _normalize_cnpj
from connectors.cvm._directory import (
    _CACHE,
    _LISTING_PATTERN,
    _PERIOD_RE,
    _cache_get,
    _cache_set,
    latest_period,
    list_files,
    list_periods,
)
from connectors.cvm._financials import (
    FinancialEntry,
    StatementType,
    _parse,
    _parse_valor,
    parse_value_status,
)
from connectors.cvm._financials import (
    _normalize_cnpj as fin_normalize_cnpj,
)
from connectors.cvm._parser import fetch_csv, fetch_csv_from_zip
from connectors.cvm.fca import FCAGeneral, _int_opt, _opt

# ---------------------------------------------------------------------------
# _parser.py
# ---------------------------------------------------------------------------


def _make_csv_bytes(content: str) -> bytes:
    return content.encode("iso-8859-1")


def _make_zip_with_csv(filename: str, content: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(filename, content)
    return buf.getvalue()


@pytest.mark.asyncio
class TestFetchCsv:
    async def test_parses_semicolon_csv(self) -> None:
        csv_content = "CNPJ;Nome\n123;Empresa\n"
        mock_client = AsyncMock()
        mock_client.get_bytes = AsyncMock(return_value=_make_csv_bytes(csv_content))
        result = await fetch_csv("http://example.com/test.csv", client=mock_client)
        assert len(result) == 1
        assert result[0]["CNPJ"] == "123"

    async def test_creates_default_client(self) -> None:
        csv_content = "A;B\n1;2\n"
        with patch("connectors.cvm._parser.HttpClient") as MockClient:
            instance = AsyncMock()
            instance.get_bytes = AsyncMock(return_value=_make_csv_bytes(csv_content))
            MockClient.return_value = instance
            result = await fetch_csv("http://example.com/test.csv")
            assert len(result) == 1


@pytest.mark.asyncio
class TestFetchCsvFromZip:
    async def test_parses_csv_in_zip(self) -> None:
        csv_content = "X;Y\n1;2\n"
        zip_bytes = _make_zip_with_csv("data.csv", csv_content)
        mock_client = AsyncMock()
        mock_client.get_bytes = AsyncMock(return_value=zip_bytes)
        result = await fetch_csv_from_zip("http://example.com/test.zip", client=mock_client)
        assert len(result) == 1
        assert result[0]["X"] == "1"

    async def test_filters_by_filename(self) -> None:
        csv1 = "A;B\n1;2\n"
        csv2 = "C;D\n3;4\n"
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("target_data.csv", csv1)
            zf.writestr("other_data.csv", csv2)
        mock_client = AsyncMock()
        mock_client.get_bytes = AsyncMock(return_value=buf.getvalue())
        result = await fetch_csv_from_zip("http://example.com/test.zip", filename_contains="target", client=mock_client)
        assert len(result) == 1
        assert "A" in result[0]

    async def test_skips_non_csv_files(self) -> None:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("readme.txt", "not csv")
            zf.writestr("data.csv", "X;Y\n1;2\n")
        mock_client = AsyncMock()
        mock_client.get_bytes = AsyncMock(return_value=buf.getvalue())
        result = await fetch_csv_from_zip("http://example.com/test.zip", client=mock_client)
        assert len(result) == 1

    async def test_empty_zip(self) -> None:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("empty.csv", "")
        mock_client = AsyncMock()
        mock_client.get_bytes = AsyncMock(return_value=buf.getvalue())
        result = await fetch_csv_from_zip("http://example.com/test.zip", client=mock_client)
        assert result == []


# ---------------------------------------------------------------------------
# _financials.py
# ---------------------------------------------------------------------------


class TestParseValor:
    def test_simple_integer(self) -> None:
        assert _parse_valor("1234") == 1234.0

    def test_brazilian_format(self) -> None:
        assert _parse_valor("1.234.567,89") == pytest.approx(1234567.89)

    def test_single_dot_decimal(self) -> None:
        assert _parse_valor("1234.56") == pytest.approx(1234.56)

    def test_empty_raises(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            _parse_valor("")

    def test_whitespace_raises(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            _parse_valor("   ")

    def test_multiple_dots_thousands(self) -> None:
        assert _parse_valor("1.234.567") == 1234567.0

    def test_negative(self) -> None:
        assert _parse_valor("-1.234,56") == pytest.approx(-1234.56)


class TestParseValueStatus:
    def test_empty_returns_missing(self) -> None:
        val, status = parse_value_status("")
        assert val is None
        assert status == "missing"

    def test_na_returns_not_applicable(self) -> None:
        val, status = parse_value_status("N/A")
        assert val is None
        assert status == "not_applicable"

    def test_suppressed(self) -> None:
        val, status = parse_value_status("-")
        assert val is None
        assert status == "suppressed"

    def test_double_dash_suppressed(self) -> None:
        val, status = parse_value_status("--")
        assert val is None
        assert status == "suppressed"

    def test_valid_number(self) -> None:
        val, status = parse_value_status("1.234,56")
        assert val is not None
        assert status == "reported"
        assert float(val) == pytest.approx(1234.56)

    def test_invalid_returns_parse_error(self) -> None:
        val, status = parse_value_status("abc")
        assert val is None
        assert status == "parse_error"

    def test_nao_aplicavel(self) -> None:
        val, status = parse_value_status("Não Aplicável")
        assert val is None
        assert status == "not_applicable"


class TestNormalizeCnpj:
    def test_strips_formatting(self) -> None:
        assert fin_normalize_cnpj("33.000.167/0001-01") == "33000167000101"

    def test_already_clean(self) -> None:
        assert fin_normalize_cnpj("33000167000101") == "33000167000101"


class TestParseFinancials:
    def test_filters_by_cnpj(self) -> None:
        rows = [
            {
                "CNPJ_CIA": "33.000.167/0001-01",
                "DENOM_CIA": "Empresa A",
                "CD_CVM": "123",
                "DT_REFER": "2025-01-01",
                "VERSAO": "1",
                "VL_CONTA": "1000",
                "CD_CONTA": "1.01",
                "DS_CONTA": "Ativo",
            },
            {
                "CNPJ_CIA": "99.999.999/0001-99",
                "DENOM_CIA": "Empresa B",
                "CD_CVM": "456",
                "DT_REFER": "2025-01-01",
                "VERSAO": "1",
                "VL_CONTA": "2000",
                "CD_CONTA": "1.01",
                "DS_CONTA": "Ativo",
            },
        ]
        result = _parse(rows, "33.000.167/0001-01")
        assert len(result) == 1
        assert result[0].cnpj == "33.000.167/0001-01"

    def test_no_filter_returns_all(self) -> None:
        rows = [
            {
                "CNPJ_CIA": "33.000.167/0001-01",
                "DENOM_CIA": "A",
                "CD_CVM": "1",
                "DT_REFER": "2025-01-01",
                "VERSAO": "1",
                "VL_CONTA": "100",
            },
            {
                "CNPJ_CIA": "99.999.999/0001-99",
                "DENOM_CIA": "B",
                "CD_CVM": "2",
                "DT_REFER": "2025-01-01",
                "VERSAO": "1",
                "VL_CONTA": "200",
            },
        ]
        result = _parse(rows, None)
        assert len(result) == 2

    def test_invalid_versao_raises(self) -> None:
        rows = [
            {
                "CNPJ_CIA": "33.000.167/0001-01",
                "DENOM_CIA": "A",
                "CD_CVM": "1",
                "DT_REFER": "2025-01-01",
                "VERSAO": "abc",
                "VL_CONTA": "100",
            }
        ]
        with pytest.raises(ValueError, match="invalid VERSAO"):
            _parse(rows, None)

    def test建造s_financial_entry(self) -> None:
        rows = [
            {
                "CNPJ_CIA": "33.000.167/0001-01",
                "DENOM_CIA": "Empresa",
                "CD_CVM": "123",
                "DT_REFER": "2025-01-01",
                "VERSAO": "2",
                "CD_CONTA": "1.01",
                "DS_CONTA": "Ativo Circulante",
                "VL_CONTA": "5000",
                "MOEDA": "REAL",
                "ESCALA_MOEDA": "MIL",
                "DT_INI_EXERC": "2024-01-01",
                "ORDEM_EXERC": "1º",
                "GRUPO_DFP": "DFP Consolidado",
                "COLUNA_DF": "Colum1",
            }
        ]
        result = _parse(rows, None)
        assert len(result) == 1
        e = result[0]
        assert e.cod_conta == "1.01"
        assert e.valor == 5000.0
        assert e.moeda == "REAL"


class TestFinancialEntryToDict:
    def test_to_dict(self) -> None:
        e = FinancialEntry(cnpj="123", nome_empresa="Test", cod_cvm="1", dt_referencia="2025-01-01")
        d = e.to_dict()
        assert d["cnpj"] == "123"
        assert d["valor"] == 0.0


class TestStatementType:
    def test_all_values(self) -> None:
        assert len(StatementType) == 14
        assert StatementType.BPA_CON.value == "BPA_con"
        assert StatementType.DRE_CON.value == "DRE_con"


# ---------------------------------------------------------------------------
# _directory.py
# ---------------------------------------------------------------------------


class TestDirectoryPatterns:
    def test_listing_pattern(self) -> None:
        html = '<a href="data_202501.zip"><a href="file.csv">'
        matches = _LISTING_PATTERN.findall(html)
        assert "data_202501.zip" in matches
        assert "file.csv" in matches

    def test_period_pattern_year(self) -> None:
        match = _PERIOD_RE.search("data_2025.zip")
        assert match is not None
        assert match.group(1) == "2025"

    def test_period_pattern_yearmonth(self) -> None:
        match = _PERIOD_RE.search("data_202501.zip")
        assert match is not None
        assert match.group(1) == "202501"


@pytest.mark.asyncio
class TestDirectoryCache:
    async def test_cache_set_and_get(self) -> None:
        _CACHE.clear()
        await _cache_set("test_key", ["file1.zip"])
        result = await _cache_get("test_key")
        assert result == ["file1.zip"]

    async def test_cache_miss(self) -> None:
        _CACHE.clear()
        result = await _cache_get("nonexistent_key_xyz")
        assert result is None


@pytest.mark.asyncio
class TestListFiles:
    async def test_returns_sorted_files(self) -> None:
        _CACHE.clear()
        html = '<a href="b.zip"><a href="a.csv"><a href="c.txt">'
        mock_client = AsyncMock()
        mock_client.get_bytes = AsyncMock(return_value=html.encode())
        result = await list_files("CAT_FILES", "PROD", client=mock_client)
        assert result == ["a.csv", "b.zip", "c.txt"]


@pytest.mark.asyncio
class TestListPeriods:
    async def test_extracts_periods(self) -> None:
        _CACHE.clear()
        html = '<a href="data_202501.zip"><a href="data_202502.zip"><a href="data_2024.zip">'
        mock_client = AsyncMock()
        mock_client.get_bytes = AsyncMock(return_value=html.encode())
        periods = await list_periods("CAT_PERIODS", "PROD", client=mock_client)
        assert "202501" in periods
        assert "2024" in periods


@pytest.mark.asyncio
class TestLatestPeriod:
    async def test_returns_last_period(self) -> None:
        _CACHE.clear()
        html = '<a href="data_2024.zip"><a href="data_202501.zip">'
        mock_client = AsyncMock()
        mock_client.get_bytes = AsyncMock(return_value=html.encode())
        result = await latest_period("CAT", "PROD", client=mock_client)
        assert result is not None

    async def test_returns_none_when_empty(self) -> None:
        _CACHE.clear()
        html = '<a href="readme.txt">'
        mock_client = AsyncMock()
        mock_client.get_bytes = AsyncMock(return_value=html.encode())
        result = await latest_period("CAT_PROD_EMPTY", "DADOS", client=mock_client)
        assert result is None


# ---------------------------------------------------------------------------
# _cad.py
# ---------------------------------------------------------------------------


class TestCadNormalizeCnpj:
    def test_strips_non_digits(self) -> None:
        assert _normalize_cnpj("33.000.167/0001-01") == "33000167000101"

    def test_already_clean(self) -> None:
        assert _normalize_cnpj("33000167000101") == "33000167000101"


# ---------------------------------------------------------------------------
# fca.py
# ---------------------------------------------------------------------------


class TestFcaHelpers:
    def test_opt_none(self) -> None:
        assert _opt(None) is None

    def test_opt_empty(self) -> None:
        assert _opt("  ") is None

    def test_opt_valid(self) -> None:
        assert _opt("  hello  ") == "hello"

    def test_int_opt_none(self) -> None:
        assert _int_opt(None) is None

    def test_int_opt_empty(self) -> None:
        assert _int_opt("  ") is None

    def test_int_opt_valid(self) -> None:
        assert _int_opt("42") == 42

    def test_int_opt_invalid(self) -> None:
        assert _int_opt("abc") is None


class TestFCAModels:
    def test_fca_general建造s(self) -> None:
        g = FCAGeneral(
            cnpj="123",
            nome_empresarial="Test",
            cod_cvm="1",
            dt_referencia="2025-01-01",
        )
        assert g.cnpj == "123"

    def test_fca_general_optional_fields(self) -> None:
        g = FCAGeneral(
            cnpj="123",
            nome_empresarial="Test",
            cod_cvm="1",
            dt_referencia="2025-01-01",
            setor_atividade="Financeiro",
            pagina_web="https://test.com",
        )
        assert g.setor_atividade == "Financeiro"
        assert g.pagina_web == "https://test.com"
