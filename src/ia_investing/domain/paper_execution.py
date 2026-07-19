from __future__ import annotations

import hashlib
import json
import random
from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_DOWN, Decimal

INTENT_TRANSITIONS: dict[str, frozenset[str]] = {
    "draft": frozenset({"pending_approval", "cancelled"}),
    "pending_approval": frozenset({"approved", "cancelled", "expired", "failed"}),
    "approved": frozenset({"submitted", "cancelled", "expired", "failed"}),
    "submitted": frozenset({"completed", "cancelled", "expired", "failed"}),
    "completed": frozenset(),
    "cancelled": frozenset(),
    "expired": frozenset(),
    "failed": frozenset(),
}

ORDER_TRANSITIONS: dict[str, frozenset[str]] = {
    "created": frozenset({"accepted", "rejected", "cancelled", "expired"}),
    "accepted": frozenset({"partially_filled", "filled", "cancelled", "expired"}),
    "partially_filled": frozenset({"partially_filled", "filled", "cancelled", "expired"}),
    "filled": frozenset(),
    "cancelled": frozenset(),
    "rejected": frozenset(),
    "expired": frozenset(),
}


def validate_transition(current: str, target: str, transitions: dict[str, frozenset[str]]) -> None:
    if target not in transitions.get(current, frozenset()):
        raise ValueError(f"invalid paper state transition: {current} -> {target}")


@dataclass(frozen=True, slots=True)
class ExecutionConfiguration:
    version: str
    lot_size: Decimal
    max_participation: Decimal
    spread_bps: Decimal
    impact_bps_at_full_participation: Decimal
    fee_bps: Decimal
    tax_bps: Decimal
    latency_ms: int

    def validate(self) -> None:
        if self.lot_size <= 0 or self.latency_ms < 0:
            raise ValueError("lot size must be positive and latency nonnegative")
        if not Decimal(0) < self.max_participation <= Decimal(1):
            raise ValueError("max participation must be within (0, 1]")
        if any(
            value < 0 for value in (self.spread_bps, self.impact_bps_at_full_participation, self.fee_bps, self.tax_bps)
        ):
            raise ValueError("cost parameters must be nonnegative")


@dataclass(frozen=True, slots=True)
class MarketSnapshot:
    observed_at: datetime
    mid_price: Decimal
    available_quantity: Decimal
    market_open: bool


@dataclass(frozen=True, slots=True)
class TradingWindow:
    opens_at: datetime
    closes_at: datetime


def validate_paper_order_request(
    *,
    order_type: str,
    limit_price: Decimal | None,
    quantity: Decimal,
    lot_size: Decimal,
    earliest_execution_at: datetime,
    expires_at: datetime,
    trading_windows: tuple[TradingWindow, ...],
) -> None:
    if order_type not in {"market", "limit"}:
        raise ValueError("paper order type must be market or limit")
    if (order_type == "limit") != (limit_price is not None) or (limit_price is not None and limit_price <= 0):
        raise ValueError("limit paper order requires a positive limit price")
    if quantity <= 0 or lot_size <= 0 or quantity % lot_size:
        raise ValueError("paper order quantity must be a positive whole lot")
    if earliest_execution_at.tzinfo is None or expires_at.tzinfo is None or expires_at <= earliest_execution_at:
        raise ValueError("paper execution window is invalid")
    if not any(
        window.opens_at.tzinfo is not None
        and window.closes_at.tzinfo is not None
        and max(window.opens_at, earliest_execution_at) < min(window.closes_at, expires_at)
        for window in trading_windows
    ):
        raise ValueError("paper order has no open market session in its execution window")


@dataclass(frozen=True, slots=True)
class SimulatedFill:
    sequence: int
    quantity: Decimal
    price: Decimal
    gross_value: Decimal
    fee_value: Decimal
    tax_value: Decimal
    slippage_bps: Decimal
    market_timestamp: datetime


@dataclass(frozen=True, slots=True)
class SimulationResult:
    status: str
    fills: tuple[SimulatedFill, ...]
    unfilled_quantity: Decimal
    input_sha256: str
    seed: int


