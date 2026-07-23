from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, getcontext

getcontext().prec = 28


@dataclass(frozen=True, slots=True)
class DCFInput:
    free_cash_flows: tuple[Decimal, ...]
    discount_rate: Decimal
    terminal_growth: Decimal
    net_debt: Decimal
    shares_outstanding: Decimal


@dataclass(frozen=True, slots=True)
class DCFResult:
    enterprise_value: Decimal
    equity_value: Decimal
    value_per_share: Decimal


def discounted_cash_flow(inputs: DCFInput) -> DCFResult:
    if not inputs.free_cash_flows:
        raise ValueError("at least one free cash flow is required")
    if inputs.discount_rate <= inputs.terminal_growth:
        raise ValueError("discount rate must exceed terminal growth")
    if inputs.shares_outstanding <= 0:
        raise ValueError("shares outstanding must be positive")
    one = Decimal(1)
    present_value = sum(
        cash_flow / ((one + inputs.discount_rate) ** year)
        for year, cash_flow in enumerate(inputs.free_cash_flows, start=1)
    )
    last_cash_flow = inputs.free_cash_flows[-1]
    terminal_value = last_cash_flow * (one + inputs.terminal_growth) / (inputs.discount_rate - inputs.terminal_growth)
    present_terminal = terminal_value / ((one + inputs.discount_rate) ** len(inputs.free_cash_flows))
    enterprise = present_value + present_terminal
    equity = enterprise - inputs.net_debt
    return DCFResult(enterprise, equity, equity / inputs.shares_outstanding)


def weighted_scenarios(scenarios: dict[str, DCFResult], probabilities: dict[str, Decimal]) -> DCFResult:
    if set(scenarios) != {"bear", "base", "bull"} or set(probabilities) != set(scenarios):
        raise ValueError("bear, base and bull scenarios are required")
    if sum(probabilities.values()) != Decimal(1):
        raise ValueError("scenario probabilities must sum to one")
    return DCFResult(
        enterprise_value=sum(scenarios[name].enterprise_value * probabilities[name] for name in scenarios),  # type: ignore[arg-type]
        equity_value=sum(scenarios[name].equity_value * probabilities[name] for name in scenarios),  # type: ignore[arg-type]
        value_per_share=sum(scenarios[name].value_per_share * probabilities[name] for name in scenarios),  # type: ignore[arg-type]
    )


def relative_valuation(
    metric: Decimal,
    selected_multiple: Decimal,
    net_debt: Decimal,
    shares_outstanding: Decimal,
) -> DCFResult:
    if metric < 0 or selected_multiple <= 0 or shares_outstanding <= 0:
        raise ValueError("relative valuation inputs are outside the supported domain")
    enterprise = metric * selected_multiple
    equity = enterprise - net_debt
    return DCFResult(enterprise, equity, equity / shares_outstanding)


def reverse_dcf_growth(
    market_enterprise_value: Decimal,
    starting_cash_flow: Decimal,
    discount_rate: Decimal,
    years: int = 5,
) -> Decimal:
    if market_enterprise_value <= 0 or starting_cash_flow <= 0 or years < 1:
        raise ValueError("reverse DCF inputs must be positive")
    low, high = Decimal("-0.50"), discount_rate - Decimal("0.000001")
    for _ in range(200):
        growth = (low + high) / 2
        cash_flows = tuple(starting_cash_flow * ((Decimal(1) + growth) ** year) for year in range(1, years + 1))
        value = discounted_cash_flow(
            DCFInput(cash_flows, discount_rate, growth, Decimal(0), Decimal(1))
        ).enterprise_value
        if value < market_enterprise_value:
            low = growth
        else:
            high = growth
    return (low + high) / 2
