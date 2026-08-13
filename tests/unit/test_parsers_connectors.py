"""Tests for parsers (HTML, PDF) and connectors (B3 parser, base HTTP client)."""

from __future__ import annotations

import asyncio
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from parsers._html import extract_text_from_tag, parse_html
from parsers._types import ParsedDocument
from connectors.b3._parser import (
    _format_date,
    _LINE_WIDTH,
    _parse_csv_int,
    _parse_csv_price,
    _parse_date_str,
    _parse_int,
    _parse_line,
    _parse_price,
)
from connectors.base import HttpClient


# ---------------------------------------------------------------------------
# parsers/_html.py
# ---------------------------------------------------------------------------
class TestParseHtml:
    def test_simple_text(self):
        result = parse_html("<p>Hello World</p>")
        assert isinstance(result, ParsedDocument)
        assert "Hello World" in result.text

    def test_strips_script(self):
        result = parse_html("<p>Visible</p><script>alert('hi')</script><p>Also visible</p>")
        assert "Visible" in result.text
        assert "alert" not in result.text

    def test_strips_style(self):
        result = parse_html("<p>Text</p><style>.red{color:red}</style>")
        assert "color:red" not in result.text

    def test_strips_noscript(self):
        result = parse_html("<p>Text</p><noscript>JS content</noscript>")
        assert "JS content" not in result.text

    def test_block_tags_add_newlines(self):
        result = parse_html("<div>Line1</div><div>Line2</div>")
        assert "Line1" in result.text
        assert "Line2" in result.text

    def test_multiple_spaces_collapsed(self):
        result = parse_html("<p>hello   world</p>")
        assert "hello world" in result.text

    def test_metadata_source(self):
        result = parse_html("<p>Hi</p>")
        assert result.metadata["source"] == "html"

    def test_empty_html(self):
        result = parse_html("")
        assert result.text == ""

    def test_heading_tags(self):
        result = parse_html("<h1>Title</h1><h2>Sub</h2>")
        assert "Title" in result.text

    def test_list_items(self):
        result = parse_html("<ul><li>A</li><li>B</li></ul>")
        assert "A" in result.text


class TestExtractTextFromTag:
    def test_basic(self):
        text = extract_text_from_tag("<div><p>inner</p></div>", "p")
        assert "inner" in text

    def test_no_match(self):
        text = extract_text_from_tag("<div>hello</div>", "span")
        assert text == ""

    def test_with_attrs(self):
        html = '<div class="target">Matched</div><div>Not matched</div>'
        text = extract_text_from_tag(html, "div", attrs={"class": "target"})
        assert "Matched" in text

    def test_nested_same_tag(self):
        html = "<div><div>nested</div></div>"
        text = extract_text_from_tag(html, "div")
        assert "nested" in text

    def test_multiple_instances(self):
        html = "<p>A</p><p>B</p>"
        text = extract_text_from_tag(html, "p")
        assert "A" in text
        assert "B" in text


# ---------------------------------------------------------------------------
# connectors/b3/_parser.py
# ---------------------------------------------------------------------------
class TestParsePrice:
    def test_normal(self):
        assert _parse_price("0000000012345") == 123.45

    def test_empty(self):
        assert _parse_price("") == 0.0

    def test_whitespace(self):
        assert _parse_price("   ") == 0.0

    def test_invalid(self):
        assert _parse_price("invalid") == 0.0


class TestParseInt:
    def test_normal(self):
        assert _parse_int("12345") == 12345

    def test_empty(self):
        assert _parse_int("") == 0

    def test_invalid(self):
        assert _parse_int("abc") == 0


class TestFormatDate:
    def test_valid(self):
        assert _format_date("20240326") == date(2024, 3, 26)

    def test_invalid_length(self):
        assert _format_date("202403") is None

    def test_invalid_date(self):
        assert _format_date("20241301") is None

    def test_whitespace(self):
        assert _format_date("  20240326  ") == date(2024, 3, 26)


