"""Tests for connectors.b3._downloader — ZIP fetch and parse."""

from __future__ import annotations

import io
import zipfile
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from connectors.b3._downloader import _fetch, RECORD_TIPREG
from connectors.b3._models import CotahistTrade


def _build_trade_line(
    ticker: str = "PETR4",
    date_str: str = "20240326",
    cod_bdi: str = "02",
    close_price: int = 3870,
) -> str:
    buf = [" "] * 245
    buf[0:2] = list("01")
    buf[2:10] = list(date_str)
    buf[10:12] = list(cod_bdi)
    buf[12:24] = list(ticker.ljust(12))
    buf[110:123] = list(str(close_price).rjust(13))
    line = "".join(buf)
    assert len(line) == 245, f"Expected 245 chars, got {len(line)}"
    return line


def _make_zip(txt_content: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("COTAHIST_A2024.TXT", txt_content)
    return buf.getvalue()


def _make_multi_file_zip(*filenames_content: tuple[str, str]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, content in filenames_content:
            zf.writestr(name, content)
    return buf.getvalue()


@pytest.mark.asyncio
class TestFetch:
    async def test_parses_valid_trade_from_zip(self) -> None:
        line = _build_trade_line()
        zip_bytes = _make_zip(line)
        mock_client = AsyncMock()
        mock_client.get_bytes = AsyncMock(return_value=zip_bytes)

        results = await _fetch("http://example.com/test.zip", client=mock_client)
        assert len(results) == 1
        assert results[0].ticker == "PETR4"
        assert results[0].trade_date == date(2024, 3, 26)

    async def test_filters_by_ticker(self) -> None:
        line1 = _build_trade_line(ticker="PETR4      ")
        line2 = _build_trade_line(ticker="VALE3      ")
        zip_bytes = _make_zip(line1 + "\n" + line2)
        mock_client = AsyncMock()
        mock_client.get_bytes = AsyncMock(return_value=zip_bytes)

        results = await _fetch("http://example.com/test.zip", ticker="PETR4", client=mock_client)
        assert len(results) == 1
        assert results[0].ticker == "PETR4"

    async def test_filters_by_market_code(self) -> None:
        line1 = _build_trade_line(cod_bdi="02")
        line2 = _build_trade_line(ticker="VALE3      ", cod_bdi="96")
        zip_bytes = _make_zip(line1 + "\n" + line2)
        mock_client = AsyncMock()
        mock_client.get_bytes = AsyncMock(return_value=zip_bytes)

        results = await _fetch("http://example.com/test.zip", market_codes=["02"], client=mock_client)
        assert len(results) == 1
        assert results[0].cod_bdi == "02"

    async def test_skips_non_txt_files(self) -> None:
        line = _build_trade_line()
        zip_bytes = io.BytesIO()
        with zipfile.ZipFile(zip_bytes, "w") as zf:
            zf.writestr("readme.md", "not a data file")
            zf.writestr("COTAHIST_A2024.TXT", line)
        mock_client = AsyncMock()
        mock_client.get_bytes = AsyncMock(return_value=zip_bytes.getvalue())

        results = await _fetch("http://example.com/test.zip", client=mock_client)
        assert len(results) == 1

    async def test_skips_header_and_footer_lines(self) -> None:
        header = "00" + " " * 243
        footer = "99" + " " * 243
        line = _build_trade_line()
        content = f"{header}\n{line}\n{footer}"
        zip_bytes = _make_zip(content)
        mock_client = AsyncMock()
        mock_client.get_bytes = AsyncMock(return_value=zip_bytes)

        results = await _fetch("http://example.com/test.zip", client=mock_client)
        assert len(results) == 1

    async def test_skips_short_lines(self) -> None:
        line = _build_trade_line()
        short = "01short"
        content = f"{short}\n{line}"
        zip_bytes = _make_zip(content)
        mock_client = AsyncMock()
        mock_client.get_bytes = AsyncMock(return_value=zip_bytes)

        results = await _fetch("http://example.com/test.zip", client=mock_client)
        assert len(results) == 1

    async def test_empty_zip_returns_empty(self) -> None:
        zip_bytes = io.BytesIO()
        with zipfile.ZipFile(zip_bytes, "w") as zf:
            zf.writestr("empty.txt", "")
        mock_client = AsyncMock()
        mock_client.get_bytes = AsyncMock(return_value=zip_bytes.getvalue())

        results = await _fetch("http://example.com/test.zip", client=mock_client)
        assert results == []

    async def test_sorts_results_by_date_and_ticker(self) -> None:
        line_a = _build_trade_line(ticker="VALE3      ", date_str="20240326")
        line_b = _build_trade_line(ticker="PETR4      ", date_str="20240325")
        zip_bytes = _make_zip(line_a + "\n" + line_b)
        mock_client = AsyncMock()
        mock_client.get_bytes = AsyncMock(return_value=zip_bytes)

        results = await _fetch("http://example.com/test.zip", client=mock_client)
        assert results[0].ticker == "PETR4"
        assert results[1].ticker == "VALE3"

    async def test_ticker_filter_is_case_insensitive(self) -> None:
        line = _build_trade_line(ticker="petr4      ")
        zip_bytes = _make_zip(line)
        mock_client = AsyncMock()
        mock_client.get_bytes = AsyncMock(return_value=zip_bytes)

        results = await _fetch("http://example.com/test.zip", ticker="PETR4", client=mock_client)
        assert len(results) == 1

    async def test_creates_default_client_when_none(self) -> None:
        """When no client is passed, _fetch creates a default HttpClient."""
        line = _build_trade_line()
        zip_bytes = _make_zip(line)
        with patch("connectors.b3._downloader.HttpClient") as MockClient:
            instance = AsyncMock()
            instance.get_bytes = AsyncMock(return_value=zip_bytes)
            MockClient.return_value = instance
            results = await _fetch("http://example.com/test.zip")
            assert len(results) == 1
