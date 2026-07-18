from __future__ import annotations

from collections.abc import Callable

from ._helpers import _get, _md, _pct_change, _safe_div
from ._types import LineItems, MarketData


def _div_yield_12m(li: LineItems, market_data: MarketData) -> float | None:
    """Dividend yield dos últimos 12 meses (%)."""
    total_dps = _get(li, "dividendos_por_acao_12m")
    price = _md(market_data, "price")
    return _safe_div(total_dps, price)


def _div_growth_3y(li: LineItems, _md: MarketData) -> float | None:
    """Crescimento dos dividendos nos últimos 3 anos (%)."""
    return _pct_change(
        _get(li, "dividendos_por_acao_atual"),
        _get(li, "dividendos_por_acao_3y_atras"),
    )


def _payout_avg_3y(li: LineItems, _md: MarketData) -> float | None:
    """Payout médio nos últimos 3 anos."""
    return _get(li, "payout_medio_3y")


def _div_consistency(li: LineItems, _md: MarketData) -> float | None:
    """Consistência de pagamento de dividendos (0-1)."""
    return _get(li, "consistencia_dividendos")


def _jcp_ratio(li: LineItems, _md: MarketData) -> float | None:
    """JCP sobre dividendos totais (%)."""
    jcp = _get(li, "jcp_por_acao")
    total_div = _get(li, "dividendos_por_acao_12m")
    return _safe_div(jcp, total_div)


DIVIDEND_METRICS: dict[str, Callable[[LineItems, MarketData], float | None]] = {
    "div_yield_12m": _div_yield_12m,
    "div_growth_3y": _div_growth_3y,
    "payout_avg_3y": _payout_avg_3y,
    "div_consistency": _div_consistency,
    "jcp_ratio": _jcp_ratio,
}
