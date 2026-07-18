from __future__ import annotations

from collections.abc import Callable

from ._helpers import _get, _md, _pct_change, _safe_div
from ._types import LineItems, MarketData


def _revenue_yoy(li: LineItems, _md: MarketData) -> float | None:
    """Crescimento da receita líquida em relação ao período anterior (YoY %)."""
    return _pct_change(_get(li, "receita_liquida"), _get(li, "receita_liquida_anterior"))


def _ebitda_yoy(li: LineItems, _md: MarketData) -> float | None:
    """Crescimento do EBITDA em relação ao período anterior (YoY %)."""
    return _pct_change(_get(li, "ebitda"), _get(li, "ebitda_anterior"))


def _net_income_yoy(li: LineItems, _md: MarketData) -> float | None:
    """Crescimento do lucro líquido em relação ao período anterior (YoY %)."""
    return _pct_change(_get(li, "lucro_liquido"), _get(li, "lucro_liquido_anterior"))


def _gross_margin(li: LineItems, _md: MarketData) -> float | None:
    """Margem bruta sobre receita líquida (%)."""
    return _safe_div(_get(li, "lucro_bruto"), _get(li, "receita_liquida"))


def _ebitda_margin(li: LineItems, _md: MarketData) -> float | None:
    """Margem EBITDA sobre receita líquida (%)."""
    return _safe_div(_get(li, "ebitda"), _get(li, "receita_liquida"))


def _net_margin(li: LineItems, _md: MarketData) -> float | None:
    """Margem líquida sobre receita líquida (%)."""
    return _safe_div(_get(li, "lucro_liquido"), _get(li, "receita_liquida"))


def _roe(li: LineItems, _md: MarketData) -> float | None:
    """Return on equity — lucro líquido sobre patrimônio líquido (%)."""
    return _safe_div(_get(li, "lucro_liquido"), _get(li, "patrimonio_liquido"))


def _roa(li: LineItems, _md: MarketData) -> float | None:
    """Return on assets — lucro líquido sobre total de ativos (%)."""
    return _safe_div(_get(li, "lucro_liquido"), _get(li, "total_ativos"))


def _roic(li: LineItems, _md: MarketData) -> float | None:
    """Return on invested capital — EBIT*(1-ir) sobre capital investido (%)."""
    ebit = _get(li, "ebit")
    tax_rate = _get(li, "aliquota_imposto")
    invested_capital = _get(li, "capital_investido")
    if ebit is None or tax_rate is None or invested_capital is None:
        return None
    nopat = ebit * (1 - tax_rate)
    return _safe_div(nopat, invested_capital)


def _asset_turnover(li: LineItems, _md: MarketData) -> float | None:
    """Giro do ativo — receita líquida sobre total de ativos."""
    return _safe_div(_get(li, "receita_liquida"), _get(li, "total_ativos"))


def _fcf_yield(li: LineItems, market_data: MarketData) -> float | None:
    """Free cash flow yield — fluxo de caixa livre sobre market cap (%)."""
    fcf = _get(li, "fluxo_caixa_livre")
    market_cap = _md(market_data, "market_cap")
    return _safe_div(fcf, market_cap)


QUALITY_GROWTH_METRICS: dict[str, Callable[[LineItems, MarketData], float | None]] = {
    "revenue_yoy": _revenue_yoy,
    "ebitda_yoy": _ebitda_yoy,
    "net_income_yoy": _net_income_yoy,
    "gross_margin": _gross_margin,
    "ebitda_margin": _ebitda_margin,
    "net_margin": _net_margin,
    "roe": _roe,
    "roa": _roa,
    "roic": _roic,
    "asset_turnover": _asset_turnover,
    "fcf_yield": _fcf_yield,
}
