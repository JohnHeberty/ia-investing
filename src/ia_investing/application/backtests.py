from __future__ import annotations

import hashlib
from dataclasses import asdict
from datetime import date
from decimal import Decimal
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.portfolio_domain import BacktestConfig, InstitutionalBacktestRun
from ia_investing.domain.backtest import (
    HistoricalUniverseMember,
    InstitutionalBacktestConfig,
    MarketSession,
    PointInTimeCorporateAction,
    PointInTimePrice,
    PointInTimeSignal,
    run_point_in_time_backtest,
)
from ia_investing.domain.identity import InstitutionalAccessContext, ResourceAttributes, authorize


class InstitutionalBacktestService:
    """Persist a deterministic PIT backtest and return the same run on replay."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def run(
        self,
        *,
        config: InstitutionalBacktestConfig,
        strategy_name: str,
        universe_definition: dict[str, object],
        benchmark_index_id: UUID,
        benchmark_instrument_id: str | None,
        sessions: tuple[MarketSession, ...],
        signals: tuple[PointInTimeSignal, ...],
        universe_members: tuple[HistoricalUniverseMember, ...],
        prices: tuple[PointInTimePrice, ...],
        corporate_actions: tuple[PointInTimeCorporateAction, ...],
        code_version: str,
        context: InstitutionalAccessContext,
    ) -> InstitutionalBacktestRun:
        authorize(context, "portfolio:propose", ResourceAttributes(context.organization_id))
        if not strategy_name.strip() or not code_version.strip():
            raise ValueError("strategy_name and code_version are required")
        result = run_point_in_time_backtest(
            config=config,
            sessions=sessions,
            signals=signals,
            universe_members=universe_members,
            prices=prices,
            corporate_actions=corporate_actions,
            benchmark_instrument_id=benchmark_instrument_id,
        )
        storage_config_sha256 = hashlib.sha256(f"{context.organization_id}:{result.config_sha256}".encode()).hexdigest()
        stored_config = await self.session.scalar(
            sa.select(BacktestConfig).where(
                BacktestConfig.organization_id == context.organization_id,
                BacktestConfig.config_sha256 == storage_config_sha256,
            )
        )
        if stored_config is None:
            stored_config = BacktestConfig(
                organization_id=context.organization_id,
                strategy_name=strategy_name.strip(),
                universe_definition=universe_definition,
                benchmark_index_id=benchmark_index_id,
                start_date=config.start_date,
                end_date=config.end_date,
                signal_delay_sessions=config.signal_delay_sessions,
                costs={"transaction_cost_bps": str(config.transaction_cost_bps)},
                taxes={"sell_tax_bps": str(config.sell_tax_bps)},
                seed=config.seed,
                config_sha256=storage_config_sha256,
            )
            self.session.add(stored_config)
            await self.session.flush()
        existing = await self.session.scalar(
            sa.select(InstitutionalBacktestRun).where(
                InstitutionalBacktestRun.config_id == stored_config.id,
                InstitutionalBacktestRun.code_version == code_version,
                InstitutionalBacktestRun.data_snapshot_sha256 == result.data_sha256,
            )
        )
        if existing is not None:
            return existing
        run = InstitutionalBacktestRun(
            config_id=stored_config.id,
            code_version=code_version,
            data_snapshot_sha256=result.data_sha256,
            status="succeeded",
            result_sha256=result.result_sha256,
            results={
                "algorithm_config_sha256": result.config_sha256,
                "trades": [_json_value(asdict(item)) for item in result.trades],
                "nav": [_json_value(asdict(item)) for item in result.nav],
                "applied_actions": [_json_value(list(item)) for item in result.applied_actions],
            },
        )
        self.session.add(run)
        await self.session.flush()
        return run

    async def get(self, run_id: UUID, context: InstitutionalAccessContext) -> InstitutionalBacktestRun:
        row = await self.session.execute(
            sa.select(InstitutionalBacktestRun, BacktestConfig)
            .join(BacktestConfig, BacktestConfig.id == InstitutionalBacktestRun.config_id)
            .where(InstitutionalBacktestRun.id == run_id)
        )
        pair = row.one_or_none()
        if pair is None:
            raise LookupError("backtest run not found")
        run, config = pair
        authorize(context, "portfolio:read", ResourceAttributes(config.organization_id))
        return run  # type: ignore[no-any-return]


def validate_walk_forward_dates(
    start_date: date, training_end: date, out_of_sample_start: date, end_date: date
) -> None:
    if not (start_date <= training_end < out_of_sample_start <= end_date):
        raise ValueError("walk-forward dates must be ordered and non-overlapping")


def _json_value(value: object) -> object:
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    if isinstance(value, (date, Decimal)):
        return str(value)
    return value
