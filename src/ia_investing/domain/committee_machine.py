from __future__ import annotations

from typing import Any

from ia_investing.domain.base_machine import BaseMachineModel, BaseStateMachine

COMMITTEE_STATES = [
    "scheduled",
    "in_session",
    "voting",
    "deliberating",
    "decided",
    "published",
    "archived",
]

COMMITTEE_TRANSITIONS: list[dict[str, Any]] = [
    {"trigger": "convene", "source": "scheduled", "dest": "in_session"},
    {"trigger": "start_voting", "source": "in_session", "dest": "voting", "conditions": "_quorum_met"},
    {"trigger": "deliberate", "source": "voting", "dest": "deliberating"},
    {"trigger": "make_decision", "source": "deliberating", "dest": "decided", "conditions": "_majority_reached"},
    {"trigger": "publish", "source": "decided", "dest": "published"},
    {"trigger": "archive", "source": "published", "dest": "archived"},
]


class CommitteeMachineModel(BaseMachineModel):
    total_members: int = 0
    present_members: int = 0
    votes_in_favor: int = 0
    votes_against: int = 0
    members_notified: bool = False

    def _quorum_met(self, **kwargs: Any) -> bool:
        if self.total_members == 0:
            return False
        return self.present_members >= self.total_members // 2 + 1

    def _majority_reached(self, **kwargs: Any) -> bool:
        total_votes = self.votes_in_favor + self.votes_against
        if total_votes == 0:
            return False
        return self.votes_in_favor > total_votes / 2

    def on_enter_published(self, **kwargs: Any) -> None:
        self.members_notified = True


def create_committee_machine(model: CommitteeMachineModel | None = None) -> BaseStateMachine:
    if model is None:
        model = CommitteeMachineModel(state="scheduled")
    return BaseStateMachine(
        model=model,
        states=COMMITTEE_STATES,
        transitions=COMMITTEE_TRANSITIONS,
        initial="scheduled",
    )
