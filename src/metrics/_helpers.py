from __future__ import annotations

import math

from ._types import LineItems, MarketData


def _safe_div(numerator: float | None, denominator: float | None) -> float | None:
    """Divisão segura que retorna None quando o denominador é zero ou nulo."""
    if numerator is None or denominator is None or denominator == 0:
        return None
    result = numerator / denominator
    return result if math.isfinite(result) else None


def _pct_change(current: float | None, previous: float | None) -> float | None:
    """Calcula variação percentual entre dois valores."""
    if current is None or previous is None or previous == 0:
        return None
    return ((current - previous) / abs(previous)) * 100


def _get(li: LineItems, key: str) -> float | None:
    """Extrai valor dos line_items, convertendo para float ou retornando None."""
    val = li.get(key)
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _md(data: MarketData, key: str) -> float | None:
    """Extrai valor dos market_data, convertendo para float ou retornando None."""
    val = data.get(key)
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None
