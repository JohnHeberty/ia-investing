from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from decimal import Decimal

PORTFOLIO_TRANSITIONS: dict[str, frozenset[str]] = {
    "draft": frozenset({"researching", "archived"}),
    "researching": frozenset({"simulated", "suspended", "archived"}),
    "simulated": frozenset({"committee_review", "researching", "suspended"}),
    "committee_review": frozenset({"approved", "simulated", "suspended"}),
    "approved": frozenset({"paper_live", "suspended"}),
    "paper_live": frozenset({"suspended", "archived"}),
    "suspended": frozenset({"researching", "paper_live", "archived"}),
    "eligible_for_live": frozenset(),
    "live": frozenset(),
    "archived": frozenset(),
}


def canonical_hash(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)
    return hashlib.sha256(encoded.encode()).hexdigest()


def validate_portfolio_transition(current: str, target: str) -> None:
    if target not in PORTFOLIO_TRANSITIONS.get(current, frozenset()):
        raise ValueError(f"invalid portfolio transition: {current} -> {target}")
    if target in {"eligible_for_live", "live"}:
        raise ValueError("live readiness and live states are disabled in phase 5")


def validate_mandate(
    *,
    min_cash_weight: Decimal,
    max_cash_weight: Decimal,
    max_turnover: Decimal,
    max_drawdown: Decimal,
    benchmark_in_universe: bool,
) -> None:
    if not Decimal(0) <= min_cash_weight <= max_cash_weight <= Decimal(1):
        raise ValueError("cash weights must satisfy 0 <= min <= max <= 1")
    if not Decimal(0) <= max_turnover <= Decimal(2):
        raise ValueError("max turnover must be between zero and two")
    if not Decimal(0) <= max_drawdown <= Decimal(1):
        raise ValueError("max drawdown must be between zero and one")
    if benchmark_in_universe:
        raise ValueError("benchmark cannot belong to the investable universe")


@dataclass(frozen=True, slots=True)
class PositionValue:
    instrument_id: str
    quantity: Decimal
    price: Decimal

    @property
    def market_value(self) -> Decimal:
        if self.quantity < 0 or self.price < 0:
            raise ValueError("position quantity and price must be nonnegative")
        return self.quantity * self.price


@dataclass(frozen=True, slots=True)
class NavResult:
    cash_value: Decimal
    positions_value: Decimal
    fees_value: Decimal
    taxes_value: Decimal
    nav: Decimal
    reconciled: bool
    input_sha256: str


def calculate_nav(
    positions: tuple[PositionValue, ...],
    cash: tuple[Decimal, ...],
    fees: tuple[Decimal, ...] = (),
    taxes: tuple[Decimal, ...] = (),
) -> NavResult:
    cash_value = sum(cash, start=Decimal(0))
    positions_value = sum((position.market_value for position in positions), start=Decimal(0))
    fees_value = sum(fees, start=Decimal(0))
    taxes_value = sum(taxes, start=Decimal(0))
    if fees_value < 0 or taxes_value < 0:
        raise ValueError("fees and taxes must be nonnegative")
    nav = cash_value + positions_value - fees_value - taxes_value
    payload = {
        "positions": [(item.instrument_id, item.quantity, item.price) for item in positions],
        "cash": cash,
        "fees": fees,
        "taxes": taxes,
    }
    return NavResult(cash_value, positions_value, fees_value, taxes_value, nav, nav >= 0, canonical_hash(payload))


@dataclass(frozen=True, slots=True)
class RiskLimitInput:
    name: str
    limit_type: str
    maximum: Decimal


@dataclass(frozen=True, slots=True)
class RiskBreachResult:
    name: str
    limit_type: str
    observed: Decimal
    maximum: Decimal
    blocks: bool


def evaluate_risk_limits(
    observations: dict[str, Decimal], limits: tuple[RiskLimitInput, ...]
) -> tuple[RiskBreachResult, ...]:
    breaches: list[RiskBreachResult] = []
    for limit in limits:
        if limit.limit_type not in {"hard", "soft"}:
            raise ValueError(f"invalid risk limit type: {limit.limit_type}")
        if limit.maximum < 0:
            raise ValueError("risk limit cannot be negative")
        observed = observations.get(limit.name)
        if observed is not None and observed > limit.maximum:
            breaches.append(
                RiskBreachResult(limit.name, limit.limit_type, observed, limit.maximum, limit.limit_type == "hard")
            )
    return tuple(breaches)


def stress_portfolio(exposures: dict[str, Decimal], shocks: dict[str, Decimal]) -> Decimal:
    missing = set(shocks) - exposures.keys()
    if missing:
        raise ValueError(f"stress factors lack exposure: {sorted(missing)}")
    return sum((exposures[factor] * shock for factor, shock in shocks.items()), start=Decimal(0))


