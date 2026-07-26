"""Motor de cálculo de métricas financeiras para o mercado brasileiro.

Organiza 50+ métricas em pilares: Quality & Growth, Leverage & Debt,
Valuation, Market & Technical, Dividend e Macro.
"""

from __future__ import annotations

from collections.abc import Callable

from ._dividend import DIVIDEND_METRICS
from ._helpers import _pct_change, _safe_div  # noqa: F401
from ._leverage_debt import LEVERAGE_DEBT_METRICS
from ._macro import MACRO_METRICS
from ._market_technical import MARKET_TECHNICAL_METRICS
from ._quality_growth import QUALITY_GROWTH_METRICS
from ._types import LineItems, MarketData, MetricResult, PillarResult
from ._valuation import VALUATION_METRICS

# ---------------------------------------------------------------------------
# Registro central de pilares
# ---------------------------------------------------------------------------

PILLARS: dict[str, dict[str, Callable[[LineItems, MarketData], float | None]]] = {
    "quality_growth": QUALITY_GROWTH_METRICS,
    "leverage_debt": LEVERAGE_DEBT_METRICS,
    "valuation": VALUATION_METRICS,
    "market_technical": MARKET_TECHNICAL_METRICS,
    "dividend": DIVIDEND_METRICS,
    "macro": MACRO_METRICS,
}


# ---------------------------------------------------------------------------
# API pública
# ---------------------------------------------------------------------------


def calculate_pillar(
    pillar_name: str,
    line_items: LineItems,
    market_data: MarketData,
) -> MetricResult:
    """Calcula todas as métricas de um pilar específico.

    Args:
        pillar_name: Nome do pilar (quality_growth, leverage_debt, valuation,
            market_technical, dividend, macro).
        line_items: Dicionário com os valores das contas contábeis normalizados.
        market_data: Dicionário com dados de mercado (preço, market cap, etc.).

    Returns:
        Dicionário nome → valor calculado (ou None se dados insuficientes).
    """
    pillar = PILLARS.get(pillar_name)
    if pillar is None:
        return {}

    return {name: fn(line_items, market_data) for name, fn in pillar.items()}


def calculate_all(
    line_items: LineItems,
    market_data: MarketData,
) -> PillarResult:
    """Calcula todas as métricas de todos os pilares.

    Args:
        line_items: Dicionário com os valores das contas contábeis normalizados.
        market_data: Dicionário com dados de mercado (preço, market cap, etc.).

    Returns:
        Dicionário pilar → {métrica → valor calculado}.
    """
    return {pillar_name: calculate_pillar(pillar_name, line_items, market_data) for pillar_name in PILLARS}


def get_pillar_names() -> list[str]:
    """Retorna a lista de nomes de pilares disponíveis."""
    return list(PILLARS.keys())


def get_metric_names(pillar_name: str | None = None) -> list[str]:
    """Retorna os nomes das métricas, opcionalmente filtradas por pilar."""
    if pillar_name is not None:
        pillar = PILLARS.get(pillar_name, {})
        return list(pillar.keys())
    return [name for pillar in PILLARS.values() for name in pillar]
