from __future__ import annotations

from datetime import date

import pytest

from connectors.b3._cotahist import (
    _parse_int,
    _parse_line,
    _parse_price,
)


def _make_line(
    tipreg: str = "01",
    date_str: str = "20240326",
    cod_bdi: str = "02",
    ticker: str = "PETR4      ",
    open_price: int = 3850,
    max_price: int = 3900,
    min_price: int = 3800,
    avg_price: int = 3850,
    close_price: int = 3870,
    num_neg: int = 50000,
    qty: int = 1000000,
    volume: int = 3850000000,
    isin: str = "BRPETR4F0004",
) -> str:
    # Fields: TIPREG(2) + DATA(8) + CODBDI(2) + CODNEG(12) + ...
    # PREABE(13) + PREMAX(13) + PREMIN(13) + PREMED(13) + PREULT(13)
    # Using positional construction for 245-char line
    line = [" "] * 245
    # TIPREG 0-2
    line[0:2] = list(tipreg)
    # DATA 2-10
    line[2:10] = list(date_str)
    # CODBDI 10-12
    line[10:12] = list(cod_bdi)
    # CODNEG 12-24
    line[12:24] = list(ticker.ljust(12))
    # PREABE 58-71
    line[58:71] = list(str(open_price).rjust(13))
    # PREMAX 71-84
    line[71:84] = list(str(max_price).rjust(13))
    # PREMIN 84-97
    line[84:97] = list(str(min_price).rjust(13))
    # PREMED 97-110
    line[97:110] = list(str(avg_price).rjust(13))
    # PREULT 110-123
    line[110:123] = list(str(close_price).rjust(13))
    # TOTNEG 156-164
    line[156:164] = list(str(num_neg).rjust(8))
    # QUATOT 164-180
    line[164:180] = list(str(qty).rjust(16))
    # VOLTOT 180-200
    line[180:200] = list(str(volume).rjust(20))
    # ISIN 236-248
    line[236:248] = list(isin.ljust(12))
    return "".join(line)


class TestParsePrice:
    @pytest.mark.parametrize(
        "slc, expected",
        [
            ("         3850", 38.50),
            ("            0", 0.0),
            ("          100", 1.00),
        ],
    )
    def test_parse_price(self, slc, expected):
        assert _parse_price(slc) == pytest.approx(expected)

    def test_empty_string(self):
        assert _parse_price("") == 0.0

    def test_whitespace_only(self):
        assert _parse_price("   ") == 0.0


class TestParseInt:
    @pytest.mark.parametrize(
        "slc, expected",
        [
            ("    50000", 50000),
            ("        0", 0),
            ("  1234567", 1234567),
        ],
    )
    def test_parse_int(self, slc, expected):
        assert _parse_int(slc) == expected

    def test_empty_string(self):
        assert _parse_int("") == 0


class TestParseLine:
    def test_valid_line(self):
        line = _make_line(ticker="PETR4      ", open_price=3850, close_price=3870)
        result = _parse_line(line)
        assert result is not None
        assert result.ticker == "PETR4"
        assert result.trade_date == date(2024, 3, 26)
        assert result.preco_abertura == pytest.approx(38.50)
        assert result.preco_ultimo == pytest.approx(38.70)
        assert result.cod_bdi == "02"

    def test_header_line_returns_none(self):
        line = _make_line(tipreg="00")
        assert _parse_line(line) is None

    def test_footer_line_returns_none(self):
        line = _make_line(tipreg="99")
        assert _parse_line(line) is None

    def test_short_line_returns_none(self):
        assert _parse_line("0120240326") is None

    def test_empty_line_returns_none(self):
        assert _parse_line("") is None

    def test_empty_ticker_returns_none(self):
        line = _make_line(ticker="            ")
        assert _parse_line(line) is None
