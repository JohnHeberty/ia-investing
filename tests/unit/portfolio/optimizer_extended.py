"""Extended unit tests for portfolio._optimizer — covers kwargs constructor, fallback solver, sector constraints, min_holding, transactions, and single-asset covariance."""

from __future__ import annotations

import cvxpy as cp
import numpy as np
import polars as pl
import pytest

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


@pytest.mark.unit
class TestOptimizerConfig:
    def test_defaults(self):
        cfg = OptimizerConfig()
        assert cfg.risk_aversion == 1.0
        assert cfg.max_weight == 0.10
        assert cfg.min_weight == 0.0
        assert cfg.max_sector == 0.30
        assert cfg.max_turnover == 0.20
        assert cfg.transaction_cost_bps == 10.0
        assert cfg.solver == "SCS"
        assert cfg.fallback_solver is None
        assert cfg.timeout_seconds == 30.0

    def test_custom_values(self):
        cfg = OptimizerConfig(risk_aversion=2.0, max_weight=0.25, solver="CLARABEL")
        assert cfg.risk_aversion == 2.0
        assert cfg.max_weight == 0.25
        assert cfg.solver == "CLARABEL"


@pytest.mark.unit
class TestOptimizationResult:
    def test_failure_result_fields(self):
        result = OptimizationResult(
            status="infeasible",
            weights={},
            expected_return=None,
            expected_risk=None,
            sharpe_ratio=None,
            turnover=None,
        )
        assert result.status == "infeasible"
        assert result.weights == {}
        assert result.transactions == []
        assert result.diagnostics == {}
        assert result.slacks == {}


