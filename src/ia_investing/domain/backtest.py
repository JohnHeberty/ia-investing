from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class PointInTimeSignal:
    instrument_id: str
    signal_date: date
    knowledge_at: datetime
    score: Decimal
    source: str = "quant"


@dataclass(frozen=True, slots=True)
class HistoricalUniverseMember:
    instrument_id: str
    valid_from: date
    valid_to: date | None
    knowledge_at: datetime


def known_signals(signals: tuple[PointInTimeSignal, ...], decision_time: datetime) -> tuple[PointInTimeSignal, ...]:
    return tuple(
        signal
        for signal in signals
        if signal.knowledge_at <= decision_time and signal.signal_date <= decision_time.date()
    )


def historical_universe(
    members: tuple[HistoricalUniverseMember, ...],
    decision_time: datetime,
    benchmark_instrument_id: str | None,
) -> frozenset[str]:
    return frozenset(
        member.instrument_id
        for member in members
        if member.knowledge_at <= decision_time
        and member.valid_from <= decision_time.date()
        and (member.valid_to is None or member.valid_to > decision_time.date())
        and member.instrument_id != benchmark_instrument_id
    )


def select_equal_weight(
    signals: tuple[PointInTimeSignal, ...],
    universe: frozenset[str],
    top_n: int,
) -> dict[str, Decimal]:
    if top_n < 1:
        raise ValueError("top_n must be positive")
    ranked = sorted(
        (signal for signal in signals if signal.instrument_id in universe),
        key=lambda item: (-item.score, item.instrument_id),
    )[:top_n]
    if not ranked:
        return {}
    weight = Decimal(1) / Decimal(len(ranked))
    return {signal.instrument_id: weight for signal in ranked}


@dataclass(frozen=True, slots=True)
class MarketSession:
    session_date: date
    close_at: datetime


@dataclass(frozen=True, slots=True)
class PointInTimePrice:
    instrument_id: str
    session_date: date
    knowledge_at: datetime
    close: Decimal


@dataclass(frozen=True, slots=True)
class PointInTimeCorporateAction:
    instrument_id: str
    effective_date: date
    knowledge_at: datetime
    action_type: str
    value: Decimal
    tax_rate: Decimal = Decimal(0)


@dataclass(frozen=True, slots=True)
class InstitutionalBacktestConfig:
    start_date: date
    end_date: date
    signal_delay_sessions: int
    top_n: int
    initial_cash: Decimal
    transaction_cost_bps: Decimal = Decimal(0)
    sell_tax_bps: Decimal = Decimal(0)
    seed: int = 0


@dataclass(frozen=True, slots=True)
class BacktestTrade:
    instrument_id: str
    signal_date: date
    execution_date: date
    side: str
    quantity: Decimal
    price: Decimal
    gross_value: Decimal
    costs: Decimal


@dataclass(frozen=True, slots=True)
class BacktestNav:
    session_date: date
    cash: Decimal
    positions_value: Decimal
    nav: Decimal
    benchmark_nav: Decimal | None


@dataclass(frozen=True, slots=True)
class InstitutionalBacktestResult:
    config_sha256: str
    data_sha256: str
    result_sha256: str
    trades: tuple[BacktestTrade, ...]
    nav: tuple[BacktestNav, ...]
    applied_actions: tuple[tuple[str, date, str], ...]


def _canonical_hash(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)
    return hashlib.sha256(encoded.encode()).hexdigest()


def _validate_config(config: InstitutionalBacktestConfig) -> None:
    if config.end_date < config.start_date:
        raise ValueError("backtest end_date must not precede start_date")
    if config.signal_delay_sessions < 1:
        raise ValueError("signal delay must be at least one market session")
    if config.top_n < 1 or config.initial_cash <= 0:
        raise ValueError("top_n and initial_cash must be positive")
    if config.transaction_cost_bps < 0 or config.sell_tax_bps < 0:
        raise ValueError("costs and taxes must be nonnegative")


