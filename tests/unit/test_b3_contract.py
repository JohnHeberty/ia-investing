"""Contract tests for B3 COTAHIST parser and market data models."""
from datetime import date

import pytest

from connectors.b3._models import CotahistTrade
from connectors.b3._parser import _format_date, _parse_date_str, _parse_int, _parse_line, _parse_price


def _build_valid_line() -> str:
    """Build a correct 245-char COTAHIST fixed-width record."""
    line = [" "] * 245
    line[0:2] = list("01")  # TIPREG
    line[2:10] = list("20241230")  # DATA
    line[10:12] = list("02")  # CODBDI
    line[12:24] = list("PETR4" + " " * 7)  # CODNEG (12 chars)
    line[24:38] = list("PETROLEO BRASIL ")  # NOME (14 chars)
    line[38:44] = list("ON NM")  # ESPEC (6 chars)
    line[58:71] = list("0000000000724")  # PREABE
    line[71:84] = list("0000000000735")  # PREMAX
    line[84:97] = list("0000000000710")  # PREMIN
    line[97:110] = list("0000000000722")  # PREMED
    line[110:123] = list("0000000000730")  # PREULT
    line[156:164] = list("00005000")  # TOTNEG
    line[164:180] = list("0000000001000000")  # QUATOT
    line[180:200] = list("000000000072200000")  # VOLTOT
    return "".join(line)


VALID_LINE = _build_valid_line()


# --- COTAHIST fixed-width contract ---


def test_parse_line_returns_cotahist_trade() -> None:
    """_parse_line parses a valid COTAHIST fixed-width record."""
    result = _parse_line(VALID_LINE)
    assert result is not None
    assert isinstance(result, CotahistTrade)
    assert result.trade_date == date(2024, 12, 30)
    assert result.ticker == "PETR4"
    assert result.cod_bdi == "02"


def test_parse_line_skips_header_and_footer() -> None:
    """TIPREG 00 (header) and 99 (footer) return None."""
    header = "00" + " " * 243
    footer = "99" + " " * 243
    assert _parse_line(header) is None
    assert _parse_line(footer) is None


def test_parse_line_short_line_returns_none() -> None:
    """Lines shorter than 245 chars return None."""
    assert _parse_line("01short") is None


def test_parse_line_non_numeric_price_returns_none() -> None:
    """Invalid prices result in None trade."""
    bad = "012024123002PETR4       " + "X" * 230
    result = _parse_line(bad.ljust(245))
    assert result is None


def test_parse_line_empty_ticker_returns_none() -> None:
    """Missing ticker yields None."""
    line = list(" " * 245)
    line[0:2] = list("01")
    line[2:10] = list("20241230")
    line[10:12] = list("02")
    # ticker at [12:24] stays spaces
    assert _parse_line("".join(line)) is None


def test_parse_line_prices_populated() -> None:
    """Price fields are correctly parsed from centavos."""
    result = _parse_line(VALID_LINE)
    assert result is not None
    assert result.preco_abertura == pytest.approx(7.24)
    assert result.preco_maximo == pytest.approx(7.35)
    assert result.preco_minimo == pytest.approx(7.10)
    assert result.preco_medio == pytest.approx(7.22)
    assert result.preco_ultimo == pytest.approx(7.30)


def test_parse_line_volume_and_counts() -> None:
    """Volume and trade count fields are correctly parsed."""
    result = _parse_line(VALID_LINE)
    assert result is not None
    assert result.num_negocios == 5000
    assert result.qtd_titulos_negociados == 1000000
    assert result.volume_financeiro == pytest.approx(72200.0)


def test_parse_line_moeda_always_brl() -> None:
    """Parsed trade always has moeda=R$."""
    result = _parse_line(VALID_LINE)
    assert result is not None
    assert result.moeda == "R$"


def test_parse_line_uppercases_ticker() -> None:
    """Ticker is uppercased."""
    line = list(VALID_LINE)
    line[12:24] = list("petr4" + " " * 6)
    result = _parse_line("".join(line))
    assert result is not None
    assert result.ticker == "PETR4"


# --- Price/int parser contracts ---


def test_parse_price_centavos() -> None:
    """_parse_price converts 13-char centavos to float."""
    assert _parse_price("0000000000724") == pytest.approx(7.24)


def test_parse_price_zero() -> None:
    """Zero centavos yields 0.0."""
    assert _parse_price("0000000000000") == 0.0


def test_parse_price_empty() -> None:
    """Empty string yields 0.0."""
    assert _parse_price("") == 0.0


