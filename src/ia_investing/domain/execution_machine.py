from __future__ import annotations

from typing import Any

from ia_investing.domain.base_machine import BaseMachineModel, BaseStateMachine

EXECUTION_STATES = [
    "pending",
    "validated",
    "queued",
    "dispatched",
    "confirmed",
    "failed",
    "settled",
]

EXECUTION_TRANSITIONS: list[dict[str, Any]] = [
    {"trigger": "run_validation", "source": "pending", "dest": "validated"},
    {"trigger": "queue", "source": "validated", "dest": "queued"},
    {"trigger": "dispatch", "source": "queued", "dest": "dispatched", "conditions": "_sufficient_balance"},
    {"trigger": "confirm", "source": "dispatched", "dest": "confirmed"},
    {"trigger": "fail", "source": "dispatched", "dest": "failed"},
    {"trigger": "fail", "source": "queued", "dest": "failed"},
    {"trigger": "fail", "source": "validated", "dest": "failed"},
    {"trigger": "fail", "source": "confirmed", "dest": "failed"},
    {"trigger": "settle", "source": "confirmed", "dest": "settled"},
    {"trigger": "retry", "source": "failed", "dest": "pending"},
]


class ExecutionMachineModel(BaseMachineModel):
    available_balance: float = 0.0
    required_amount: float = 0.0
    alert_triggered: bool = False

    def _sufficient_balance(self, **kwargs: Any) -> bool:
        return self.available_balance >= self.required_amount

    def on_enter_failed(self, **kwargs: Any) -> None:
        self.alert_triggered = True


def create_execution_machine(model: ExecutionMachineModel | None = None) -> BaseStateMachine:
    if model is None:
        model = ExecutionMachineModel(state="pending")
    return BaseStateMachine(
        model=model,
        states=EXECUTION_STATES,
        transitions=EXECUTION_TRANSITIONS,
        initial="pending",
    )
