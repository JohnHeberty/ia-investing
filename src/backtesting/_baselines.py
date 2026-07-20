from __future__ import annotations

from collections.abc import Awaitable, Callable

import polars as pl


async def equal_weight_strategy(
    prices_df: pl.DataFrame,
    price_cols: list[str],
    current_weights: dict[str, float],
) -> dict[str, float]:
    if not price_cols:
        return {}
    weight = 1.0 / len(price_cols)
    return {col: weight for col in price_cols}


async def market_cap_proxy_strategy(
    prices_df: pl.DataFrame,
    price_cols: list[str],
    current_weights: dict[str, float],
) -> dict[str, float]:
    if prices_df.height < 1 or not price_cols:
        return current_weights or {}

    latest_row = prices_df.tail(1).to_dicts()[0]
    scores: dict[str, float] = {}
    for col in price_cols:
        val = latest_row.get(col)
        if val is not None and val > 0:
            scores[col] = float(val)

    if not scores:
        return current_weights or {}

    total = sum(scores.values())
    if total <= 0:
        return current_weights or {}

    return {col: score / total for col, score in scores.items()}


async def momentum_strategy(
    prices_df: pl.DataFrame,
    price_cols: list[str],
    current_weights: dict[str, float],
    lookback: int = 60,
) -> dict[str, float]:
    if prices_df.height < lookback or not price_cols:
        return current_weights or {}

    recent = prices_df.tail(lookback)
    first_row = recent.head(1).to_dicts()[0]
    last_row = recent.tail(1).to_dicts()[0]

    scores: dict[str, float] = {}
    for col in price_cols:
        first_val = first_row.get(col)
        last_val = last_row.get(col)
        if first_val is not None and last_val is not None and first_val > 0:
            momentum = (float(last_val) / float(first_val)) - 1.0
            if momentum > 0:
                scores[col] = momentum

    if not scores:
        return await equal_weight_strategy(prices_df, price_cols, current_weights)

    total = sum(scores.values())
    if total <= 0:
        return await equal_weight_strategy(prices_df, price_cols, current_weights)

    return {col: score / total for col, score in scores.items()}


async def sector_neutral_strategy(
    prices_df: pl.DataFrame,
    price_cols: list[str],
    current_weights: dict[str, float],
    sector_map: dict[str, str] | None = None,
) -> dict[str, float]:
    if not price_cols:
        return {}

    if sector_map is None:
        return await equal_weight_strategy(prices_df, price_cols, current_weights)

    sectors: dict[str, list[str]] = {}
    for col in price_cols:
        sector = sector_map.get(col, "unknown")
        sectors.setdefault(sector, []).append(col)

    weights: dict[str, float] = {}
    sector_weight = 1.0 / len(sectors) if sectors else 0.0

    for sector_tickers in sectors.values():
        per_ticker = sector_weight / len(sector_tickers)
        for ticker in sector_tickers:
            weights[ticker] = per_ticker

    return weights


def make_baseline_strategies(
    sector_map: dict[str, str] | None = None,
) -> dict[str, Callable[[pl.DataFrame, list[str], dict[str, float]], Awaitable[dict[str, float]]]]:
    async def _equal_weight(
        prices_df: pl.DataFrame,
        price_cols: list[str],
        current_weights: dict[str, float],
    ) -> dict[str, float]:
        return await equal_weight_strategy(prices_df, price_cols, current_weights)

    async def _market_cap(
        prices_df: pl.DataFrame,
        price_cols: list[str],
        current_weights: dict[str, float],
    ) -> dict[str, float]:
        return await market_cap_proxy_strategy(prices_df, price_cols, current_weights)

    async def _momentum(
        prices_df: pl.DataFrame,
        price_cols: list[str],
        current_weights: dict[str, float],
    ) -> dict[str, float]:
        return await momentum_strategy(prices_df, price_cols, current_weights)

    async def _sector_neutral(
        prices_df: pl.DataFrame,
        price_cols: list[str],
        current_weights: dict[str, float],
    ) -> dict[str, float]:
        return await sector_neutral_strategy(prices_df, price_cols, current_weights, sector_map)

    return {
        "equal_weight": _equal_weight,
        "market_cap_proxy": _market_cap,
        "momentum_60d": _momentum,
        "sector_neutral": _sector_neutral,
    }
