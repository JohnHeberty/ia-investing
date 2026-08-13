"""Unit tests for connectors.cvm._cad — CVM company registration."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from connectors.cvm._cad import _normalize_cnpj, get_companies, get_company_by_cnpj


@pytest.mark.unit
class TestNormalizeCnpj:
    def test_strips_punctuation(self):
        assert _normalize_cnpj("12.345.678/0001-90") == "12345678000190"

    def test_already_clean(self):
        assert _normalize_cnpj("12345678000190") == "12345678000190"

    def test_empty(self):
        assert _normalize_cnpj("") == ""


@pytest.mark.unit
class TestGetCompanies:
    @pytest.mark.asyncio
    async def test_filters_by_cnpj(self):
        mock_rows = [
            {"CNPJ": "12.345.678/0001-90", "Nome": "Empresa A"},
            {"CNPJ": "98.765.432/0001-10", "Nome": "Empresa B"},
        ]
        with patch("connectors.cvm._parser.fetch_csv", new_callable=AsyncMock, return_value=mock_rows):
            result = await get_companies(cnpj="12.345.678/0001-90")
        assert len(result) == 1
        assert result[0]["Nome"] == "Empresa A"

    @pytest.mark.asyncio
    async def test_no_filter_returns_all(self):
        mock_rows = [{"CNPJ": "111"}, {"CNPJ": "222"}]
        with patch("connectors.cvm._parser.fetch_csv", new_callable=AsyncMock, return_value=mock_rows):
            result = await get_companies()
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_no_match_returns_empty(self):
        mock_rows = [{"CNPJ": "111"}]
        with patch("connectors.cvm._parser.fetch_csv", new_callable=AsyncMock, return_value=mock_rows):
            result = await get_companies(cnpj="999")
        assert result == []


@pytest.mark.unit
class TestGetCompanyByCnpj:
    @pytest.mark.asyncio
    async def test_returns_most_recent(self):
        mock_rows = [
            {"CNPJ": "123", "Data_Referencia": "2025-01-01", "Nome": "Old"},
            {"CNPJ": "123", "Data_Referencia": "2026-06-01", "Nome": "New"},
        ]
        with patch("connectors.cvm._parser.fetch_csv", new_callable=AsyncMock, return_value=mock_rows):
            result = await get_company_by_cnpj("123")
        assert result is not None
        assert result["Nome"] == "New"

    @pytest.mark.asyncio
    async def test_not_found_returns_none(self):
        with patch("connectors.cvm._parser.fetch_csv", new_callable=AsyncMock, return_value=[]):
            result = await get_company_by_cnpj("999")
        assert result is None
