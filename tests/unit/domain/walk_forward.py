from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import date

import polars as pl
import pytest

from backtesting._baselines import (
    equal_weight_strategy,
    make_baseline_strategies,
    market_cap_proxy_strategy,
    sector_neutral_strategy,
)
from backtesting._engine import BacktestResult
from backtesting._walk_forward import (
    WalkForwardConfig,
    WalkForwardWindow,
    _aggregate_oos_results,
    _generate_windows,
    run_walk_forward,
)


def _make_price_data(start: date, days: int, tickers: list[str]) -> pl.DataFrame:
    import random

    random.seed(42)
    dates = [start + __import__("datetime").timedelta(days=i) for i in range(days)]
    data: dict[str, list] = {"date": dates}
    for ticker in tickers:
        prices = [100.0]
        for _ in range(days - 1):
            change = random.uniform(-0.02, 0.02)
            prices.append(prices[-1] * (1 + change))
        data[ticker] = prices
    return pl.DataFrame(data)


def _constant_strategy(value: float) -> Callable[..., Awaitable[dict[str, float]]]:
    async def strategy(
        prices_df: pl.DataFrame,
        price_cols: list[str],
        current_weights: dict[str, float],
    ) -> dict[str, float]:
        if not price_cols:
            return {}
        weight = value / len(price_cols)
        return dict.fromkeys(price_cols, weight)

    return strategy


class TestWalkForwardWindows:
    def test_generates_correct_windows(self) -> None:
        all_dates = [date(2025, 1, 1) + __import__("datetime").timedelta(days=i) for i in range(365)]
        config = WalkForwardConfig(
            start_date=date(2025, 1, 1),
            end_date=date(2025, 12, 31),
            training_bars=60,
            oos_bars=30,
        )
        windows = _generate_windows(config, all_dates)
        assert len(windows) > 0
        for w in windows:
            assert w.training_start < w.training_end
            assert w.training_end < w.oos_start
            assert w.oos_start <= w.oos_end

    def test_no_windows_if_insufficient_data(self) -> None:
        all_dates = [date(2025, 1, 1) + __import__("datetime").timedelta(days=i) for i in range(10)]
        config = WalkForwardConfig(
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 10),
            training_bars=60,
            oos_bars=30,
        )
        windows = _generate_windows(config, all_dates)
        assert windows == []

    def test_step_bars_controls_stride(self) -> None:
        all_dates = [date(2025, 1, 1) + __import__("datetime").timedelta(days=i) for i in range(200)]
        config = WalkForwardConfig(
            start_date=date(2025, 1, 1),
            end_date=date(2025, 7, 19),
            training_bars=30,
            oos_bars=15,
            step_bars=15,
        )
        windows = _generate_windows(config, all_dates)
        assert len(windows) > 1
        prev_train_start = windows[0].training_start
        for w in windows[1:]:
            assert w.training_start > prev_train_start
            prev_train_start = w.training_start

    def test_windows_dont_exceed_date_range(self) -> None:
        all_dates = [date(2025, 1, 1) + __import__("datetime").timedelta(days=i) for i in range(100)]
        config = WalkForwardConfig(
            start_date=date(2025, 1, 1),
            end_date=date(2025, 4, 11),
            training_bars=30,
            oos_bars=20,
        )
        windows = _generate_windows(config, all_dates)
        for w in windows:
            assert w.training_start >= config.start_date
            assert w.oos_end <= config.end_date


class TestAggregateOOS:
    def test_aggregate_averages_metrics(self) -> None:
        fold1 = type(
            "Fold",
            (),
            {
                "oos_result": BacktestResult(
                    cagr=0.10,
                    sharpe=1.0,
                    sortino=1.5,
                    calmar=2.0,
                    max_drawdown=0.05,
                    win_rate=0.55,
                    total_return=0.10,
                    annual_volatility=0.12,
                    benchmark_return=0.08,
                    alpha=0.02,
                    information_ratio=0.5,
                    trades=[],
                ),
                "window": WalkForwardWindow(date(2025, 1, 1), date(2025, 3, 31), date(2025, 4, 1), date(2025, 6, 30)),
            },
        )()
        fold2 = type(
            "Fold",
            (),
            {
                "oos_result": BacktestResult(
                    cagr=0.20,
                    sharpe=2.0,
                    sortino=3.0,
                    calmar=4.0,
                    max_drawdown=0.10,
                    win_rate=0.60,
                    total_return=0.20,
                    annual_volatility=0.15,
                    benchmark_return=0.06,
                    alpha=0.14,
                    information_ratio=1.0,
                    trades=[],
                ),
                "window": WalkForwardWindow(date(2025, 4, 1), date(2025, 6, 30), date(2025, 7, 1), date(2025, 9, 30)),
            },
        )()
        result = _aggregate_oos_results((fold1, fold2))
        assert result.cagr == pytest.approx(0.15)
        assert result.sharpe == pytest.approx(1.5)
        assert result.alpha == pytest.approx(0.08)

    def test_empty_folds_returns_zeros(self) -> None:
        result = _aggregate_oos_results(())
        assert result.cagr == 0.0
        assert result.sharpe == 0.0


