from __future__ import annotations

from collections.abc import Callable

from ._helpers import _get, _safe_div
from ._types import LineItems, MarketData


def _net_debt_ebitda(li: LineItems, _md: MarketData) -> float | None:
    """Dívida líquida sobre EBITDA."""
    return _safe_div(_get(li, "divida_liquida"), _get(li, "ebitda"))


def _net_debt_equity(li: LineItems, _md: MarketData) -> float | None:
    """Dívida líquida sobre patrimônio líquido."""
    return _safe_div(_get(li, "divida_liquida"), _get(li, "patrimonio_liquido"))


def _current_ratio(li: LineItems, _md: MarketData) -> float | None:
    """Liquidez corrente — ativo circulante sobre passivo circulante."""
    return _safe_div(_get(li, "ativo_circulante"), _get(li, "passivo_circulante"))


def _quick_ratio(li: LineItems, _md: MarketData) -> float | None:
    """Liquidez geral — ativo circulante sobre passivo circulante + passivo não circulante."""
    denominator = (_get(li, "passivo_circulante") or 0) + (_get(li, "passivo_nao_circulante") or 0)
    return _safe_div(_get(li, "ativo_circulante"), denominator if denominator else None)


def _interest_coverage(li: LineItems, _md: MarketData) -> float | None:
    """Cobertura de juros — EBIT sobre despesas financeiras."""
    return _safe_div(_get(li, "ebit"), _get(li, "despesas_financeiras"))


def _debt_to_equity(li: LineItems, _md: MarketData) -> float | None:
    """Dívida total sobre patrimônio líquido."""
    return _safe_div(_get(li, "divida_total"), _get(li, "patrimonio_liquido"))


def _equity_multiplier(li: LineItems, _md: MarketData) -> float | None:
    """Multiplicador de patrimônio — total de ativos sobre patrimônio líquido."""
    return _safe_div(_get(li, "total_ativos"), _get(li, "patrimonio_liquido"))


LEVERAGE_DEBT_METRICS: dict[str, Callable[[LineItems, MarketData], float | None]] = {
    "net_debt_ebitda": _net_debt_ebitda,
    "net_debt_equity": _net_debt_equity,
    "current_ratio": _current_ratio,
    "quick_ratio": _quick_ratio,
    "interest_coverage": _interest_coverage,
    "debt_to_equity": _debt_to_equity,
    "equity_multiplier": _equity_multiplier,
}
