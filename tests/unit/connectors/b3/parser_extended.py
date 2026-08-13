"""Tests for connectors.b3._parser — CSV price/int parsers and extended line parsing."""

from __future__ import annotations

from datetime import date

import pytest

from connectors.b3._parser import (
    _format_date,
    _parse_csv_int,
    _parse_csv_price,
    _parse_date_str,
    _parse_int,
    _parse_line,
    _parse_price,
)


class TestParseCsvPrice:
    @pytest.mark.parametrize(
        "val, expected",
        [
            ("1.234,56", 1234.56),
            ("1234.56", 1234.56),
            ("1.234.567", 1234567.0),
            ("0", 0.0),
            ("", 0.0),
            (None, 0.0),
            ("abc", 0.0),
        ],
    )
    def test_parse_csv_price(self, val: str | None, expected: float) -> None:
        assert _parse_csv_price(val) == pytest.approx(expected)


class TestParseCsvInt:
    @pytest.mark.parametrize(
        "val, expected",
        [
            ("1.234", 1234),
            ("1234", 1234),
            ("0", 0),
            ("", 0),
            (None, 0),
            ("abc", 0),
        ],
    )
    def test_parse_csv_int(self, val: str | None, expected: int) -> None:
        assert _parse_csv_int(val) == expected


class TestFormatDate:
    def test_valid_8char(self) -> None:
        assert _format_date("20241230") == date(2024, 12, 30)

    def test_short_returns_none(self) -> None:
        assert _format_date("202412") is None

    def test_long_returns_none(self) -> None:
        assert _format_date("202412301") is None

    def test_invalid_returns_none(self) -> None:
        assert _format_date("abcdefgh") is None

    def test_whitespace_stripped(self) -> None:
        assert _format_date("  20241230  ") == date(2024, 12, 30)


class TestParseDateStr:
    def test_dd_mm_yyyy(self) -> None:
        assert _parse_date_str("30/12/2024") == date(2024, 12, 30)

    def test_yyyy_mm_dd(self) -> None:
        assert _parse_date_str("2024-12-30") == date(2024, 12, 30)

    def test_yyyyMMdd(self) -> None:
        assert _parse_date_str("20241230") == date(2024, 12, 30)

    def test_invalid_returns_none(self) -> None:
        assert _parse_date_str("not-a-date") is None

    def test_empty_returns_none(self) -> None:
        assert _parse_date_str("") is None

    def test_whitespace_returns_none(self) -> None:
        assert _parse_date_str("   ") is None


class TestParseLineExtended:
    def test_empty_date_returns_none(self) -> None:
        buf = [" "] * 245
        buf[0:2] = list("01")
        buf[10:12] = list("02")
        buf[12:24] = list("TEST       ")
        # Date field [2:10] stays spaces
        assert _parse_line("".join(buf)) is None

    def test_parse_price_with_invalid_non_numeric(self) -> None:
        assert _parse_price("   ABCDEFGHIJKL") == 0.0

    def test_parse_int_with_invalid(self) -> None:
        assert _parse_int("  ABCDEFGH") == 0

    def test_short_line_at_boundary(self) -> None:
        assert _parse_line("01" * 100) is None

    def test_line_exactly_245_chars_valid(self) -> None:
        buf = [" "] * 246
        buf[0:2] = list("01")
        buf[2:10] = list("20241230")
        buf[10:12] = list("02")
        buf[12:24] = list("TEST       ")
        buf[58:71] = list("0000000000100")
        buf[71:84] = list("0000000000100")
        buf[84:97] = list("0000000000100")
        buf[97:110] = list("0000000000100")
        buf[110:123] = list("0000000000100")
        result = _parse_line("".join(buf))
        assert result is not None
        assert result.ticker == "TEST"
