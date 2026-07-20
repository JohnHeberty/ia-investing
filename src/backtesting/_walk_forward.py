from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

import polars as pl

from ._engine import BacktestEngine, BacktestResult

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class WalkForwardWindow:
    training_start: date
    training_end: date
    oos_start: date
    oos_end: date


@dataclass(frozen=True, slots=True)
class WalkForwardFold:
    window: WalkForwardWindow
    training_result: BacktestResult
    oos_result: BacktestResult


@dataclass(frozen=True, slots=True)
class WalkForwardResult:
    folds: tuple[WalkForwardFold, ...]
    aggregated_oos: BacktestResult
    baseline_results: dict[str, BacktestResult]
    total_oos_bars: int
    total_oos_trades: int


@dataclass(frozen=True, slots=True)
class WalkForwardConfig:
    start_date: date
    end_date: date
    training_bars: int
    oos_bars: int
    step_bars: int | None = None
    rebalance_freq: str = "monthly"
    benchmark: str = "IBOVESPA"
    initial_capital: float = 1_000_000.0
    transaction_cost_bps: float = 10.0
    slippage_bps: float = 5.0


def _generate_windows(
    config: WalkForwardConfig,
    all_dates: list[date],
) -> list[WalkForwardWindow]:
    step = config.step_bars if config.step_bars is not None else config.oos_bars

    valid_dates = [d for d in all_dates if config.start_date <= d <= config.end_date]
    if len(valid_dates) < config.training_bars + config.oos_bars:
        return []

    windows: list[WalkForwardWindow] = []
    i = 0
    while i + config.training_bars + config.oos_bars <= len(valid_dates):
        train_start = valid_dates[i]
        train_end = valid_dates[i + config.training_bars - 1]
        oos_start = valid_dates[i + config.training_bars]
        oos_end_idx = min(i + config.training_bars + config.oos_bars - 1, len(valid_dates) - 1)
        oos_end = valid_dates[oos_end_idx]
        windows.append(
            WalkForwardWindow(
                training_start=train_start,
                training_end=train_end,
                oos_start=oos_start,
                oos_end=oos_end,
            )
        )
        i += step
    return windows


def _aggregate_oos_results(folds: tuple[WalkForwardFold, ...]) -> BacktestResult:
    if not folds:
        return BacktestResult(
            cagr=0.0, sharpe=0.0, sortino=0.0, calmar=0.0,
            max_drawdown=0.0, win_rate=0.0, total_return=0.0,
            annual_volatility=0.0, benchmark_return=0.0, alpha=0.0,
            information_ratio=0.0, trades=[],
        )

    all_trades: list[dict] = []
    for fold in folds:
        all_trades.extend(fold.oos_result.trades)

    oos_results = [fold.oos_result for fold in folds]
    if not oos_results:
        return _empty_result()

    avg_cagr = sum(r.cagr for r in oos_results) / len(oos_results)
    avg_sharpe = sum(r.sharpe for r in oos_results) / len(oos_results)
    avg_sortino = sum(r.sortino for r in oos_results) / len(oos_results)
    avg_calmar = sum(r.calmar for r in oos_results) / len(oos_results)
    avg_max_dd = sum(r.max_drawdown for r in oos_results) / len(oos_results)
    avg_win_rate = sum(r.win_rate for r in oos_results) / len(oos_results)
    avg_total_return = sum(r.total_return for r in oos_results) / len(oos_results)
    avg_vol = sum(r.annual_volatility for r in oos_results) / len(oos_results)
    avg_bench = sum(r.benchmark_return for r in oos_results) / len(oos_results)
    avg_alpha = sum(r.alpha for r in oos_results) / len(oos_results)
    avg_ir = sum(r.information_ratio for r in oos_results) / len(oos_results)

    return BacktestResult(
        cagr=avg_cagr,
        sharpe=avg_sharpe,
        sortino=avg_sortino,
        calmar=avg_calmar,
        max_drawdown=avg_max_dd,
        win_rate=avg_win_rate,
        total_return=avg_total_return,
        annual_volatility=avg_vol,
        benchmark_return=avg_bench,
        alpha=avg_alpha,
        information_ratio=avg_ir,
        trades=all_trades,
    )