def simulate_order(
    *,
    side: str,
    quantity: Decimal,
    signal_at: datetime,
    approved_at: datetime,
    expires_at: datetime,
    snapshots: tuple[MarketSnapshot, ...],
    configuration: ExecutionConfiguration,
    seed: int,
    limit_price: Decimal | None = None,
) -> SimulationResult:
    configuration.validate()
    if side not in {"buy", "sell"} or quantity <= 0:
        raise ValueError("side and quantity are invalid")
    if signal_at.tzinfo is None or approved_at.tzinfo is None or expires_at.tzinfo is None:
        raise ValueError("execution timestamps must include timezone information")
    cutoff = max(signal_at, approved_at)
    eligible = tuple(
        item
        for item in snapshots
        if item.market_open
        and cutoff <= item.observed_at <= expires_at
        and item.mid_price > 0
        and item.available_quantity > 0
    )
    input_payload = {
        "side": side,
        "quantity": str(quantity),
        "signal_at": signal_at.isoformat(),
        "approved_at": approved_at.isoformat(),
        "expires_at": expires_at.isoformat(),
        "configuration_version": configuration.version,
        "seed": seed,
        "snapshots": [
            [item.observed_at.isoformat(), str(item.mid_price), str(item.available_quantity), item.market_open]
            for item in snapshots
        ],
    }
    input_sha256 = hashlib.sha256(json.dumps(input_payload, sort_keys=True).encode()).hexdigest()
    remaining = quantity
    fills: list[SimulatedFill] = []
    rng = random.Random(seed)
    direction = Decimal(1) if side == "buy" else Decimal(-1)
    for snapshot in eligible:
        capacity = snapshot.available_quantity * configuration.max_participation
        fill_quantity = min(remaining, capacity)
        fill_quantity = (fill_quantity / configuration.lot_size).to_integral_value(
            rounding=ROUND_DOWN
        ) * configuration.lot_size
        if fill_quantity <= 0:
            continue
        participation = fill_quantity / snapshot.available_quantity
        deterministic_jitter = Decimal(str(rng.uniform(-0.05, 0.05)))
        slippage_bps = max(
            Decimal(0),
            configuration.spread_bps / Decimal(2)
            + configuration.impact_bps_at_full_participation * participation * (Decimal(1) + deterministic_jitter),
        )
        price = snapshot.mid_price * (Decimal(1) + direction * slippage_bps / Decimal(10_000))
        if limit_price is not None and (
            (side == "buy" and price > limit_price) or (side == "sell" and price < limit_price)
        ):
            continue
        price = price.quantize(Decimal("0.00000001"))
        gross = fill_quantity * price
        fills.append(
            SimulatedFill(
                sequence=len(fills) + 1,
                quantity=fill_quantity,
                price=price,
                gross_value=gross,
                fee_value=(gross * configuration.fee_bps / Decimal(10_000)).quantize(Decimal("0.00000001")),
                tax_value=(gross * configuration.tax_bps / Decimal(10_000)).quantize(Decimal("0.00000001")),
                slippage_bps=slippage_bps.quantize(Decimal("0.000001")),
                market_timestamp=snapshot.observed_at,
            )
        )
        remaining -= fill_quantity
        if remaining <= 0:
            break
    status = "filled" if remaining == 0 else "partially_filled" if fills else "expired"
    return SimulationResult(status, tuple(fills), remaining, input_sha256, seed)


@dataclass(frozen=True, slots=True)
class LedgerDelta:
    instrument_quantity: Decimal
    cash_delta: Decimal
    fees: Decimal
    taxes: Decimal


def fill_to_ledger(side: str, fill: SimulatedFill) -> LedgerDelta:
    if side == "buy":
        return LedgerDelta(
            fill.quantity, -(fill.gross_value + fill.fee_value + fill.tax_value), fill.fee_value, fill.tax_value
        )
    if side == "sell":
        return LedgerDelta(
            -fill.quantity, fill.gross_value - fill.fee_value - fill.tax_value, fill.fee_value, fill.tax_value
        )
    raise ValueError("invalid side")


