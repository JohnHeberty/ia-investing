from __future__ import annotations

import asyncio

import numpy as np
import polars as pl
import pytest

# Skip this entire module if cvxpy is unavailable or broken (numpy incompatibility).
try:
    import cvxpy as _cvxpy_check

    if getattr(_cvxpy_check, "__version__", "").startswith("0.0.0"):
        pytest.skip("cvxpy unavailable due to numpy incompatibility", allow_module_level=True)
except (ImportError, ModuleNotFoundError):
    pytest.skip("cvxpy unavailable", allow_module_level=True)

from portfolio._optimizer import OptimizationResult, OptimizerConfig, PortfolioOptimizer


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
        optimizer = PortfolioOptimizer(max_weight=0.50)
        result = await optimizer.optimize(returns)

        assert result.expected_risk is not None and result.expected_risk >= 0.0

    @pytest.mark.asyncio
    async def test_infeasible_constraints_fail_closed_without_equal_weight(self):
        returns = _make_returns(n_assets=3)
        optimizer = PortfolioOptimizer(max_weight=0.20)
        result = await optimizer.optimize(returns)

        assert result.status == "infeasible"
        assert result.weights == {}
        assert result.expected_return is None

    @pytest.mark.asyncio
    async def test_cash_bounds_are_solver_constraints_and_reported(self):
        returns = pl.DataFrame({"A": [-0.02, -0.01, -0.03], "B": [-0.01, -0.02, -0.01]})
        optimizer = PortfolioOptimizer(
            OptimizerConfig(max_weight=1.0, min_cash_weight=0.10, max_cash_weight=0.20, risk_aversion=0.0)
        )
        result = await optimizer.optimize(returns)
        assert result.status in {"optimal", "optimal_inaccurate"}
        assert 0.10 - 1e-4 <= result.diagnostics["cash_weight"] <= 0.20 + 1e-4
        assert result.slacks["minimum_invested"] <= 1e-4
        assert result.slacks["maximum_invested"] <= 1e-4

    @pytest.mark.asyncio
    async def test_symmetric_known_solution_is_equal_weight_golden(self):
        returns = pl.DataFrame({"A": [0.01, -0.01, 0.01, -0.01], "B": [0.01, -0.01, 0.01, -0.01]})
        result = await PortfolioOptimizer(max_weight=1.0, risk_aversion=1.0).optimize(returns)
        assert result.status in {"optimal", "optimal_inaccurate"}
        assert result.weights["A"] == pytest.approx(0.5, abs=1e-4)
        assert result.weights["B"] == pytest.approx(0.5, abs=1e-4)

    @pytest.mark.asyncio
    async def test_solver_timeout_fails_closed(self, monkeypatch):
        async def never_finishes(*_args, **_kwargs):
            await asyncio.sleep(60)

        monkeypatch.setattr(asyncio, "to_thread", never_finishes)
        optimizer = PortfolioOptimizer(OptimizerConfig(max_weight=1.0, timeout_seconds=0.001))
        result = await optimizer.optimize(_make_returns())

        assert result.status == "failed"
        assert result.weights == {}
        assert result.diagnostics["reason"] == "solver timeout exceeded"

    @pytest.mark.asyncio
    async def test_cancellation_is_propagated(self, monkeypatch):
        started = asyncio.Event()

        async def never_finishes(*_args, **_kwargs):
            started.set()
            await asyncio.sleep(60)

        monkeypatch.setattr(asyncio, "to_thread", never_finishes)
        task = asyncio.create_task(PortfolioOptimizer(max_weight=1.0).optimize(_make_returns()))
        await started.wait()
        task.cancel()

        with pytest.raises(asyncio.CancelledError):
            await task
