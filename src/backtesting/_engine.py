from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import date

import polars as pl

from ._metrics import BacktestMetrics, compute_metrics

logger = logging.getLogger(__name__)

MIN_HISTORY_BARS = 20  # Minimum bars for reliable metric computation
WEIGHT_THRESHOLD = 1e-6  # Positions below this weight are excluded from turnover calculations
BPS_DIVISOR = 10_000.0  # 1 basis point = 0.01% = 1/10_000


@dataclass(frozen=True, slots=True)
class BacktestResult:
    cagr: float
    sharpe: float
    sortino: float
    calmar: float
    max_drawdown: float
    win_rate: float
    total_return: float
    annual_volatility: float
    benchmark_return: float
    alpha: float
    information_ratio: float
    trades: list[dict[str, object]] = field(default_factory=list)
    metrics: BacktestMetrics | None = None


def _daily(dates: list[date]) -> set[date]:
    return set(dates)


def _weekly(dates: list[date]) -> set[date]:
    result: set[date] = set()
    seen_weeks: set[tuple[int, int]] = set()
    for d in reversed(dates):
        wk = d.isocalendar()[:2]
        if wk not in seen_weeks:
            seen_weeks.add(wk)
            result.add(d)
    return result


def _monthly(dates: list[date]) -> set[date]:
    result: set[date] = set()
    seen_months: set[tuple[int, int]] = set()
    for d in reversed(dates):
        key = (d.year, d.month)
        if key not in seen_months:
            seen_months.add(key)
            result.add(d)
    return result