def reconciliation_is_blocking(*, quantity_delta: Decimal, cash_delta: Decimal, tolerance: Decimal) -> bool:
    if tolerance < 0:
        raise ValueError("tolerance must be nonnegative")
    return abs(quantity_delta) > tolerance or abs(cash_delta) > tolerance


def require_human_challenger_decision(decision: str, decided_by: str | None) -> None:
    if decision not in {"retained", "promoted", "rejected"} or not decided_by:
        raise ValueError("champion/challenger decision requires an attributed committee decision")


@dataclass(frozen=True, slots=True)
class ReconciliationOrder:
    order_id: str
    requested_quantity: Decimal
    recorded_filled_quantity: Decimal
    status: str


@dataclass(frozen=True, slots=True)
class ReconciliationFill:
    order_id: str
    event_key: str
    quantity: Decimal
    gross_value: Decimal
    fee_value: Decimal
    tax_value: Decimal
    side: str


@dataclass(frozen=True, slots=True)
class ReconciliationLedgerEntry:
    source_reference: str
    amount: Decimal
    quantity: Decimal


@dataclass(frozen=True, slots=True)
class DetectedBreak:
    rule: str
    resource_key: str
    expected: dict[str, str]
    actual: dict[str, str]
    severity: str
    blocking: bool


def reconcile_execution(
    orders: tuple[ReconciliationOrder, ...],
    fills: tuple[ReconciliationFill, ...],
    ledger: tuple[ReconciliationLedgerEntry, ...],
    *,
    tolerance: Decimal = Decimal("0.00000001"),
) -> tuple[DetectedBreak, ...]:
    if tolerance < 0:
        raise ValueError("reconciliation tolerance must be nonnegative")
    fills_by_order: dict[str, list[ReconciliationFill]] = {}
    for fill in fills:
        fills_by_order.setdefault(fill.order_id, []).append(fill)
    ledger_by_source = {entry.source_reference: entry for entry in ledger}
    breaks: list[DetectedBreak] = []
    for order in orders:
        order_fills = fills_by_order.get(order.order_id, [])
        actual_filled = sum((fill.quantity for fill in order_fills), start=Decimal(0))
        if actual_filled > order.requested_quantity + tolerance:
            breaks.append(
                DetectedBreak(
                    "order_overfill",
                    order.order_id,
                    {"maximum": str(order.requested_quantity)},
                    {"filled": str(actual_filled)},
                    "critical",
                    True,
                )
            )
        if abs(actual_filled - order.recorded_filled_quantity) > tolerance:
            breaks.append(
                DetectedBreak(
                    "order_fill_quantity",
                    order.order_id,
                    {"recorded": str(order.recorded_filled_quantity)},
                    {"sum_of_fills": str(actual_filled)},
                    "critical",
                    True,
                )
            )
        expected_status = (
            "filled"
            if actual_filled == order.requested_quantity
            else "partially_filled"
            if actual_filled
            else order.status
        )
        if order.status in {"filled", "partially_filled"} and order.status != expected_status:
            breaks.append(
                DetectedBreak(
                    "order_status",
                    order.order_id,
                    {"status": expected_status},
                    {"status": order.status},
                    "warning",
                    False,
                )
            )
    for fill in fills:
        source = f"paper-fill:{fill.event_key}"
        entry = ledger_by_source.get(source)
        expected_quantity = fill.quantity if fill.side == "buy" else -fill.quantity
        expected_amount = (
            -(fill.gross_value + fill.fee_value + fill.tax_value)
            if fill.side == "buy"
            else fill.gross_value - fill.fee_value - fill.tax_value
        )
        if entry is None:
            breaks.append(
                DetectedBreak(
                    "fill_missing_ledger",
                    fill.event_key,
                    {"source_reference": source},
                    {"source_reference": "missing"},
                    "critical",
                    True,
                )
            )
        elif abs(entry.quantity - expected_quantity) > tolerance or abs(entry.amount - expected_amount) > tolerance:
            breaks.append(
                DetectedBreak(
                    "fill_ledger_identity",
                    fill.event_key,
                    {"quantity": str(expected_quantity), "amount": str(expected_amount)},
                    {"quantity": str(entry.quantity), "amount": str(entry.amount)},
                    "critical",
                    True,
                )
            )
    return tuple(breaks)


