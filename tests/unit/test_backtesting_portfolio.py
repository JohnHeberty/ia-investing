"""Tests for backtesting metrics, baselines, and portfolio transforms."""

from __future__ import annotations

import asyncio

import numpy as np
import polars as pl
import pytest

from backtesting._baselines import (
    equal_weight_strategy,
    make_baseline_strategies,
    market_cap_proxy_strategy,
    momentum_strategy,
    sector_neutral_strategy,
)
from backtesting._metrics import (
    BacktestMetrics,
    _compute_cagr,
    _compute_calmar,
    _compute_information_ratio,
    _compute_max_drawdown,
    _compute_sharpe,
    _compute_sortino,
    compute_metrics,
)
from portfolio._transforms import (
    TransformDefinition,
    percentile,
    percentile_ranks,
    winsorize,
    z_scores,
)


# ---------------------------------------------------------------------------
# backtesting/_metrics.py
# ---------------------------------------------------------------------------
class TestComputeCAGR:
    def test_normal(self):
        # With 252 periods, CAGR = (121/100)^(252/251) - 1
        curve = [100.0] + [100.0 + i * 0.08333 for i in range(252)]
        cagr = _compute_cagr(curve, 252)
        assert cagr > 0.0

    def test_empty(self):
        assert _compute_cagr([], 252) == 0.0

    def test_single_value(self):
        assert _compute_cagr([100.0], 252) == 0.0

    def test_zero_initial(self):
        assert _compute_cagr([0.0, 100.0], 252) == 0.0

    def test_negative_final(self):
        assert _compute_cagr([100.0, -50.0], 252) == 0.0


class TestComputeMaxDrawdown:
    def test_no_drawdown(self):
        assert _compute_max_drawdown([100.0, 110.0, 120.0]) == 0.0

    def test_with_drawdown(self):
        assert _compute_max_drawdown([100.0, 120.0, 90.0]) == pytest.approx(0.25)

    def test_peak_at_end(self):
        assert _compute_max_drawdown([100.0, 80.0, 100.0]) == pytest.approx(0.2)

    def test_zero_peak(self):
        assert _compute_max_drawdown([0.0, 0.0]) == 0.0


class TestComputeSharpe:
    def test_short_returns(self):
        assert _compute_sharpe(np.array([0.01])) == 0.0

    def test_zero_volatility(self):
        returns = np.array([0.01, 0.01, 0.01])
        assert _compute_sharpe(returns) == 0.0

    def test_positive_sharpe(self):
        returns = np.array([0.01, -0.005, 0.02, -0.01, 0.015])
        assert _compute_sharpe(returns) > 0


class TestComputeSortino:
    def test_short_returns(self):
        assert _compute_sortino(np.array([0.01])) == 0.0

    def test_no_negative_returns(self):
        assert _compute_sortino(np.array([0.01, 0.02, 0.03])) == 0.0

    def test_with_negative_returns(self):
        returns = np.array([0.01, -0.02, 0.03, -0.01])
        assert _compute_sortino(returns) != 0.0


class TestComputeCalmar:
    def test_zero_drawdown(self):
        assert _compute_calmar(0.1, 0.0) == 0.0

    def test_normal(self):
        assert _compute_calmar(0.15, 0.1) == pytest.approx(1.5)


class TestComputeInformationRatio:
    def test_short(self):
        assert _compute_information_ratio(np.array([0.01]), np.array([0.01])) == 0.0

    def test_zero_tracking_error(self):
        p = np.array([0.01, 0.02, 0.03])
        assert _compute_information_ratio(p, p) == 0.0

    def test_positive(self):
        p = np.array([0.02, 0.03, 0.04])
        b = np.array([0.01, 0.01, 0.01])
        assert _compute_information_ratio(p, b) > 0


class TestComputeMetrics:
    def test_basic(self):
        curve = [100.0 + i * 10 for i in range(20)]
        m = compute_metrics(curve)
        assert isinstance(m, BacktestMetrics)
        assert m.total_return > 0

    def test_with_benchmark(self):
        curve = [100.0, 110.0, 120.0, 130.0]
        bench = [100.0, 105.0, 110.0, 115.0]
        m = compute_metrics(curve, benchmark_prices=bench)
        assert m.benchmark_return != 0.0

    def test_flat_curve(self):
        curve = [100.0, 100.0, 100.0]
        m = compute_metrics(curve)
        assert m.total_return == 0.0


# ---------------------------------------------------------------------------
# backtesting/_baselines.py
# ---------------------------------------------------------------------------
class TestEqualWeightStrategy:
    def test_basic(self):
        result = asyncio.get_event_loop().run_until_complete(
            equal_weight_strategy(pl.DataFrame(), ["A", "B", "C"], {})
        )
        assert result == {"A": pytest.approx(1 / 3), "B": pytest.approx(1 / 3), "C": pytest.approx(1 / 3)}

    def test_empty_cols(self):
        result = asyncio.get_event_loop().run_until_complete(
            equal_weight_strategy(pl.DataFrame(), [], {})
        )
        assert result == {}


