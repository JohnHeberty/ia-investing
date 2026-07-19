from __future__ import annotations

from dataclasses import dataclass

import numpy as np

TRADING_DAYS_PER_YEAR = 252


@dataclass(frozen=True, slots=True)
class BacktestMetrics:
    cagr: float
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    max_drawdown: float
    win_rate: float
    total_return: float
    annual_volatility: float
    benchmark_return: float
    alpha: float
    information_ratio: float


def _compute_cagr(equity_curve: list[float], periods_per_year: float) -> float:
    if not equity_curve or equity_curve[0] <= 0:
        return 0.0
    n_periods = len(equity_curve) - 1
    if n_periods == 0:
        return 0.0
    final = equity_curve[-1]
    initial = equity_curve[0]
    if final <= 0 or initial <= 0:
        return 0.0
    return (final / initial) ** (periods_per_year / n_periods) - 1.0


def _compute_max_drawdown(equity_curve: list[float]) -> float:
    peak = equity_curve[0]
    max_dd = 0.0
    for val in equity_curve:
        if val > peak:
            peak = val
        dd = (peak - val) / peak if peak > 0 else 0.0
        if dd > max_dd:
            max_dd = dd
    return max_dd


def _compute_sharpe(returns: np.ndarray, rf: float = 0.0) -> float:
    if len(returns) < 2:
        return 0.0
    excess = returns - rf / TRADING_DAYS_PER_YEAR
    mu = np.mean(excess)
    sigma = np.std(excess, ddof=1)
    if sigma == 0:
        return 0.0
    return float(mu / sigma * np.sqrt(TRADING_DAYS_PER_YEAR))


def _compute_sortino(returns: np.ndarray, rf: float = 0.0) -> float:
    if len(returns) < 2:
        return 0.0
    excess = returns - rf / TRADING_DAYS_PER_YEAR
    mu = np.mean(excess)
    downside = returns[returns < 0]
    if len(downside) == 0:
        return 0.0
    downside_std = np.sqrt(np.mean(downside**2))
    if downside_std == 0:
        return 0.0
    return float(mu / downside_std * np.sqrt(TRADING_DAYS_PER_YEAR))


def _compute_calmar(cagr: float, max_dd: float) -> float:
    if max_dd == 0:
        return 0.0
    return cagr / max_dd


def _compute_information_ratio(portfolio_returns: np.ndarray, benchmark_returns: np.ndarray) -> float:
    if len(portfolio_returns) < 2:
        return 0.0
    active = portfolio_returns - benchmark_returns
    tracking_error = np.std(active, ddof=1)
    if tracking_error == 0:
        return 0.0
    return float(np.mean(active) / tracking_error * np.sqrt(TRADING_DAYS_PER_YEAR))


def compute_metrics(
    equity_curve: list[float],
    benchmark_prices: list[float] | None = None,
    periods_per_year: float = TRADING_DAYS_PER_YEAR,
) -> BacktestMetrics:
    total_return = equity_curve[-1] / equity_curve[0] - 1.0
    periods = len(equity_curve) - 1
    cagr = _compute_cagr(equity_curve, periods_per_year)

    ret_arr = np.array([equity_curve[i] / equity_curve[i - 1] - 1.0 for i in range(1, len(equity_curve))])

    benchmark_return = 0.0
    alpha = 0.0
    ir = 0.0

    if benchmark_prices and len(benchmark_prices) >= 2:
        benchmark_return = benchmark_prices[-1] / benchmark_prices[0] - 1.0
        benchmark_cagr = (
            ((benchmark_prices[-1] / benchmark_prices[0]) ** (periods_per_year / periods) - 1.0) if periods > 0 else 0.0
        )
        bench_rets = np.array(
            [benchmark_prices[i] / benchmark_prices[i - 1] - 1.0 for i in range(1, len(benchmark_prices))]
        )
        min_len = min(len(ret_arr), len(bench_rets))
        alpha = cagr - benchmark_cagr
        ir = _compute_information_ratio(ret_arr[:min_len], bench_rets[:min_len])

    sharpe = _compute_sharpe(ret_arr)
    sortino = _compute_sortino(ret_arr)
    max_dd = _compute_max_drawdown(equity_curve)
    calmar = _compute_calmar(cagr, max_dd)
    win_rate = float(np.mean(ret_arr > 0)) if len(ret_arr) > 0 else 0.0
    annual_vol = float(np.std(ret_arr, ddof=1) * np.sqrt(TRADING_DAYS_PER_YEAR)) if len(ret_arr) > 1 else 0.0

    return BacktestMetrics(
        cagr=round(cagr, 6),
        sharpe_ratio=round(sharpe, 4),
        sortino_ratio=round(sortino, 4),
        calmar_ratio=round(calmar, 4),
        max_drawdown=round(max_dd, 6),
        win_rate=round(win_rate, 4),
        total_return=round(total_return, 6),
        annual_volatility=round(annual_vol, 6),
        benchmark_return=round(benchmark_return, 6),
        alpha=round(alpha, 6),
        information_ratio=round(ir, 4),
    )