REQUIRED_POST_MORTEM_LINEAGE = frozenset(
    {
        "portfolio_version_id",
        "thesis_version_ids",
        "agent_run_ids",
        "decision",
        "trade_intent_ids",
        "attribution_by_asset",
        "attribution_by_sector",
        "attribution_by_factor",
        "decision_attribution",
        "cost_attribution",
        "comparison",
        "error_classification",
        "corrective_actions",
    }
)


def immutable_report_hash(payload: dict[str, object]) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


def validate_post_mortem_lineage(attribution: dict[str, object]) -> None:
    missing = REQUIRED_POST_MORTEM_LINEAGE - attribution.keys()
    if missing:
        raise ValueError(f"post-mortem lineage is incomplete: {', '.join(sorted(missing))}")
    actions = attribution["corrective_actions"]
    if not isinstance(actions, list):
        raise ValueError("corrective_actions must be a list")
    for action in actions:
        if not isinstance(action, dict) or not all(
            action.get(field) for field in ("action", "owner_role", "due_at", "verification")
        ):
            raise ValueError("corrective action requires action, owner role, due date and verification")


@dataclass(frozen=True, slots=True)
class PaperAttribution:
    by_asset: dict[str, Decimal]
    by_sector: dict[str, Decimal]
    by_factor: dict[str, Decimal]
    decision: Decimal
    costs: Decimal
    gross_return: Decimal
    net_return: Decimal


def calculate_paper_attribution(
    *,
    weights: dict[str, Decimal],
    asset_returns: dict[str, Decimal],
    sectors: dict[str, str],
    factor_exposures: dict[str, Decimal],
    factor_returns: dict[str, Decimal],
    baseline_return: Decimal,
    fee_return: Decimal,
    tax_return: Decimal,
    slippage_return: Decimal,
) -> PaperAttribution:
    if set(weights) - asset_returns.keys() or set(weights) - sectors.keys():
        raise ValueError("asset return or sector is missing for attribution")
    if set(factor_exposures) - factor_returns.keys():
        raise ValueError("factor return is missing for attribution")
    if any(value < 0 for value in (fee_return, tax_return, slippage_return)):
        raise ValueError("attributed costs must be nonnegative")
    by_asset = {asset: weight * asset_returns[asset] for asset, weight in weights.items()}
    by_sector: dict[str, Decimal] = {}
    for asset, contribution in by_asset.items():
        sector = sectors[asset]
        by_sector[sector] = by_sector.get(sector, Decimal(0)) + contribution
    by_factor = {factor: exposure * factor_returns[factor] for factor, exposure in factor_exposures.items()}
    gross = sum(by_asset.values(), start=Decimal(0))
    costs = fee_return + tax_return + slippage_return
    return PaperAttribution(by_asset, by_sector, by_factor, gross - baseline_return, costs, gross, gross - costs)


def compare_strategy_results(
    *, expected: Decimal, backtest: Decimal, paper: Decimal, realized: Decimal
) -> dict[str, Decimal]:
    return {
        "expected": expected,
        "backtest": backtest,
        "paper": paper,
        "realized": realized,
        "paper_vs_expected": paper - expected,
        "paper_vs_backtest": paper - backtest,
        "realized_vs_paper": realized - paper,
    }


def classify_post_mortem_error(
    *, data_incident: bool, model_miss: bool, decision_override: bool, execution_miss: bool, operational_break: bool
) -> str:
    causes = {
        "data": data_incident,
        "model": model_miss,
        "decision": decision_override,
        "execution": execution_miss,
        "operation": operational_break,
    }
    active = [name for name, enabled in causes.items() if enabled]
    return active[0] if len(active) == 1 else "mixed" if active else "none"


