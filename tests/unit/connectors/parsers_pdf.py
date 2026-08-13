"""Unit tests for parsers._pdf — PDF parsing helpers and functions."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from parsers._pdf import _sanitize_cell, _sanitize_tables, extract_tables, parse_pdf


class TestSanitizeCell:
    def test_none_returns_empty(self):
        assert _sanitize_cell(None) == ""

    def test_empty_string_returns_empty(self):
        assert _sanitize_cell("") == ""

    def test_normal_string_preserved(self):
        assert _sanitize_cell("hello") == "hello"

    def test_whitespace_preserved(self):
        assert _sanitize_cell("  ") == "  "

    def test_numeric_string(self):
        assert _sanitize_cell("123") == "123"


class TestSanitizeTables:
    def test_empty_list(self):
        assert _sanitize_tables([]) == []

    def test_none_cells_replaced(self):
        raw: list[list[list[str | None]]] = [[["a", None], [None, "b"]]]
        result = _sanitize_tables(raw)
        assert result == [[["a", ""], ["", "b"]]]

    def test_multiple_tables(self):
        raw: list[list[list[str | None]]] = [
            [[None, "h2"], ["v1", None]],
            [["x"]],
        ]
        result = _sanitize_tables(raw)
        assert result == [
            [["", "h2"], ["v1", ""]],
            [["x"]],
        ]

    def test_all_none_table(self):
        raw: list[list[list[str | None]]] = [[[None, None, None]]]
        result = _sanitize_tables(raw)
        assert result == [[["", "", ""]]]


def _make_mock_page(text: str | None, tables: list | None) -> MagicMock:
    page = MagicMock()
    page.extract_text.return_value = text
    page.extract_tables.return_value = tables or []
    return page


def _make_mock_pdf_context(pages: list[MagicMock], metadata: dict[str, Any] | None = None) -> MagicMock:
    """Create a mock that works as `pdfplumber.open(path)` context manager."""
    pdf = MagicMock()
    pdf.pages = pages
    pdf.metadata = metadata if metadata is not None else {"Title": "Test PDF"}
    return pdf


@pytest.fixture(autouse=True)
def _mock_pdfplumber(monkeypatch):
    """Provide a mock pdfplumber module in sys.modules for all tests in this file."""
    mock_plumber = MagicMock()
    monkeypatch.setitem(sys.modules, "pdfplumber", mock_plumber)
    return mock_plumber


class TestParsePdf:
    def test_basic_parse(self, _mock_pdfplumber):
        page = _make_mock_page("Page 1 text", [[["a", "b"]]])
        mock_pdf = _make_mock_pdf_context([page])
        _mock_pdfplumber.open.return_value.__enter__ = MagicMock(return_value=mock_pdf)
        _mock_pdfplumber.open.return_value.__exit__ = MagicMock(return_value=False)

        result = parse_pdf(Path("/tmp/test.pdf"))

        assert result.text == "Page 1 text"
        assert len(result.tables) == 1
        assert result.tables[0][0] == ["a", "b"]
        assert result.metadata["page_count"] == 1
        assert result.metadata["page_limit_enforced"] is False
        assert result.source_path == "/tmp/test.pdf"

    def test_multiple_pages_concatenated(self, _mock_pdfplumber):
        p1 = _make_mock_page("Page 1", None)
        p2 = _make_mock_page("Page 2", None)
        mock_pdf = _make_mock_pdf_context([p1, p2])
        _mock_pdfplumber.open.return_value.__enter__ = MagicMock(return_value=mock_pdf)
        _mock_pdfplumber.open.return_value.__exit__ = MagicMock(return_value=False)

        result = parse_pdf(Path("/tmp/test.pdf"))
        assert result.text == "Page 1\nPage 2"

    def test_none_text_page_skipped(self, _mock_pdfplumber):
        p1 = _make_mock_page(None, None)
        p2 = _make_mock_page("Real text", None)
        mock_pdf = _make_mock_pdf_context([p1, p2])
        _mock_pdfplumber.open.return_value.__enter__ = MagicMock(return_value=mock_pdf)
        _mock_pdfplumber.open.return_value.__exit__ = MagicMock(return_value=False)

        result = parse_pdf(Path("/tmp/test.pdf"))
        assert result.text == "Real text"

    def test_tables_collected_across_pages(self, _mock_pdfplumber):
        p1 = _make_mock_page(None, [[["a", "b"]]])
        p2 = _make_mock_page(None, [[["c", "d"]]])
        mock_pdf = _make_mock_pdf_context([p1, p2])
        _mock_pdfplumber.open.return_value.__enter__ = MagicMock(return_value=mock_pdf)
        _mock_pdfplumber.open.return_value.__exit__ = MagicMock(return_value=False)

        result = parse_pdf(Path("/tmp/test.pdf"))
        assert len(result.tables) == 2

    def test_no_metadata_uses_empty_dict(self, _mock_pdfplumber):
        page = _make_mock_page("text", None)
        mock_pdf = _make_mock_pdf_context([page], metadata=None)
        _mock_pdfplumber.open.return_value.__enter__ = MagicMock(return_value=mock_pdf)
        _mock_pdfplumber.open.return_value.__exit__ = MagicMock(return_value=False)

        result = parse_pdf(Path("/tmp/test.pdf"))
        assert result.metadata["page_count"] == 1

    def test_page_limit_enforced(self, _mock_pdfplumber):
        pages = [_make_mock_page(f"p{i}", None) for i in range(501)]
        mock_pdf = _make_mock_pdf_context(pages)
        _mock_pdfplumber.open.return_value.__enter__ = MagicMock(return_value=mock_pdf)
        _mock_pdfplumber.open.return_value.__exit__ = MagicMock(return_value=False)

        result = parse_pdf(Path("/tmp/test.pdf"))
        assert result.metadata["page_count"] == 501
        assert result.metadata["page_limit_enforced"] is True

    def test_page_limit_not_enforced_under_500(self, _mock_pdfplumber):
        pages = [_make_mock_page(f"p{i}", None) for i in range(500)]
        mock_pdf = _make_mock_pdf_context(pages)
        _mock_pdfplumber.open.return_value.__enter__ = MagicMock(return_value=mock_pdf)
        _mock_pdfplumber.open.return_value.__exit__ = MagicMock(return_value=False)

        result = parse_pdf(Path("/tmp/test.pdf"))
        assert result.metadata["page_limit_enforced"] is False

    def test_none_tables_not_extended(self, _mock_pdfplumber):
        page = _make_mock_page("text", None)
        mock_pdf = _make_mock_pdf_context([page])
        _mock_pdfplumber.open.return_value.__enter__ = MagicMock(return_value=mock_pdf)
        _mock_pdfplumber.open.return_value.__exit__ = MagicMock(return_value=False)

        result = parse_pdf(Path("/tmp/test.pdf"))
        assert result.tables == []

    def test_string_path_converted(self, _mock_pdfplumber):
        page = _make_mock_page("ok", None)
        mock_pdf = _make_mock_pdf_context([page])
        _mock_pdfplumber.open.return_value.__enter__ = MagicMock(return_value=mock_pdf)
        _mock_pdfplumber.open.return_value.__exit__ = MagicMock(return_value=False)

        result = parse_pdf("/tmp/test.pdf")
        assert result.source_path == "/tmp/test.pdf"

    def test_metadata_dict_not_none(self, _mock_pdfplumber):
        page = _make_mock_page("text", None)
        mock_pdf = _make_mock_pdf_context([page], metadata={"Author": "test"})
        _mock_pdfplumber.open.return_value.__enter__ = MagicMock(return_value=mock_pdf)
        _mock_pdfplumber.open.return_value.__exit__ = MagicMock(return_value=False)

        result = parse_pdf(Path("/tmp/test.pdf"))
        assert result.metadata["Author"] == "test"
        assert result.metadata["page_count"] == 1

    def test_no_text_no_tables(self, _mock_pdfplumber):
        page = _make_mock_page(None, None)
        mock_pdf = _make_mock_pdf_context([page])
        _mock_pdfplumber.open.return_value.__enter__ = MagicMock(return_value=mock_pdf)
        _mock_pdfplumber.open.return_value.__exit__ = MagicMock(return_value=False)

        result = parse_pdf(Path("/tmp/test.pdf"))
        assert result.text == ""
        assert result.tables == []

    def test_empty_tables_list_not_extended(self, _mock_pdfplumber):
        page = _make_mock_page("text", [])
        mock_pdf = _make_mock_pdf_context([page])
        _mock_pdfplumber.open.return_value.__enter__ = MagicMock(return_value=mock_pdf)
        _mock_pdfplumber.open.return_value.__exit__ = MagicMock(return_value=False)

        result = parse_pdf(Path("/tmp/test.pdf"))
        assert result.tables == []


class TestExtractTables:
    def test_basic_extract(self, _mock_pdfplumber):
        page = _make_mock_page(None, [[["x", "y"]]])
        mock_pdf = _make_mock_pdf_context([page])
        _mock_pdfplumber.open.return_value.__enter__ = MagicMock(return_value=mock_pdf)
        _mock_pdfplumber.open.return_value.__exit__ = MagicMock(return_value=False)

        result = extract_tables(Path("/tmp/test.pdf"))
        assert len(result) == 1
        assert result[0][0] == ["x", "y"]

    def test_no_tables_returns_empty(self, _mock_pdfplumber):
        page = _make_mock_page(None, [])
        mock_pdf = _make_mock_pdf_context([page])
        _mock_pdfplumber.open.return_value.__enter__ = MagicMock(return_value=mock_pdf)
        _mock_pdfplumber.open.return_value.__exit__ = MagicMock(return_value=False)

        result = extract_tables(Path("/tmp/test.pdf"))
        assert result == []

    def test_none_tables_returns_empty(self, _mock_pdfplumber):
        page = _make_mock_page(None, None)
        mock_pdf = _make_mock_pdf_context([page])
        _mock_pdfplumber.open.return_value.__enter__ = MagicMock(return_value=mock_pdf)
        _mock_pdfplumber.open.return_value.__exit__ = MagicMock(return_value=False)

        result = extract_tables(Path("/tmp/test.pdf"))
        assert result == []

    def test_multiple_pages_tables_combined(self, _mock_pdfplumber):
        p1 = _make_mock_page(None, [[["a"]]])
        p2 = _make_mock_page(None, [[["b"]]])
        mock_pdf = _make_mock_pdf_context([p1, p2])
        _mock_pdfplumber.open.return_value.__enter__ = MagicMock(return_value=mock_pdf)
        _mock_pdfplumber.open.return_value.__exit__ = MagicMock(return_value=False)

        result = extract_tables(Path("/tmp/test.pdf"))
        assert len(result) == 2

    def test_string_path(self, _mock_pdfplumber):
        page = _make_mock_page(None, [[["z"]]])
        mock_pdf = _make_mock_pdf_context([page])
        _mock_pdfplumber.open.return_value.__enter__ = MagicMock(return_value=mock_pdf)
        _mock_pdfplumber.open.return_value.__exit__ = MagicMock(return_value=False)

        result = extract_tables("/tmp/test.pdf")
        assert len(result) == 1

    def test_page_limit_respected(self, _mock_pdfplumber):
        pages = [_make_mock_page(None, [[["t"]]]) for _ in range(501)]
        mock_pdf = _make_mock_pdf_context(pages)
        _mock_pdfplumber.open.return_value.__enter__ = MagicMock(return_value=mock_pdf)
        _mock_pdfplumber.open.return_value.__exit__ = MagicMock(return_value=False)

        result = extract_tables(Path("/tmp/test.pdf"))
        assert len(result) == 500

    def test_none_cells_sanitized(self, _mock_pdfplumber):
        page = _make_mock_page(None, [[["a", None]]])
        mock_pdf = _make_mock_pdf_context([page])
        _mock_pdfplumber.open.return_value.__enter__ = MagicMock(return_value=mock_pdf)
        _mock_pdfplumber.open.return_value.__exit__ = MagicMock(return_value=False)

        result = extract_tables(Path("/tmp/test.pdf"))
        assert result[0][0] == ["a", ""]