def _empty_result() -> BacktestResult:
    return BacktestResult(
        cagr=0.0, sharpe=0.0, sortino=0.0, calmar=0.0,
        max_drawdown=0.0, win_rate=0.0, total_return=0.0,
        annual_volatility=0.0, benchmark_return=0.0, alpha=0.0,
        information_ratio=0.0, trades=[],
    )


StrategyFactory = Callable[
    [pl.DataFrame, list[str]],
    Callable[[pl.DataFrame, list[str], dict[str, float]], Awaitable[dict[str, float]]],
]


async def run_walk_forward(
    config: WalkForwardConfig,
    universe_data: pl.DataFrame,
    strategy_factory: StrategyFactory,
    baselines: dict[str, Callable[[pl.DataFrame, list[str], dict[str, float]], Awaitable[dict[str, float]]]] | None = None,
) -> WalkForwardResult:
    engine = BacktestEngine(
        initial_capital=config.initial_capital,
        transaction_cost_bps=config.transaction_cost_bps,
        slippage_bps=config.slippage_bps,
    )

    price_cols = [c for c in universe_data.columns if c != "date"]
    all_dates = sorted(universe_data.select("date").to_series().to_list())

    windows = _generate_windows(config, all_dates)
    if not windows:
        empty = _empty_result()
        return WalkForwardResult(
            folds=(),
            aggregated_oos=empty,
            baseline_results={},
            total_oos_bars=0,
            total_oos_trades=0,
        )

    folds: list[WalkForwardFold] = []
    for window in windows:
        training_data = universe_data.filter(
            (pl.col("date") >= pl.lit(window.training_start))
            & (pl.col("date") <= pl.lit(window.training_end))
        )
        oos_data = universe_data.filter(
            (pl.col("date") >= pl.lit(window.oos_start))
            & (pl.col("date") <= pl.lit(window.oos_end))
        )

        strategy_fn = strategy_factory(training_data, price_cols)

        training_result = await engine.run(
            strategy_fn=strategy_fn,
            universe_data=universe_data,
            start_date=window.training_start,
            end_date=window.training_end,
            rebalance_freq=config.rebalance_freq,
            benchmark=config.benchmark,
        )

        oos_result = await engine.run(
            strategy_fn=strategy_fn,
            universe_data=universe_data,
            start_date=window.oos_start,
            end_date=window.oos_end,
            rebalance_freq=config.rebalance_freq,
            benchmark=config.benchmark,
        )

        folds.append(
            WalkForwardFold(
                window=window,
                training_result=training_result,
                oos_result=oos_result,
            )
        )

    aggregated = _aggregate_oos_results(tuple(folds))

    baseline_results: dict[str, BacktestResult] = {}
    if baselines:
        for name, baseline_fn in baselines.items():
            baseline_result = await engine.run(
                strategy_fn=baseline_fn,
                universe_data=universe_data,
                start_date=config.start_date,
                end_date=config.end_date,
                rebalance_freq=config.rebalance_freq,
                benchmark=config.benchmark,
            )
            baseline_results[name] = baseline_result

    total_oos_bars = sum(
        len(
            universe_data.filter(
                (pl.col("date") >= pl.lit(fold.window.oos_start))
                & (pl.col("date") <= pl.lit(fold.window.oos_end))
            )
        )
        for fold in folds
    )
    total_oos_trades = sum(len(fold.oos_result.trades) for fold in folds)

    return WalkForwardResult(
        folds=tuple(folds),
        aggregated_oos=aggregated,
        baseline_results=baseline_results,
        total_oos_bars=total_oos_bars,
        total_oos_trades=total_oos_trades,
    )
