from __future__ import annotations

from typing import Any

from ia_investing.domain.base_machine import BaseMachineModel, BaseStateMachine

THESIS_STATES = [
    "draft",
    "under_review",
    "approved",
    "active",
    "monitoring",
    "completed",
    "archived",
]

THESIS_TRANSITIONS: list[dict[str, Any]] = [
    {"trigger": "submit", "source": "draft", "dest": "under_review"},
    {"trigger": "approve", "source": "under_review", "dest": "approved", "conditions": "_can_approve"},
    {"trigger": "reject", "source": "under_review", "dest": "draft"},
    {"trigger": "activate", "source": "approved", "dest": "active"},
    {"trigger": "escalate", "source": "active", "dest": "monitoring"},
    {"trigger": "complete", "source": "active", "dest": "completed"},
    {"trigger": "complete", "source": "monitoring", "dest": "completed"},
    {"trigger": "archive", "source": "completed", "dest": "archived"},
]


class ThesisMachineModel(BaseMachineModel):
    has_required_evidence: bool = False
    monitoring_scheduled: bool = False

    def _can_approve(self, **kwargs: Any) -> bool:
        return self.has_required_evidence

    def on_enter_active(self, **kwargs: Any) -> None:
        self.monitoring_scheduled = True


def create_thesis_machine(model: ThesisMachineModel | None = None) -> BaseStateMachine:
    if model is None:
        model = ThesisMachineModel(state="draft")
    return BaseStateMachine(
        model=model,
        states=THESIS_STATES,
        transitions=THESIS_TRANSITIONS,
        initial="draft",
    )
