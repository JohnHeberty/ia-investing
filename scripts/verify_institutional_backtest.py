from __future__ import annotations

import asyncio
from argparse import ArgumentParser
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

from database.core import session_scope
from ia_investing.application.backtests import InstitutionalBacktestService
from ia_investing.domain.backtest import (
    HistoricalUniverseMember,
    InstitutionalBacktestConfig,
    MarketSession,
    PointInTimePrice,
    PointInTimeSignal,
)
from ia_investing.domain.identity import InstitutionalAccessContext


async def verify(organization_id: UUID, benchmark_index_id: UUID) -> None:
    first_close = datetime(2026, 1, 2, 20, tzinfo=UTC)
    second_close = datetime(2026, 1, 5, 20, tzinfo=UTC)
    context = InstitutionalAccessContext(
        "service:backtest-verification",
        organization_id,
        frozenset(),
        frozenset({"portfolio:propose", "portfolio:read"}),
        "paper",
    )
    arguments = {
        "config": InstitutionalBacktestConfig(
            date(2026, 1, 2), date(2026, 1, 5), 1, 1, Decimal("100000"), Decimal("5"), Decimal("2"), 42
        ),
        "strategy_name": "PIT verification",
        "universe_definition": {"kind": "verification", "top_n": 1},
        "benchmark_index_id": benchmark_index_id,
        "benchmark_instrument_id": "benchmark",
        "sessions": (MarketSession(date(2026, 1, 2), first_close), MarketSession(date(2026, 1, 5), second_close)),
        "signals": (PointInTimeSignal("asset", date(2026, 1, 2), first_close, Decimal("1")),),
        "universe_members": (
            HistoricalUniverseMember("asset", date(2020, 1, 1), None, datetime(2020, 1, 1, tzinfo=UTC)),
        ),
        "prices": (
            PointInTimePrice("asset", date(2026, 1, 2), first_close, Decimal("10")),
            PointInTimePrice("benchmark", date(2026, 1, 2), first_close, Decimal("100")),
            PointInTimePrice("asset", date(2026, 1, 5), second_close, Decimal("11")),
            PointInTimePrice("benchmark", date(2026, 1, 5), second_close, Decimal("101")),
        ),
        "corporate_actions": (),
        "code_version": "verification-v1",
        "context": context,
    }
    async with session_scope() as session:
        service = InstitutionalBacktestService(session)
        first = await service.run(**arguments)
        replay = await service.run(**arguments)
        if first.id != replay.id or first.status != "succeeded" or not first.result_sha256:
            raise RuntimeError("backtest replay did not preserve the reproducible run")
        queried = await service.get(first.id, context)
        if queried.id != first.id:
            raise RuntimeError("backtest query returned a different run")
        print(
            "institutional-backtest-ok",
            f"run_id={first.id}",
            f"data_sha256={first.data_snapshot_sha256}",
            f"result_sha256={first.result_sha256}",
        )


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("--organization-id", type=UUID, required=True)
    parser.add_argument("--benchmark-index-id", type=UUID, required=True)
    arguments = parser.parse_args()
    asyncio.run(verify(arguments.organization_id, arguments.benchmark_index_id))
