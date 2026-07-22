from __future__ import annotations

from typing import Any

from ia_investing.domain.base_machine import BaseMachineModel, BaseStateMachine

RISK_STATES = [
    "normal",
    "monitoring",
    "breached",
    "escalated",
    "resolved",
]

RISK_TRANSITIONS: list[dict[str, Any]] = [
    {"trigger": "detect_anomaly", "source": "normal", "dest": "monitoring"},
    {"trigger": "breach", "source": "monitoring", "dest": "breached", "conditions": "_threshold_exceeded"},
    {"trigger": "investigate", "source": "breached", "dest": "escalated"},
    {"trigger": "mitigate", "source": "escalated", "dest": "monitoring"},
    {"trigger": "mitigate", "source": "breached", "dest": "monitoring"},
    {"trigger": "resolve", "source": "monitoring", "dest": "normal"},
    {"trigger": "resolve", "source": "escalated", "dest": "resolved"},
    {"trigger": "resolve", "source": "breached", "dest": "resolved"},
]


class RiskMachineModel(BaseMachineModel):
    threshold_value: float = 0.0
    current_value: float = 0.0
    risk_team_alerted: bool = False
    auto_escalated: bool = False

    def _threshold_exceeded(self, **kwargs: Any) -> bool:
        return self.current_value > self.threshold_value

    def on_enter_breached(self, **kwargs: Any) -> None:
        self.risk_team_alerted = True

    def on_enter_escalated(self, **kwargs: Any) -> None:
        self.auto_escalated = True


def create_risk_machine(model: RiskMachineModel | None = None) -> BaseStateMachine:
    if model is None:
        model = RiskMachineModel(state="normal")
    return BaseStateMachine(
        model=model,
        states=RISK_STATES,
        transitions=RISK_TRANSITIONS,
        initial="normal",
    )