def top_portfolio_eligible(
    *,
    approved: bool,
    nav_reconciled: bool,
    benchmark_complete: bool,
    backtest_pit_passed: bool,
    theses_healthy: bool,
    critical_breach: bool,
) -> bool:
    return (
        all((approved, nav_reconciled, benchmark_complete, backtest_pit_passed, theses_healthy)) and not critical_breach
    )


def investable_universe(
    instrument_ids: tuple[str, ...], *, restricted: frozenset[str], benchmark_instrument_id: str | None = None
) -> tuple[str, ...]:
    if len(set(instrument_ids)) != len(instrument_ids):
        raise ValueError("mandate universe contains duplicate instruments")
    selected = tuple(item for item in instrument_ids if item not in restricted and item != benchmark_instrument_id)
    if not selected:
        raise ValueError("mandate has no investable instruments after restrictions")
    return selected


@dataclass(frozen=True, slots=True)
class PortfolioRiskMetrics:
    observations: dict[str, Decimal]
    concentration: dict[str, Decimal]
    factor_exposures: dict[str, Decimal]
    liquidity: dict[str, Decimal]
    volatility: Decimal | None
    drawdown: Decimal | None
    input_sha256: str


def calculate_portfolio_risk(
    *,
    position_values: dict[str, Decimal],
    cash_value: Decimal,
    average_daily_values: dict[str, Decimal],
    factor_loadings: dict[str, dict[str, Decimal]],
    portfolio_returns: tuple[Decimal, ...],
    nav_history: tuple[Decimal, ...],
    annualization: int = 252,
) -> PortfolioRiskMetrics:
    if cash_value < 0 or any(value < 0 for value in position_values.values()):
        raise ValueError("position and cash values must be nonnegative")
    nav = cash_value + sum(position_values.values(), start=Decimal(0))
    if nav <= 0:
        raise ValueError("risk metrics require positive NAV")
    weights = {instrument: value / nav for instrument, value in position_values.items()}
    sorted_weights = sorted(weights.values(), reverse=True)
    concentration = {
        "largest_position_weight": sorted_weights[0] if sorted_weights else Decimal(0),
        "top_5_weight": sum(sorted_weights[:5], start=Decimal(0)),
        "hhi": sum((weight * weight for weight in sorted_weights), start=Decimal(0)),
        "cash_weight": cash_value / nav,
    }
    liquidity_days: dict[str, Decimal] = {}
    for instrument, value in position_values.items():
        adv = average_daily_values.get(instrument)
        if adv is None or adv <= 0:
            raise ValueError(f"liquidity is missing for instrument {instrument}")
        liquidity_days[instrument] = value / adv
    factor_names = {factor for values in factor_loadings.values() for factor in values}
    factor_exposures = {
        factor: sum(
            (
                weights.get(instrument, Decimal(0)) * values.get(factor, Decimal(0))
                for instrument, values in factor_loadings.items()
            ),
            start=Decimal(0),
        )
        for factor in sorted(factor_names)
    }
    volatility = None
    if len(portfolio_returns) >= 2:
        mean = sum(portfolio_returns, start=Decimal(0)) / Decimal(len(portfolio_returns))
        variance = sum(((item - mean) ** 2 for item in portfolio_returns), start=Decimal(0)) / Decimal(
            len(portfolio_returns) - 1
        )
        volatility = Decimal(str(math.sqrt(float(variance)) * math.sqrt(annualization)))
    drawdown = None
    if nav_history:
        peak = nav_history[0]
        maximum = Decimal(0)
        for value in nav_history:
            if value <= 0:
                raise ValueError("NAV history must be positive")
            peak = max(peak, value)
            maximum = max(maximum, (peak - value) / peak)
        drawdown = maximum
    observations = {
        **concentration,
        **{f"factor:{name}": abs(value) for name, value in factor_exposures.items()},
        "liquidity_days_max": max(liquidity_days.values(), default=Decimal(0)),
    }
    if volatility is not None:
        observations["volatility"] = volatility
    if drawdown is not None:
        observations["drawdown"] = drawdown
    payload = {
        "position_values": position_values,
        "cash_value": cash_value,
        "average_daily_values": average_daily_values,
        "factor_loadings": factor_loadings,
        "portfolio_returns": portfolio_returns,
        "nav_history": nav_history,
        "annualization": annualization,
    }
    return PortfolioRiskMetrics(
        observations,
        concentration,
        factor_exposures,
        liquidity_days,
        volatility,
        drawdown,
        canonical_hash(payload),
    )
