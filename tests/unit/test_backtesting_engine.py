from __future__ import annotations

from datetime import date, timedelta

import polars as pl
import pytest

from backtesting import BacktestEngine


@pytest.mark.asyncio
async def test_legacy_engine_rebalance_uses_current_and_target_weights() -> None:
    first = date(2026, 1, 1)
    frame = pl.DataFrame(
        {
            "date": [first + timedelta(days=index) for index in range(24)],
            "A": [100.0 + index for index in range(24)],
            "B": [100.0 for _ in range(24)],
        }
    )

    async def strategy(_prices: pl.DataFrame, _assets: list[str], _current: dict[str, float]) -> dict[str, float]:
        return {"A": 1.0, "B": 0.0}

    result = await BacktestEngine(transaction_cost_bps=10, slippage_bps=5).run(
        strategy, frame, first, first + timedelta(days=23), rebalance_freq="daily"
    )
    assert result.trades
    assert result.trades[0]["ticker"] == "A"
    assert result.trades[0]["weight_from"] == 0.0
    assert result.trades[0]["weight_to"] == 1.0
    assert result.trades[0]["cost_brl"] > 0