def validate_challenger_comparison(configuration: dict[str, object]) -> str:
    required = {"benchmark_id", "risk_policy_version", "cost_model_version", "window_type", "out_of_sample"}
    missing = required - configuration.keys()
    if missing:
        raise ValueError(f"challenger comparison is incomplete: {', '.join(sorted(missing))}")
    if configuration["window_type"] != "paper" or configuration["out_of_sample"] is not True:
        raise ValueError("challenger comparison must be out-of-sample paper")
    return immutable_report_hash(configuration)


@dataclass(frozen=True, slots=True)
class DatedReturn:
    observed_at: datetime
    value: Decimal


@dataclass(frozen=True, slots=True)
class ChallengerCriteria:
    minimum_sessions: int
    maximum_drawdown: Decimal
    data_healthy: bool
    theses_healthy: bool
    risk_healthy: bool
    liquidity_healthy: bool


@dataclass(frozen=True, slots=True)
class ChallengerAssessment:
    eligible: bool
    failures: tuple[str, ...]
    metrics: dict[str, Decimal]
    evidence_sha256: str


def _compounded_return(values: tuple[Decimal, ...]) -> Decimal:
    wealth = Decimal(1)
    for value in values:
        wealth *= Decimal(1) + value
    return wealth - Decimal(1)


def _return_drawdown(values: tuple[Decimal, ...]) -> Decimal:
    wealth = Decimal(1)
    peak = Decimal(1)
    maximum = Decimal(0)
    for value in values:
        wealth *= Decimal(1) + value
        peak = max(peak, wealth)
        maximum = max(maximum, (peak - wealth) / peak)
    return maximum


def assess_challenger(
    *,
    champion: tuple[DatedReturn, ...],
    challenger: tuple[DatedReturn, ...],
    benchmark: tuple[DatedReturn, ...],
    criteria: ChallengerCriteria,
) -> ChallengerAssessment:
    if criteria.minimum_sessions < 2 or not Decimal(0) <= criteria.maximum_drawdown <= Decimal(1):
        raise ValueError("challenger criteria are invalid")
    dates = tuple(item.observed_at for item in champion)
    if (
        dates != tuple(item.observed_at for item in challenger)
        or dates != tuple(item.observed_at for item in benchmark)
        or len(set(dates)) != len(dates)
        or any(item.tzinfo is None for item in dates)
    ):
        raise ValueError("champion, challenger and benchmark require identical unique dated observations")
    champion_values = tuple(item.value for item in champion)
    challenger_values = tuple(item.value for item in challenger)
    benchmark_values = tuple(item.value for item in benchmark)
    challenger_drawdown = _return_drawdown(challenger_values)
    divergences = tuple(challenger_values[index] - champion_values[index] for index in range(len(dates)))
    divergence_mean = sum(divergences, start=Decimal(0)) / Decimal(len(divergences)) if divergences else Decimal(0)
    divergence_stability = (
        sum(((value - divergence_mean) ** 2 for value in divergences), start=Decimal(0)) / Decimal(len(divergences) - 1)
        if len(divergences) > 1
        else Decimal(0)
    )
    failures: list[str] = []
    if len(dates) < criteria.minimum_sessions:
        failures.append("insufficient_history")
    if challenger_drawdown > criteria.maximum_drawdown:
        failures.append("drawdown_limit")
    for name, passed in (
        ("data_gate", criteria.data_healthy),
        ("thesis_gate", criteria.theses_healthy),
        ("risk_gate", criteria.risk_healthy),
        ("liquidity_gate", criteria.liquidity_healthy),
    ):
        if not passed:
            failures.append(name)
    metrics = {
        "champion_return": _compounded_return(champion_values),
        "challenger_return": _compounded_return(challenger_values),
        "benchmark_return": _compounded_return(benchmark_values),
        "challenger_drawdown": challenger_drawdown,
        "divergence_variance": divergence_stability,
    }
    evidence = {
        "dates": dates,
        "champion": champion_values,
        "challenger": challenger_values,
        "benchmark": benchmark_values,
        "criteria": criteria,
        "metrics": metrics,
        "failures": failures,
    }
    return ChallengerAssessment(not failures, tuple(failures), metrics, immutable_report_hash(evidence))
