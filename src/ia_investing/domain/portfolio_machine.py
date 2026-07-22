from __future__ import annotations

from typing import Any

from ia_investing.domain.base_machine import BaseMachineModel, BaseStateMachine

PORTFOLIO_STATES = [
    "allocating",
    "rebalancing",
    "monitoring",
    "rebalancing_pending",
    "compliance_hold",
    "liquidating",
    "closed",
]

PORTFOLIO_TRANSITIONS: list[dict[str, Any]] = [
    {"trigger": "rebalance", "source": "allocating", "dest": "rebalancing", "conditions": "_nav_positive"},
    {"trigger": "rebalance", "source": "monitoring", "dest": "rebalancing", "conditions": "_nav_positive"},
    {"trigger": "approve_rebalance", "source": "rebalancing", "dest": "monitoring"},
    {"trigger": "hold", "source": "monitoring", "dest": "compliance_hold"},
    {"trigger": "hold", "source": "rebalancing", "dest": "compliance_hold"},
    {"trigger": "hold", "source": "rebalancing_pending", "dest": "compliance_hold"},
    {"trigger": "release", "source": "compliance_hold", "dest": "monitoring", "conditions": "_compliance_cleared"},
    {
        "trigger": "release",
        "source": "compliance_hold",
        "dest": "rebalancing_pending",
        "conditions": "_compliance_cleared",
    },
    {"trigger": "release", "source": "rebalancing_pending", "dest": "rebalancing"},
    {"trigger": "liquidate", "source": "monitoring", "dest": "liquidating"},
    {"trigger": "liquidate", "source": "compliance_hold", "dest": "liquidating"},
    {"trigger": "close", "source": "liquidating", "dest": "closed"},
]


class PortfolioMachineModel(BaseMachineModel):
    nav: float = 0.0
    compliance_passed: bool = False
    orders_frozen: bool = False

    def _nav_positive(self, **kwargs: Any) -> bool:
        return self.nav > 0

    def _compliance_cleared(self, **kwargs: Any) -> bool:
        return self.compliance_passed

    def on_enter_compliance_hold(self, **kwargs: Any) -> None:
        self.orders_frozen = True

    def on_exit_compliance_hold(self, **kwargs: Any) -> None:
        self.orders_frozen = False


def create_portfolio_machine(model: PortfolioMachineModel | None = None) -> BaseStateMachine:
    if model is None:
        model = PortfolioMachineModel(state="allocating")
    return BaseStateMachine(
        model=model,
        states=PORTFOLIO_STATES,
        transitions=PORTFOLIO_TRANSITIONS,
        initial="allocating",
    )