class TestParseDateStr:
    def test_dd_mm_yyyy(self):
        assert _parse_date_str("26/03/2024") == date(2024, 3, 26)

    def test_yyyy_mm_dd(self):
        assert _parse_date_str("2024-03-26") == date(2024, 3, 26)

    def test_yyyymmdd(self):
        assert _parse_date_str("20240326") == date(2024, 3, 26)

    def test_empty(self):
        assert _parse_date_str("") is None

    def test_invalid(self):
        assert _parse_date_str("not-a-date") is None


class TestParseLine:
    def test_header_line(self):
        line = "0" + " " * 244
        assert _parse_line(line) is None

    def test_short_line(self):
        assert _parse_line("short") is None

    def test_valid_trade_line(self):
        # Fixed-width format: 2 chars TIPREG, 8 chars date, 2 chars BDI, 12 chars ticker, rest padding
        prefix = "01" + "20240326" + "01" + "PETR4       "  # 2+8+2+12=24 chars
        line = prefix + " " * (_LINE_WIDTH - len(prefix))
        assert len(line) == _LINE_WIDTH
        result = _parse_line(line)
        assert result is not None
        assert result.ticker == "PETR4"

    def test_non_trade_type(self):
        line = "99" + " " * 243
        assert _parse_line(line) is None


class TestParseCsvPrice:
    def test_comma_decimal(self):
        assert _parse_csv_price("1.234,56") == 1234.56

    def test_dot_decimal(self):
        assert _parse_csv_price("1234.56") == 1234.56

    def test_dot_thousands(self):
        assert _parse_csv_price("1.234.567") == 1234567.0

    def test_empty(self):
        assert _parse_csv_price(None) == 0.0
        assert _parse_csv_price("") == 0.0

    def test_invalid(self):
        assert _parse_csv_price("abc") == 0.0


class TestParseCsvInt:
    def test_normal(self):
        assert _parse_csv_int("1234") == 1234

    def test_thousands_separator(self):
        assert _parse_csv_int("1.234") == 1234

    def test_empty(self):
        assert _parse_csv_int(None) == 0
        assert _parse_csv_int("") == 0

    def test_invalid(self):
        assert _parse_csv_int("abc") == 0


# ---------------------------------------------------------------------------
# connectors/base.py
# ---------------------------------------------------------------------------
class TestHttpClient:
    def test_init_default(self):
        client = HttpClient()
        assert client.base_url == ""

    def test_init_with_base_url(self):
        client = HttpClient(base_url="https://example.com")
        assert client.base_url == "https://example.com"

    def test_strips_trailing_slash(self):
        client = HttpClient(base_url="https://example.com/")
        assert client.base_url == "https://example.com"

    def test_max_retries_must_be_positive(self):
        with pytest.raises(ValueError):
            HttpClient(max_retries=0)

    def test_build_url_with_base(self):
        client = HttpClient(base_url="https://example.com")
        assert client._build_url("/api/data") == "https://example.com/api/data"

    def test_build_url_absolute(self):
        client = HttpClient(base_url="https://example.com")
        assert client._build_url("https://other.com/data") == "https://other.com/data"

    def test_build_url_no_base(self):
        client = HttpClient()
        assert client._build_url("https://example.com/data") == "https://example.com/data"

    @pytest.mark.asyncio
    async def test_close_without_client(self):
        client = HttpClient()
        await client.close()  # Should not raise

    @pytest.mark.asyncio
    async def test_get_bytes_success(self):
        client = HttpClient()
        mock_response = MagicMock()
        mock_response.content = b"hello"
        mock_response.raise_for_status = MagicMock()

        mock_http_client = AsyncMock()
        mock_http_client.get = AsyncMock(return_value=mock_response)
        mock_http_client.is_closed = False
        client._client = mock_http_client

        result = await client.get_bytes("https://example.com/data")
        assert result == b"hello"

    @pytest.mark.asyncio
    async def test_get_text_success(self):
        client = HttpClient()
        mock_response = MagicMock()
        mock_response.content = "hello".encode("utf-8")
        mock_response.raise_for_status = MagicMock()

        mock_http_client = AsyncMock()
        mock_http_client.get = AsyncMock(return_value=mock_response)
        mock_http_client.is_closed = False
        client._client = mock_http_client

        result = await client.get_text("https://example.com/data")
        assert result == "hello"