def _latest_prices(
    prices: tuple[PointInTimePrice, ...],
    session_date: date,
    cutoff: datetime,
) -> dict[str, Decimal]:
    revisions: dict[str, PointInTimePrice] = {}
    for item in prices:
        if item.session_date != session_date or item.knowledge_at > cutoff:
            continue
        previous = revisions.get(item.instrument_id)
        if previous is None or item.knowledge_at > previous.knowledge_at:
            revisions[item.instrument_id] = item
    if any(item.close <= 0 for item in revisions.values()):
        raise ValueError("point-in-time prices must be positive")
    return {instrument: item.close for instrument, item in revisions.items()}


def _latest_signal_per_instrument(
    signals: tuple[PointInTimeSignal, ...],
    cutoff: datetime,
    allowed_sources: frozenset[str] | None,
) -> tuple[PointInTimeSignal, ...]:
    latest: dict[str, PointInTimeSignal] = {}
    for signal in known_signals(signals, cutoff):
        if allowed_sources is not None and signal.source not in allowed_sources:
            continue
        previous = latest.get(signal.instrument_id)
        if previous is None or (signal.signal_date, signal.knowledge_at) > (
            previous.signal_date,
            previous.knowledge_at,
        ):
            latest[signal.instrument_id] = signal
    return tuple(latest.values())


