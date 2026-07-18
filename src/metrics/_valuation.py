from __future__ import annotations

from collections.abc import Callable

from ._helpers import _get, _md, _safe_div
from ._types import LineItems, MarketData


def _pe_ttm(li: LineItems, market_data: MarketData) -> float | None:
    """P/L TTM — preço por ação sobre lucro por ação trailing twelve months."""
    price = _md(market_data, "price")
    eps = _get(li, "lucro_por_acao_ttm")
    return _safe_div(price, eps)


def _pb(li: LineItems, market_data: MarketData) -> float | None:
    """P/VP — preço por ação sobre valor patrimonial por ação."""
    price = _md(market_data, "price")
    bvps = _get(li, "valor_patrimonial_por_acao")
    return _safe_div(price, bvps)


def _ev_ebitda(li: LineItems, market_data: MarketData) -> float | None:
    """EV/EBITDA — valor da empresa sobre EBITDA."""
    ev = _md(market_data, "enterprise_value")
    return _safe_div(ev, _get(li, "ebitda"))


def _ev_ebit(li: LineItems, market_data: MarketData) -> float | None:
    """EV/EBIT — valor da empresa sobre EBIT."""
    ev = _md(market_data, "enterprise_value")
    return _safe_div(ev, _get(li, "ebit"))


def _price_to_sales(li: LineItems, market_data: MarketData) -> float | None:
    """P/S — market cap sobre receita líquida."""
    market_cap = _md(market_data, "market_cap")
    return _safe_div(market_cap, _get(li, "receita_liquida"))


def _price_to_book(li: LineItems, market_data: MarketData) -> float | None:
    """P/VP — market cap sobre patrimônio líquido."""
    market_cap = _md(market_data, "market_cap")
    return _safe_div(market_cap, _get(li, "patrimonio_liquido"))


def _dividend_yield(li: LineItems, market_data: MarketData) -> float | None:
    """Dividend yield — dividendos por ação sobre preço (%)."""
    dps = _get(li, "dividendo_por_acao")
    price = _md(market_data, "price")
    return _safe_div(dps, price)


def _payout_ratio(li: LineItems, _md: MarketData) -> float | None:
    """Payout ratio — dividendos por ação sobre lucro por ação."""
    dps = _get(li, "dividendo_por_acao")
    eps = _get(li, "lucro_por_acao")
    return _safe_div(dps, eps)


def _ev_to_fcf(li: LineItems, market_data: MarketData) -> float | None:
    """EV/FCF — valor da empresa sobre fluxo de caixa livre."""
    ev = _md(market_data, "enterprise_value")
    fcf = _get(li, "fluxo_caixa_livre")
    return _safe_div(ev, fcf)


VALUATION_METRICS: dict[str, Callable[[LineItems, MarketData], float | None]] = {
    "pe_ttm": _pe_ttm,
    "pb": _pb,
    "ev_ebitda": _ev_ebitda,
    "ev_ebit": _ev_ebit,
    "price_to_sales": _price_to_sales,
    "price_to_book": _price_to_book,
    "dividend_yield": _dividend_yield,
    "payout_ratio": _payout_ratio,
    "ev_to_fcf": _ev_to_fcf,
}