class TestMarketCapProxyStrategy:
    def test_basic(self):
        df = pl.DataFrame({"A": [100.0], "B": [200.0]})
        result = asyncio.get_event_loop().run_until_complete(
            market_cap_proxy_strategy(df, ["A", "B"], {})
        )
        assert result["A"] == pytest.approx(1 / 3)
        assert result["B"] == pytest.approx(2 / 3)

    def test_empty_df(self):
        result = asyncio.get_event_loop().run_until_complete(
            market_cap_proxy_strategy(pl.DataFrame(), ["A"], {})
        )
        assert result == {}

    def test_all_zero_prices(self):
        df = pl.DataFrame({"A": [0.0], "B": [0.0]})
        result = asyncio.get_event_loop().run_until_complete(
            market_cap_proxy_strategy(df, ["A", "B"], {})
        )
        assert result == {}

    def test_current_weights_fallback(self):
        result = asyncio.get_event_loop().run_until_complete(
            market_cap_proxy_strategy(pl.DataFrame(), [], {"A": 1.0})
        )
        assert result == {"A": 1.0}


class TestMomentumStrategy:
    def test_short_data(self):
        df = pl.DataFrame({"A": [100.0]})
        result = asyncio.get_event_loop().run_until_complete(
            momentum_strategy(df, ["A"], {}, lookback=60)
        )
        assert result == {}

    def test_sufficient_data(self):
        prices = list(range(100, 160))
        df = pl.DataFrame({"A": [float(p) for p in prices]})
        result = asyncio.get_event_loop().run_until_complete(
            momentum_strategy(df, ["A"], {}, lookback=60)
        )
        assert "A" in result


class TestSectorNeutralStrategy:
    def test_no_sector_map(self):
        result = asyncio.get_event_loop().run_until_complete(
            sector_neutral_strategy(pl.DataFrame(), ["A", "B"], {})
        )
        assert result["A"] == pytest.approx(0.5)

    def test_with_sector_map(self):
        sector_map = {"A": "tech", "B": "tech", "C": "finance"}
        result = asyncio.get_event_loop().run_until_complete(
            sector_neutral_strategy(pl.DataFrame(), ["A", "B", "C"], {}, sector_map)
        )
        assert result["A"] == pytest.approx(0.25)
        assert result["B"] == pytest.approx(0.25)
        assert result["C"] == pytest.approx(0.5)

    def test_empty_cols(self):
        result = asyncio.get_event_loop().run_until_complete(
            sector_neutral_strategy(pl.DataFrame(), [], {})
        )
        assert result == {}


class TestMakeBaselineStrategies:
    def test_returns_all_strategies(self):
        strats = make_baseline_strategies()
        assert "equal_weight" in strats
        assert "market_cap_proxy" in strats
        assert "momentum_60d" in strats
        assert "sector_neutral" in strats

    def test_with_sector_map(self):
        strats = make_baseline_strategies(sector_map={"A": "tech"})
        assert "sector_neutral" in strats


# ---------------------------------------------------------------------------
# portfolio/_transforms.py
# ---------------------------------------------------------------------------
class TestPercentile:
    def test_basic(self):
        assert percentile([1, 2, 3, 4, 5], 0.5) == 3.0

    def test_edge_quantiles(self):
        assert percentile([10, 20, 30], 0.0) == 10
        assert percentile([10, 20, 30], 1.0) == 30

    def test_empty_raises(self):
        with pytest.raises(ValueError):
            percentile([], 0.5)

    def test_invalid_quantile(self):
        with pytest.raises(ValueError):
            percentile([1, 2], 1.5)


class TestWinsorize:
    def test_basic(self):
        defn = TransformDefinition(version="1.0")
        result = winsorize([1, 2, 3, 4, 5, 100], defn)
        assert max(result) <= 100
        assert min(result) >= 1


class TestZScores:
    def test_basic(self):
        result = z_scores([10, 20, 30])
        assert len(result) == 3
        assert sum(result) == pytest.approx(0.0, abs=1e-10)

    def test_constant_values(self):
        result = z_scores([5, 5, 5])
        assert all(v == 0.0 for v in result)

    def test_empty_raises(self):
        with pytest.raises(ValueError):
            z_scores([])


class TestPercentileRanks:
    def test_basic(self):
        result = percentile_ranks([10, 20, 30])
        assert len(result) == 3
        assert result[0] == 0.0
        assert result[2] == 1.0

    def test_empty_raises(self):
        with pytest.raises(ValueError):
            percentile_ranks([])