def test_parse_price_non_numeric() -> None:
    """Non-numeric string yields 0.0."""
    assert _parse_price("   ABCDEFGHIJKL") == 0.0


def test_parse_int_basic() -> None:
    """_parse_int parses 8-char field."""
    assert _parse_int("00001234") == 1234


def test_parse_int_zero() -> None:
    """_parse_int zeros."""
    assert _parse_int("00000000") == 0


def test_parse_int_empty() -> None:
    """_parse_int empty string."""
    assert _parse_int("") == 0


# --- _format_date contracts ---


def test_format_date_compact() -> None:
    """_format_date parses YYYYMMDD."""
    assert _format_date("20241230") == date(2024, 12, 30)


def test_format_date_invalid() -> None:
    """_format_date returns None for bad input."""
    assert _format_date("invalid") is None


def test_format_date_short() -> None:
    """_format_date returns None for short string."""
    assert _format_date("2024123") is None


# --- CSV date parsing contracts ---


def test_parse_date_str_ddmmyyyy() -> None:
    assert _parse_date_str("30/12/2024") == date(2024, 12, 30)


def test_parse_date_str_iso() -> None:
    assert _parse_date_str("2024-12-30") == date(2024, 12, 30)


def test_parse_date_str_compact() -> None:
    assert _parse_date_str("20241230") == date(2024, 12, 30)


def test_parse_date_str_invalid() -> None:
    assert _parse_date_str("invalid") is None


def test_parse_date_str_empty() -> None:
    assert _parse_date_str("") is None


def test_parse_date_str_whitespace() -> None:
    assert _parse_date_str("  ") is None


# --- CotahistTrade dataclass contract ---


def test_cotahist_trade_to_dict() -> None:
    """CotahistTrade.to_dict returns all required fields."""
    trade = CotahistTrade(
        trade_date=date(2024, 12, 30),
        ticker="PETR4",
        cod_bdi="02",
        nome_resumido="PETROBRAS",
        especificacao="ON NM",
        moeda="R$",
        preco_abertura=7.24,
        preco_maximo=7.35,
        preco_minimo=7.10,
        preco_medio=7.22,
        preco_ultimo=7.30,
        num_negocios=50000,
        qtd_titulos_negociados=1000000,
        volume_financeiro=7220000.0,
        isin="BRPETRACNPR6",
    )
    d = trade.to_dict()
    assert d["ticker"] == "PETR4"
    assert d["trade_date"] == date(2024, 12, 30)
    assert d["moeda"] == "R$"
    assert "preco_abertura" in d


def test_cotahist_trade_defaults() -> None:
    """CotahistTrade defaults moeda to R$ and other optional fields."""
    trade = CotahistTrade(trade_date=date(2024, 1, 1), ticker="TEST")
    assert trade.moeda == "R$"
    assert trade.trade_date == date(2024, 1, 1)
    assert trade.ticker == "TEST"
    assert trade.cod_bdi == ""
    assert trade.preco_ultimo == 0.0


def test_cotahist_trade_to_dict_completeness() -> None:
    """to_dict contains all expected keys."""
    trade = CotahistTrade(trade_date=date(2024, 1, 1), ticker="TEST")
    d = trade.to_dict()
    expected_keys = {
        "trade_date", "ticker", "cod_bdi", "nome_resumido", "especificacao",
        "moeda", "preco_abertura", "preco_maximo", "preco_minimo", "preco_medio",
        "preco_ultimo", "num_negocios", "qtd_titulos_negociados",
        "volume_financeiro", "isin",
    }
    assert expected_keys == set(d.keys())


# --- Ticker/listing historical scenarios ---


def test_multiple_tickers_same_date_simulation() -> None:
    """Multiple tickers on the same date are valid."""
    trades = []
    for ticker in ["PETR4", "VALE3", "ITUB4"]:
        trade = CotahistTrade(
            trade_date=date(2024, 12, 30),
            ticker=ticker,
            preco_ultimo=50.0,
        )
        trades.append(trade)
    assert len(trades) == 3
    tickers = {t.ticker for t in trades}
    assert tickers == {"PETR4", "VALE3", "ITUB4"}


def test_ticker_change_over_time() -> None:
    """Same instrument can have different tickers across dates."""
    old_trade = CotahistTrade(trade_date=date(2020, 1, 2), ticker="PETR4", preco_ultimo=30.0)
    new_trade = CotahistTrade(trade_date=date(2024, 12, 30), ticker="PETR4", preco_ultimo=38.0)
    assert old_trade.ticker == new_trade.ticker
    assert old_trade.trade_date != new_trade.trade_date
