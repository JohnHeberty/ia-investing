from __future__ import annotations

from collections.abc import Callable

from ._helpers import _md
from ._types import LineItems, MarketData


def _real_interest(_li: LineItems, market_data: MarketData) -> float | None:
    """Taxa real — SELIC menos IPCA."""
    selic = _md(market_data, "selic")
    ipca = _md(market_data, "ipca")
    if selic is None or ipca is None:
        return None
    return selic - ipca


def _usd_brl(_li: LineItems, market_data: MarketData) -> float | None:
    """Câmbio USD/BRL."""
    return _md(market_data, "usd_brl")


def _industrial_production_index(_li: LineItems, market_data: MarketData) -> float | None:
    """Índice de produção industrial."""
    return _md(market_data, "industrial_production_index")


def _consumer_confidence(_li: LineItems, market_data: MarketData) -> float | None:
    """Índice de confiança do consumidor."""
    return _md(market_data, "consumer_confidence")


MACRO_METRICS: dict[str, Callable[[LineItems, MarketData], float | None]] = {
    "real_interest": _real_interest,
    "usd_brl": _usd_brl,
    "industrial_production_index": _industrial_production_index,
    "consumer_confidence": _consumer_confidence,
}