class TestRunWalkForward:
    @pytest.mark.asyncio
    async def test_walk_forward_produces_folds(self) -> None:
        data = _make_price_data(date(2025, 1, 1), 180, ["PETR4", "VALE3"])
        config = WalkForwardConfig(
            start_date=date(2025, 1, 1),
            end_date=date(2025, 6, 30),
            training_bars=30,
            oos_bars=15,
        )

        async def factory(
            train_data: pl.DataFrame,
            price_cols: list[str],
        ) -> Callable[..., Awaitable[dict[str, float]]]:
            return _constant_strategy(1.0)

        result = await run_walk_forward(config, data, factory)
        assert len(result.folds) > 0
        for fold in result.folds:
            assert fold.window.training_start < fold.window.training_end
            assert fold.window.training_end < fold.window.oos_start

    @pytest.mark.asyncio
    async def test_walk_forward_with_baselines(self) -> None:
        data = _make_price_data(date(2025, 1, 1), 180, ["PETR4", "VALE3"])
        config = WalkForwardConfig(
            start_date=date(2025, 1, 1),
            end_date=date(2025, 6, 30),
            training_bars=30,
            oos_bars=15,
        )

        async def factory(
            train_data: pl.DataFrame,
            price_cols: list[str],
        ) -> Callable[..., Awaitable[dict[str, float]]]:
            return _constant_strategy(1.0)

        baselines = make_baseline_strategies()
        result = await run_walk_forward(config, data, factory, baselines=baselines)
        assert "equal_weight" in result.baseline_results
        assert "market_cap_proxy" in result.baseline_results
        assert "momentum_60d" in result.baseline_results
        assert "sector_neutral" in result.baseline_results

    @pytest.mark.asyncio
    async def test_walk_forward_counts_bars_and_trades(self) -> None:
        data = _make_price_data(date(2025, 1, 1), 180, ["PETR4"])
        config = WalkForwardConfig(
            start_date=date(2025, 1, 1),
            end_date=date(2025, 6, 30),
            training_bars=30,
            oos_bars=15,
        )

        async def factory(
            train_data: pl.DataFrame,
            price_cols: list[str],
        ) -> Callable[..., Awaitable[dict[str, float]]]:
            return _constant_strategy(1.0)

        result = await run_walk_forward(config, data, factory)
        assert result.total_oos_bars > 0
        assert result.total_oos_trades >= 0


class TestBaselineStrategies:
    @pytest.mark.asyncio
    async def test_equal_weight_distributes_evenly(self) -> None:
        data = _make_price_data(date(2025, 1, 1), 10, ["A", "B", "C"])
        cols = ["A", "B", "C"]
        weights = await equal_weight_strategy(data, cols, {})
        assert weights == {"A": 1 / 3, "B": 1 / 3, "C": 1 / 3}

    @pytest.mark.asyncio
    async def test_market_cap_proxy_weights_by_price(self) -> None:
        df = pl.DataFrame(
            {
                "date": [date(2025, 1, 1)],
                "A": [200.0],
                "B": [100.0],
            }
        )
        weights = await market_cap_proxy_strategy(df, ["A", "B"], {})
        assert weights["A"] == pytest.approx(2 / 3)
        assert weights["B"] == pytest.approx(1 / 3)

    @pytest.mark.asyncio
    async def test_sector_neutral_distributes_across_sectors(self) -> None:
        data = _make_price_data(date(2025, 1, 1), 10, ["A", "B", "C", "D"])
        sector_map = {"A": "tech", "B": "tech", "C": "finance", "D": "finance"}
        weights = await sector_neutral_strategy(data, ["A", "B", "C", "D"], {}, sector_map)
        assert weights["A"] == pytest.approx(0.25)
        assert weights["B"] == pytest.approx(0.25)
        assert weights["C"] == pytest.approx(0.25)
        assert weights["D"] == pytest.approx(0.25)

    @pytest.mark.asyncio
    async def test_sector_neutral_without_map_falls_back_to_equal(self) -> None:
        data = _make_price_data(date(2025, 1, 1), 10, ["A", "B"])
        weights = await sector_neutral_strategy(data, ["A", "B"], {})
        assert weights == {"A": 0.5, "B": 0.5}

    def test_make_baseline_strategies_returns_all(self) -> None:
        baselines = make_baseline_strategies()
        assert set(baselines.keys()) == {
            "equal_weight",
            "market_cap_proxy",
            "momentum_60d",
            "sector_neutral",
        }