def run_point_in_time_backtest(
    *,
    config: InstitutionalBacktestConfig,
    sessions: tuple[MarketSession, ...],
    signals: tuple[PointInTimeSignal, ...],
    universe_members: tuple[HistoricalUniverseMember, ...],
    prices: tuple[PointInTimePrice, ...],
    corporate_actions: tuple[PointInTimeCorporateAction, ...] = (),
    benchmark_instrument_id: str | None = None,
    allowed_signal_sources: frozenset[str] | None = None,
) -> InstitutionalBacktestResult:
    """Run a deterministic close-to-close simulation without future knowledge."""
    _validate_config(config)
    ordered_sessions = tuple(
        sorted(
            (item for item in sessions if config.start_date <= item.session_date <= config.end_date),
            key=lambda item: item.close_at,
        )
    )
    if not ordered_sessions or len({item.session_date for item in ordered_sessions}) != len(ordered_sessions):
        raise ValueError("backtest requires unique market sessions in the configured interval")
    if any(item.close_at.tzinfo is None for item in ordered_sessions):
        raise ValueError("market session cutoffs must be timezone-aware")

    config_hash = _canonical_hash(config)
    data_hash = _canonical_hash(
        {
            "sessions": ordered_sessions,
            "signals": signals,
            "universe": universe_members,
            "prices": prices,
            "actions": corporate_actions,
            "benchmark": benchmark_instrument_id,
            "sources": sorted(allowed_signal_sources) if allowed_signal_sources is not None else None,
        }
    )
    scheduled_targets: dict[int, list[tuple[date, dict[str, Decimal]]]] = defaultdict(list)
    for index, session in enumerate(ordered_sessions):
        execution_index = index + config.signal_delay_sessions
        if execution_index >= len(ordered_sessions):
            continue
        universe = historical_universe(universe_members, session.close_at, benchmark_instrument_id)
        ranked = _latest_signal_per_instrument(signals, session.close_at, allowed_signal_sources)
        scheduled_targets[execution_index].append(
            (session.session_date, select_equal_weight(ranked, universe, config.top_n))
        )

    cash = config.initial_cash
    quantities: dict[str, Decimal] = {}
    trades: list[BacktestTrade] = []
    nav_points: list[BacktestNav] = []
    applied_actions: list[tuple[str, date, str]] = []
    applied_action_indexes: set[int] = set()
    benchmark_units: Decimal | None = None
    cost_rate = config.transaction_cost_bps / Decimal(10_000)
    sell_tax_rate = config.sell_tax_bps / Decimal(10_000)

    for index, session in enumerate(ordered_sessions):
        daily_prices = _latest_prices(prices, session.session_date, session.close_at)
        for action_index, action in enumerate(corporate_actions):
            if (
                action_index in applied_action_indexes
                or action.effective_date > session.session_date
                or action.knowledge_at > session.close_at
            ):
                continue
            quantity = quantities.get(action.instrument_id, Decimal(0))
            if action.action_type == "split":
                if action.value <= 0:
                    raise ValueError("split factor must be positive")
                quantities[action.instrument_id] = quantity * action.value
            elif action.action_type in {"dividend", "jcp"}:
                if action.value < 0 or not Decimal(0) <= action.tax_rate <= Decimal(1):
                    raise ValueError("cash distribution and tax rate are invalid")
                cash += quantity * action.value * (Decimal(1) - action.tax_rate)
            elif action.action_type == "delist":
                liquidation_price = daily_prices.get(action.instrument_id, action.value)
                if quantity and liquidation_price <= 0:
                    raise ValueError("delisting requires a positive liquidation price")
                cash += quantity * liquidation_price
                quantities.pop(action.instrument_id, None)
            else:
                raise ValueError(f"unsupported corporate action: {action.action_type}")
            applied_action_indexes.add(action_index)
            applied_actions.append((action.instrument_id, action.effective_date, action.action_type))

        for signal_date, target_weights in scheduled_targets.get(index, []):
            missing = set(target_weights) - daily_prices.keys()
            if missing:
                raise ValueError(f"execution prices missing for instruments: {sorted(missing)}")
            marked_value = sum(
                (
                    quantity * daily_prices[instrument]
                    for instrument, quantity in quantities.items()
                    if instrument in daily_prices
                ),
                start=Decimal(0),
            )
            equity = cash + marked_value
            target_instruments = set(target_weights) | set(quantities)
            desired_quantities = {
                instrument: equity * target_weights.get(instrument, Decimal(0)) / daily_prices[instrument]
                for instrument in target_instruments
                if instrument in daily_prices
            }
            deltas = {
                instrument: desired_quantities.get(instrument, Decimal(0)) - quantities.get(instrument, Decimal(0))
                for instrument in target_instruments
            }
            for side in ("SELL", "BUY"):
                for instrument in sorted(deltas):
                    delta = deltas[instrument]
                    if not delta or (side == "SELL") != (delta < 0):
                        continue
                    price = daily_prices[instrument]
                    gross = abs(delta) * price
                    costs = gross * cost_rate + (gross * sell_tax_rate if side == "SELL" else Decimal(0))
                    if side == "BUY" and gross + costs > cash:
                        delta = max(Decimal(0), cash / (price * (Decimal(1) + cost_rate)))
                        gross = delta * price
                        costs = gross * cost_rate
                    if delta == 0:
                        continue
                    cash += gross - costs if side == "SELL" else -(gross + costs)
                    quantities[instrument] = quantities.get(instrument, Decimal(0)) + delta
                    if quantities[instrument] <= Decimal("1e-18"):
                        quantities.pop(instrument, None)
                    trades.append(
                        BacktestTrade(
                            instrument,
                            signal_date,
                            session.session_date,
                            side,
                            abs(delta),
                            price,
                            gross,
                            costs,
                        )
                    )

        positions_value = sum(
            (
                quantity * daily_prices[instrument]
                for instrument, quantity in quantities.items()
                if instrument in daily_prices
            ),
            start=Decimal(0),
        )
        if quantities.keys() - daily_prices.keys():
            raise ValueError("held position lacks a point-in-time mark")
        benchmark_nav = None
        if benchmark_instrument_id is not None:
            benchmark_price = daily_prices.get(benchmark_instrument_id)
            if benchmark_price is None:
                raise ValueError("benchmark price is missing")
            if benchmark_units is None:
                benchmark_units = config.initial_cash / benchmark_price
            benchmark_nav = benchmark_units * benchmark_price
        nav_points.append(
            BacktestNav(session.session_date, cash, positions_value, cash + positions_value, benchmark_nav)
        )

    result_payload = {"trades": trades, "nav": nav_points, "actions": applied_actions}
    return InstitutionalBacktestResult(
        config_hash,
        data_hash,
        _canonical_hash(result_payload),
        tuple(trades),
        tuple(nav_points),
        tuple(applied_actions),
    )


def validate_walk_forward_split(training_end: date, out_of_sample_start: date) -> None:
    if training_end >= out_of_sample_start:
        raise ValueError("training interval must end before out-of-sample evaluation")


def signal_ablation_sources(signals: tuple[PointInTimeSignal, ...]) -> dict[str, frozenset[str]]:
    sources = frozenset(signal.source for signal in signals)
    return {
        "full": sources,
        "quant_only": frozenset({"quant"}) & sources,
        **{f"without_{source}": sources - {source} for source in sorted(sources - {"quant"})},
    }