def _quarterly(dates: list[date]) -> set[date]:
    result: set[date] = set()
    seen_quarters: set[tuple[int, int]] = set()
    for d in reversed(dates):
        q = (d.year, (d.month - 1) // 3)
        if q not in seen_quarters:
            seen_quarters.add(q)
            result.add(d)
    return result


REBALANCE_STRATEGIES: dict[str, Callable[[list[date]], set[date]]] = {
    "daily": _daily,
    "weekly": _weekly,
    "monthly": _monthly,
    "quarterly": _quarterly,
}


def _get_rebalance_dates(dates: list[date], freq: str) -> set[date]:
    strategy = REBALANCE_STRATEGIES.get(freq)
    if strategy is None:
        raise ValueError(f"Unknown rebalance frequency: {freq!r}")
    return strategy(dates)


def _compute_transaction_costs(
    old_w: float,
    new_w: float,
    equity: float,
    cost_bps: float,
    slippage_bps: float,
) -> tuple[float, float]:
    """Return (trade_value, cost_amount)."""
    delta = new_w - old_w
    cost_rate = (cost_bps + slippage_bps) / BPS_DIVISOR
    trade_value = equity * abs(delta)
    cost_amount = trade_value * cost_rate
    return trade_value, cost_amount


def _rebalance_on_date(
    prices_df: pl.DataFrame,
    current_date: date,
    price_cols: list[str],
    current_weights: dict[str, float],
    target_weights: dict[str, float],
    new_equity: float,
    cost_bps: float,
    slippage_bps: float,
) -> tuple[dict[str, float], float, list[dict[str, object]]]:
    """Execute rebalance for a single date. Returns (new_weights, updated_equity, trades)."""
    available_history = prices_df.filter(pl.col("date") <= current_date)
    if available_history.height < MIN_HISTORY_BARS:
        return current_weights.copy(), new_equity, []

    new_weights = {ticker: target_weights.get(ticker, 0.0) for ticker in price_cols}
    trades: list[dict[str, object]] = []

    for ticker in price_cols:
        old_w = current_weights.get(ticker, 0.0)
        new_w = new_weights.get(ticker, 0.0)
        delta = new_w - old_w
        if abs(delta) > WEIGHT_THRESHOLD:
            trade_value, cost_amount = _compute_transaction_costs(
                old_w,
                new_w,
                new_equity,
                cost_bps,
                slippage_bps,
            )
            new_equity -= cost_amount
            trades.append(
                {
                    "date": str(current_date),
                    "ticker": ticker,
                    "side": "BUY" if delta > 0 else "SELL",
                    "weight_from": round(old_w, 6),
                    "weight_to": round(new_w, 6),
                    "value_brl": round(trade_value, 2),
                    "cost_brl": round(cost_amount, 2),
                }
            )

    w_sum = sum(new_weights.values())
    if w_sum > 0:
        new_weights = {c: v / w_sum for c, v in new_weights.items()}

    return new_weights, new_equity, trades


class BacktestEngine:
    def __init__(
        self,
        initial_capital: float = 1_000_000.0,
        transaction_cost_bps: float = 10.0,
        slippage_bps: float = 5.0,
    ) -> None:
        self.initial_capital = initial_capital
        self.transaction_cost_bps = transaction_cost_bps
        self.slippage_bps = slippage_bps

    async def run(
        self,
        strategy_fn: Callable[
            [pl.DataFrame, list[str], dict[str, float]],
            Awaitable[dict[str, float]],
        ],
        universe_data: pl.DataFrame,
        start_date: date,
        end_date: date,
        rebalance_freq: str = "monthly",
        benchmark: str = "IBOVESPA",
    ) -> BacktestResult:
        price_cols = [c for c in universe_data.columns if c != "date"]
        filtered = universe_data.filter(
            (pl.col("date") >= pl.lit(start_date)) & (pl.col("date") <= pl.lit(end_date))
        ).sort("date")

        if filtered.height < 2:
            return self._empty_result()

        dates = filtered["date"].to_list()
        rebalance_dates = _get_rebalance_dates(dates, rebalance_freq)

        prices_df = filtered.select(["date", *price_cols])
        returns_df = prices_df.drop("date").select([pl.col(c).pct_change() for c in price_cols])

        equity_curve: list[float] = [self.initial_capital]
        current_weights: dict[str, float] = dict.fromkeys(price_cols, 0.0)
        trades_log: list[dict[str, object]] = []

        for i in range(1, len(dates)):
            daily_returns = returns_df.row(i - 1, named=True)
            portfolio_return = sum(current_weights.get(c, 0.0) * (daily_returns.get(c, 0.0) or 0.0) for c in price_cols)
            new_equity = equity_curve[-1] * (1.0 + portfolio_return)
            equity_curve.append(new_equity)

            if dates[i] in rebalance_dates:
                try:
                    new_weights = await strategy_fn(
                        prices_df.filter(pl.col("date") <= dates[i]),
                        price_cols,
                        current_weights,
                    )
                except Exception:
                    logger.exception("Strategy failed at %s", dates[i])
                    new_weights = current_weights.copy()

                current_weights, new_equity, new_trades = _rebalance_on_date(
                    prices_df,
                    dates[i],
                    price_cols,
                    current_weights,
                    new_weights,
                    new_equity,
                    self.transaction_cost_bps,
                    self.slippage_bps,
                )
                equity_curve[-1] = new_equity
                trades_log.extend(new_trades)

        bench_prices: list[float] | None = None
        if benchmark in universe_data.columns:
            bench_prices = filtered.select(pl.col(benchmark)).to_series().to_list()

        m = compute_metrics(equity_curve, bench_prices)

        return BacktestResult(
            cagr=m.cagr,
            sharpe=m.sharpe_ratio,
            sortino=m.sortino_ratio,
            calmar=m.calmar_ratio,
            max_drawdown=m.max_drawdown,
            win_rate=m.win_rate,
            total_return=m.total_return,
            annual_volatility=m.annual_volatility,
            benchmark_return=m.benchmark_return,
            alpha=m.alpha,
            information_ratio=m.information_ratio,
            trades=trades_log,
            metrics=m,
        )

    def _empty_result(self) -> BacktestResult:
        return BacktestResult(
            cagr=0.0,
            sharpe=0.0,
            sortino=0.0,
            calmar=0.0,
            max_drawdown=0.0,
            win_rate=0.0,
            total_return=0.0,
            annual_volatility=0.0,
            benchmark_return=0.0,
            alpha=0.0,
            information_ratio=0.0,
            trades=[],
        )