@pytest.mark.unit
class TestPortfolioOptimizerExtended:
    @pytest.mark.asyncio
    async def test_kwargs_constructor(self):
        returns = _make_returns(n_assets=3)
        optimizer = PortfolioOptimizer(risk_aversion=0.5, max_weight=0.50)
        result = await optimizer.optimize(returns)
        assert isinstance(result, OptimizationResult)

    @pytest.mark.asyncio
    async def test_config_constructor(self):
        returns = _make_returns(n_assets=3)
        cfg = OptimizerConfig(risk_aversion=0.5, max_weight=0.50)
        optimizer = PortfolioOptimizer(config=cfg)
        result = await optimizer.optimize(returns)
        assert isinstance(result, OptimizationResult)

    @pytest.mark.asyncio
    async def test_empty_returns_raises(self):
        empty = pl.DataFrame(schema=["A", "B"])
        optimizer = PortfolioOptimizer(max_weight=1.0)
        with pytest.raises(ValueError, match="at least one row"):
            await optimizer.optimize(empty)

    @pytest.mark.asyncio
    async def test_zero_columns_raises(self):
        empty = pl.DataFrame()
        optimizer = PortfolioOptimizer(max_weight=1.0)
        with pytest.raises(ValueError, match="at least one row"):
            await optimizer.optimize(empty)

    @pytest.mark.asyncio
    async def test_invalid_weight_bounds(self):
        returns = _make_returns(n_assets=3)
        optimizer = PortfolioOptimizer(max_weight=1.0)
        optimizer._cfg = OptimizerConfig(max_weight=0.05, min_weight=0.10)
        with pytest.raises(ValueError, match="weight bounds"):
            await optimizer.optimize(returns)

    @pytest.mark.asyncio
    async def test_invalid_cash_bounds(self):
        returns = _make_returns(n_assets=3)
        optimizer = PortfolioOptimizer(max_weight=1.0)
        optimizer._cfg = OptimizerConfig(min_cash_weight=0.30, max_cash_weight=0.10)
        with pytest.raises(ValueError, match="cash bounds"):
            await optimizer.optimize(returns)

    @pytest.mark.asyncio
    async def test_sector_constraint(self):
        returns = pl.DataFrame(
            {
                "A": [0.01, 0.02, 0.01, 0.02],
                "B": [0.01, 0.02, 0.01, 0.02],
                "C": [-0.01, -0.02, -0.01, -0.02],
            }
        )
        constraints = {"sector_map": {"Tech": ["A", "B"]}}
        optimizer = PortfolioOptimizer(max_weight=0.50, max_sector=0.40)
        result = await optimizer.optimize(returns, constraints=constraints)
        assert isinstance(result, OptimizationResult)
        sector_weight = sum(result.weights.get(t, 0) for t in ["A", "B"])
        assert sector_weight <= 0.40 + 1e-4

    @pytest.mark.asyncio
    async def test_min_holding_constraint(self):
        returns = _make_returns(n_assets=4)
        constraints = {"min_holding": {"ASSET0": 0.15}}
        optimizer = PortfolioOptimizer(max_weight=0.40)
        result = await optimizer.optimize(returns, constraints=constraints)
        if result.status in ("optimal", "optimal_inaccurate"):
            assert result.weights.get("ASSET0", 0) >= 0.15 - 1e-4

    @pytest.mark.asyncio
    async def test_with_current_weights_turnover(self):
        returns = _make_returns(n_assets=3)
        current = {"ASSET0": 0.50, "ASSET1": 0.30, "ASSET2": 0.20}
        optimizer = PortfolioOptimizer(max_weight=0.60, max_turnover=0.50)
        result = await optimizer.optimize(returns, current_weights=current)
        assert isinstance(result, OptimizationResult)
        if result.status in ("optimal", "optimal_inaccurate"):
            assert result.turnover is not None

    @pytest.mark.asyncio
    async def test_transactions_generated(self):
        returns = _make_returns(n_assets=4)
        optimizer = PortfolioOptimizer(max_weight=0.40)
        result = await optimizer.optimize(returns)
        if result.status in ("optimal", "optimal_inaccurate"):
            assert isinstance(result.transactions, list)
            for tx in result.transactions:
                assert "ticker" in tx
                assert "side" in tx
                assert tx["side"] in ("BUY", "SELL")
                assert "weight_change" in tx
                assert "cost_bps" in tx

    @pytest.mark.asyncio
    async def test_slacks_populated(self):
        returns = _make_returns(n_assets=3)
        optimizer = PortfolioOptimizer(max_weight=0.50)
        result = await optimizer.optimize(returns)
        if result.status in ("optimal", "optimal_inaccurate"):
            assert "minimum_invested" in result.slacks
            assert "maximum_invested" in result.slacks
            assert "max_weight" in result.slacks
            assert "min_weight" in result.slacks

    @pytest.mark.asyncio
    async def test_diagnostics_populated(self):
        returns = _make_returns(n_assets=3)
        optimizer = PortfolioOptimizer(max_weight=0.50)
        result = await optimizer.optimize(returns)
        if result.status in ("optimal", "optimal_inaccurate"):
            assert "solver" in result.diagnostics
            assert "cash_weight" in result.diagnostics

    @pytest.mark.asyncio
    async def test_single_asset_covariance(self):
        returns = pl.DataFrame({"A": [0.01, 0.02, 0.03]})
        optimizer = PortfolioOptimizer(max_weight=1.0, risk_aversion=0.1)
        result = await optimizer.optimize(returns)
        assert result.status in ("optimal", "optimal_inaccurate")
        assert result.weights["A"] == pytest.approx(1.0, abs=1e-3)

    @pytest.mark.asyncio
    async def test_fallback_solver_triggered(self, monkeypatch):
        call_count = {"n": 0}

        def mock_solve(prob, **kwargs):
            call_count["n"] += 1
            if call_count["n"] == 1:
                prob._status = "infeasible"
            else:
                prob._status = "optimal"
                import numpy as np

                prob._solution = cp.Variable(3)
                prob._solution.value = np.array([0.5, 0.3, 0.2])

        monkeypatch.setattr(cp.Problem, "solve", mock_solve)

        returns = _make_returns(n_assets=3)
        cfg = OptimizerConfig(max_weight=0.60, fallback_solver="SCS")
        optimizer = PortfolioOptimizer(config=cfg)
        result = await optimizer.optimize(returns)
        assert isinstance(result, OptimizationResult)
        assert call_count["n"] >= 2

    @pytest.mark.asyncio
    async def test_fallback_timeout(self, monkeypatch):
        call_count = {"n": 0}

        def mock_solve(prob, **kwargs):
            call_count["n"] += 1
            if call_count["n"] == 1:
                prob._status = "infeasible"
            else:
                # Simulate slow fallback
                import time

                time.sleep(1)

        monkeypatch.setattr(cp.Problem, "solve", mock_solve)
        returns = _make_returns(n_assets=3)
        cfg = OptimizerConfig(max_weight=0.60, fallback_solver="SCS", timeout_seconds=0.001)
        optimizer = PortfolioOptimizer(config=cfg)
        result = await optimizer.optimize(returns)
        assert result.status == "failed"
        assert result.diagnostics["reason"] == "fallback solver timeout exceeded"

    @pytest.mark.asyncio
    async def test_solver_returns_none_weights(self, monkeypatch):
        def mock_solve(prob, **kwargs):
            prob._status = "optimal"
            # Don't set value — leaves it as None

        monkeypatch.setattr(cp.Problem, "solve", mock_solve)
        returns = _make_returns(n_assets=3)
        optimizer = PortfolioOptimizer(max_weight=0.50)
        result = await optimizer.optimize(returns)
        assert result.status == "failed"
        assert result.diagnostics["reason"] == "solver returned no weights"

    @pytest.mark.asyncio
    async def test_nonoptimal_status_no_fallback(self, monkeypatch):
        def mock_solve(prob, **kwargs):
            prob._status = "infeasible"

        monkeypatch.setattr(cp.Problem, "solve", mock_solve)
        returns = _make_returns(n_assets=3)
        optimizer = PortfolioOptimizer(max_weight=0.50)
        result = await optimizer.optimize(returns)
        assert result.status == "infeasible"
        assert result.weights == {}
        assert result.diagnostics["reason"] == "solver did not produce an optimal solution"

    @pytest.mark.asyncio
    async def test_zero_risk_gives_zero_sharpe(self):
        returns = pl.DataFrame(
            {
                "A": [0.01, 0.01, 0.01],
                "B": [0.01, 0.01, 0.01],
            }
        )
        optimizer = PortfolioOptimizer(max_weight=1.0, risk_aversion=0.0)
        result = await optimizer.optimize(returns)
        if (
            result.status in ("optimal", "optimal_inaccurate")
            and result.expected_risk is not None
            and result.expected_risk == 0.0
        ):
            assert result.sharpe_ratio == 0.0

    @pytest.mark.asyncio
    async def test_current_weights_partial_mapping(self):
        returns = _make_returns(n_assets=4)
        current = {"ASSET0": 0.50}  # Only some assets
        optimizer = PortfolioOptimizer(max_weight=0.50)
        result = await optimizer.optimize(returns, current_weights=current)
        assert isinstance(result, OptimizationResult)

    @pytest.mark.asyncio
    async def test_no_sector_in_constraint_map(self):
        returns = _make_returns(n_assets=3)
        constraints = {"sector_map": {"Unknown": ["NONEXISTENT"]}}
        optimizer = PortfolioOptimizer(max_weight=0.50)
        result = await optimizer.optimize(returns, constraints=constraints)
        assert isinstance(result, OptimizationResult)

    @pytest.mark.asyncio
    async def test_min_holding_nonexistent_ticker(self):
        returns = _make_returns(n_assets=3)
        constraints = {"min_holding": {"NONEXISTENT": 0.20}}
        optimizer = PortfolioOptimizer(max_weight=0.50)
        result = await optimizer.optimize(returns, constraints=constraints)
        assert isinstance(result, OptimizationResult)
