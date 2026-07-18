from __future__ import annotations

import numpy as np
import polars as pl
import pytest

from portfolio._optimizer import OptimizationResult, PortfolioOptimizer


def _make_returns(seed: int = 42, n_days: int = 100, n_assets: int = 3) -> pl.DataFrame:
    rng = np.random.default_rng(seed)
    tickers = [f"ASSET{i}" for i in range(n_assets)]
    data = rng.normal(loc=0.001, scale=0.02, size=(n_days, n_assets))
    return pl.DataFrame(data, schema=tickers)


class TestPortfolioOptimizer:
    @pytest.mark.asyncio
    async def test_weights_sum_to_one(self):
        returns = _make_returns(n_assets=3)
        optimizer = PortfolioOptimizer(risk_aversion=1.0, max_weight=0.50)
        result = await optimizer.optimize(returns)

        assert isinstance(result, OptimizationResult)
        total = sum(result.weights.values())
        assert total == pytest.approx(1.0, abs=1e-4)

    @pytest.mark.asyncio
    async def test_weights_non_negative(self):
        returns = _make_returns(n_assets=4)
        optimizer = PortfolioOptimizer(risk_aversion=1.0, max_weight=0.40)
        result = await optimizer.optimize(returns)

        for ticker, w in result.weights.items():
            assert w >= -1e-6, f"Negative weight for {ticker}: {w}"

    @pytest.mark.asyncio
    async def test_max_weight_constraint(self):
        returns = _make_returns(n_assets=5)
        max_w = 0.25
        optimizer = PortfolioOptimizer(risk_aversion=1.0, max_weight=max_w)
        result = await optimizer.optimize(returns)

        for ticker, w in result.weights.items():
            assert w <= max_w + 1e-4, f"Weight {w} for {ticker} exceeds max {max_w}"

    @pytest.mark.asyncio
    async def test_single_asset_goes_to_one(self):
        returns = _make_returns(n_assets=1)
        optimizer = PortfolioOptimizer(risk_aversion=0.1, max_weight=1.0)
        result = await optimizer.optimize(returns)

        assert len(result.weights) == 1
        w = next(iter(result.weights.values()))
        assert w == pytest.approx(1.0, abs=1e-3)

    @pytest.mark.asyncio
    async def test_expected_risk_non_negative(self):
        returns = _make_returns(n_assets=3)
        optimizer = PortfolioOptimizer()
        result = await optimizer.optimize(returns)

        assert result.expected_risk >= 0.0
