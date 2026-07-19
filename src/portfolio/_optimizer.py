from __future__ import annotations

import logging
from dataclasses import dataclass, field

import cvxpy as cp
import numpy as np
import polars as pl

logger = logging.getLogger(__name__)

BPS_DIVISOR = 10_000.0
MAX_SOLVER_ITERS = 10_000
SOLVER_EPSILON = 1e-8
WEIGHT_THRESHOLD = 1e-6


@dataclass(frozen=True, slots=True)
class OptimizationResult:
    weights: dict[str, float]
    expected_return: float
    expected_risk: float
    sharpe_ratio: float
    turnover: float
    transactions: list[dict] = field(default_factory=list)


@dataclass(slots=True)
class OptimizerConfig:
    risk_aversion: float = 1.0
    max_weight: float = 0.10
    min_weight: float = 0.0
    max_sector: float = 0.30
    max_turnover: float = 0.20
    transaction_cost_bps: float = 10.0
    solver: str = "SCS"
    fallback_solver: str | None = None


class PortfolioOptimizer:
    def __init__(self, config: OptimizerConfig | None = None, **kwargs: float | str | None) -> None:
        if config is not None:
            self._cfg = config
        else:
            self._cfg = OptimizerConfig(**kwargs)  # type: ignore[arg-type]

    def _build_constraints(
        self,
        w: cp.Variable,
        n: int,
        current_w: np.ndarray,
        has_current: bool,
        constraints: dict | None,
        asset_idx: dict[str, int],
    ) -> list:
        constraint_list: list = [
            cp.sum(w) == 1,
            w >= self._cfg.min_weight,
            w <= self._cfg.max_weight,
        ]
        if has_current:
            constraint_list.append(cp.norm(w - current_w, 1) <= self._cfg.max_turnover)
        if constraints:
            sector_map = constraints.get("sector_map", {})
            for _sector, tickers in sector_map.items():
                sector_idx = [asset_idx[t] for t in tickers if t in asset_idx]
                if sector_idx:
                    constraint_list.append(cp.sum(w[sector_idx]) <= self._cfg.max_sector)
            min_holding = constraints.get("min_holding", {})
            for ticker, min_w in min_holding.items():
                if ticker in asset_idx:
                    constraint_list.append(w[asset_idx[ticker]] >= min_w)
        return constraint_list

    def _equal_weight_result(
        self, n: int, assets: tuple[str, ...], mu: np.ndarray, cov: np.ndarray,
    ) -> OptimizationResult:
        equal_w = np.ones(n) / n
        return OptimizationResult(
            weights={assets[i]: float(equal_w[i]) for i in range(n)},
            expected_return=float(mu @ equal_w),
            expected_risk=float(np.sqrt(equal_w @ cov @ equal_w)),
            sharpe_ratio=0.0,
            turnover=0.0,
            transactions=[],
        )

    def _build_transactions(
        self,
        assets: tuple[str, ...],
        opt_w: np.ndarray,
        current_w: np.ndarray,
        n: int,
    ) -> list[dict]:
        transactions: list[dict] = []
        for i in range(n):
            delta = float(opt_w[i] - current_w[i])
            if abs(delta) > WEIGHT_THRESHOLD:
                transactions.append({
                    "ticker": assets[i],
                    "side": "BUY" if delta > 0 else "SELL",
                    "weight_change": round(delta, 8),
                    "cost_bps": self._cfg.transaction_cost_bps,
                })
        return transactions

    async def optimize(
        self,
        returns: pl.DataFrame,
        current_weights: dict[str, float] | None = None,
        constraints: dict | None = None,
    ) -> OptimizationResult:
        assets = returns.columns
        n = len(assets)
        if returns.height == 0 or n == 0:
            raise ValueError("returns DataFrame must have at least one row and one column")
        asset_idx = {a: i for i, a in enumerate(assets)}

        returns_np = returns.to_numpy()
        mu = np.mean(returns_np, axis=0)
        cov = np.cov(returns_np, rowvar=False)
        if cov.ndim == 0:
            cov = cov.reshape(1, 1)

        w = cp.Variable(n)
        current_w = np.zeros(n)
        if current_weights:
            for k, v in current_weights.items():
                if k in asset_idx:
                    current_w[asset_idx[k]] = v

        transaction_cost = self._cfg.transaction_cost_bps / BPS_DIVISOR
        turnover_cost = transaction_cost * cp.norm(w - current_w, 1)

        objective = cp.Maximize(
            mu @ w - self._cfg.risk_aversion * cp.quad_form(w, cov) - turnover_cost
        )

        constraint_list = self._build_constraints(w, n, current_w, bool(current_weights), constraints, asset_idx)

        prob = cp.Problem(objective, constraint_list)
        prob.solve(solver=self._cfg.solver, max_iters=MAX_SOLVER_ITERS, eps=SOLVER_EPSILON)

        if prob.status not in ("optimal", "optimal_inaccurate") and self._cfg.fallback_solver is not None:
            logger.warning(
                "Primary solver '%s' returned '%s', trying fallback solver '%s'",
                self._cfg.solver,
                prob.status,
                self._cfg.fallback_solver,
            )
            prob.solve(solver=self._cfg.fallback_solver, max_iters=MAX_SOLVER_ITERS, eps=SOLVER_EPSILON)

        if prob.status not in ("optimal", "optimal_inaccurate"):
            logger.warning("Optimization failed with status: %s", prob.status)
            return self._equal_weight_result(n, tuple(assets), mu, cov)

        opt_w = w.value
        if opt_w is None:
            return self._equal_weight_result(n, tuple(assets), mu, cov)

        opt_weights = {
            assets[i]: round(float(opt_w[i]), 8)
            for i in range(n)
            if float(opt_w[i]) > WEIGHT_THRESHOLD
        }

        exp_ret = float(mu @ opt_w)
        exp_risk = float(np.sqrt(opt_w @ cov @ opt_w))
        sharpe = exp_ret / exp_risk if exp_risk > 0 else 0.0
        turnover_val = float(np.abs(opt_w - current_w).sum())
        transactions = self._build_transactions(tuple(assets), opt_w, current_w, n)

        return OptimizationResult(
            weights=opt_weights,
            expected_return=exp_ret,
            expected_risk=exp_risk,
            sharpe_ratio=sharpe,
            turnover=turnover_val,
            transactions=transactions,
        )
