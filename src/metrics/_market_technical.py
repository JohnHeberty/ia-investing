from __future__ import annotations

from collections.abc import Callable

from ._helpers import _md
from ._types import LineItems, MarketData


def _market_cap(_li: LineItems, market_data: MarketData) -> float | None:
    """Valor de mercado."""
    return _md(market_data, "market_cap")


def _enterprise_value(_li: LineItems, market_data: MarketData) -> float | None:
    """Valor da empresa (enterprise value)."""
    return _md(market_data, "enterprise_value")


def _liquidity_avg_20d(_li: LineItems, market_data: MarketData) -> float | None:
    """Média de negociações nos últimos 20 dias."""
    return _md(market_data, "liquidity_avg_20d")


def _beta_60d(_li: LineItems, market_data: MarketData) -> float | None:
    """Beta nos últimos 60 dias."""
    return _md(market_data, "beta_60d")


def _volatility_20d_annualized(_li: LineItems, market_data: MarketData) -> float | None:
    """Volatilidade anualizada dos últimos 20 dias (%)."""
    return _md(market_data, "volatility_20d_annualized")


def _momentum(_li: LineItems, market_data: MarketData, period: str) -> float | None:
    """Retorno em um período específico."""
    return _md(market_data, f"momentum_{period}")


def _momentum_1m(li: LineItems, md: MarketData) -> float | None:
    """Momento de 1 mês."""
    return _momentum(li, md, "1m")


def _momentum_3m(li: LineItems, md: MarketData) -> float | None:
    """Momento de 3 meses."""
    return _momentum(li, md, "3m")


def _momentum_6m(li: LineItems, md: MarketData) -> float | None:
    """Momento de 6 meses."""
    return _momentum(li, md, "6m")


def _momentum_12m(li: LineItems, md: MarketData) -> float | None:
    """Momento de 12 meses."""
    return _momentum(li, md, "12m")


MARKET_TECHNICAL_METRICS: dict[str, Callable[[LineItems, MarketData], float | None]] = {
    "market_cap": _market_cap,
    "enterprise_value": _enterprise_value,
    "liquidity_avg_20d": _liquidity_avg_20d,
    "beta_60d": _beta_60d,
    "volatility_20d_annualized": _volatility_20d_annualized,
    "momentum_1m": _momentum_1m,
    "momentum_3m": _momentum_3m,
    "momentum_6m": _momentum_6m,
    "momentum_12m": _momentum_12m,
}
