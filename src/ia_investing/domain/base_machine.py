from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from threading import Lock
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field
from transitions import Machine, MachineError


class InvalidTransitionError(ValueError):
    def __init__(self, message: str = "") -> None:
        super().__init__(message)


class StateHistoryEntry(BaseModel):
    from_state: str
    to_state: str
    timestamp: datetime
    reason: str | None = None


class BaseMachineModel(BaseModel):
    model_config = ConfigDict(extra="allow", arbitrary_types_allowed=True)

    id: UUID = Field(default_factory=uuid4)
    state: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    state_history: list[StateHistoryEntry] = Field(default_factory=list)

    def _save_prev(self, **kwargs: Any) -> None:
        object.__setattr__(self, "_prev_state", self.state)

    def _record_transition(self, **kwargs: Any) -> None:
        prev: str = object.__getattribute__(self, "_prev_state")
        curr = self.state
        reason = kwargs.get("reason")
        self.state_history.append(
            StateHistoryEntry(
                from_state=prev,
                to_state=curr,
                timestamp=datetime.now(UTC),
                reason=reason,
            )
        )


def _add_tracking(transitions: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for t in transitions:
        t = dict(t)
        before = t.pop("before", None)
        if isinstance(before, str):
            before = [before]
        before = before or []
        t["before"] = ["_save_prev", *before]

        after = t.pop("after", None)
        if isinstance(after, str):
            after = [after]
        after = after or []
        t["after"] = [*after, "_record_transition"]
        result.append(t)
    return result


class BaseStateMachine:
    def __init__(
        self,
        model: BaseMachineModel,
        states: Sequence[str | dict[str, Any]],
        transitions: Sequence[dict[str, Any]],
        initial: str,
    ) -> None:
        self._model = model
        self._lock = Lock()
        self._transitions_meta = list(transitions)

        persisted_state = model.state

        enhanced = _add_tracking(transitions)
        Machine(
            model=model,
            states=states,
            transitions=enhanced,
            initial=initial,
            auto_transitions=False,
        )

        if model.state != persisted_state:
            model.state = persisted_state

    @property
    def model(self) -> BaseMachineModel:
        return self._model

    @property
    def state(self) -> str:
        return self._model.state

    def get_allowed_transitions(self) -> list[dict[str, str]]:
        with self._lock:
            current = self._model.state
            return [
                {"trigger": t["trigger"], "dest": t["dest"]}
                for t in self._transitions_meta
                if t["source"] == current or t["source"] == "*"
            ]

    def can_transition_to(self, target: str) -> bool:
        with self._lock:
            current = self._model.state
            return any(
                t["dest"] == target for t in self._transitions_meta if t["source"] == current or t["source"] == "*"
            )

    def get_state_history(self) -> list[tuple[str, str, datetime, str | None]]:
        return [(e.from_state, e.to_state, e.timestamp, e.reason) for e in self._model.state_history]

    def apply(self, trigger: str, *, reason: str | None = None, **kwargs: Any) -> str:
        with self._lock:
            trigger_fn = getattr(self._model, trigger, None)
            if trigger_fn is None:
                raise InvalidTransitionError(f"Trigger '{trigger}' not available from state '{self._model.state}'")
            try:
                result = trigger_fn(reason=reason, **kwargs)
            except MachineError as exc:
                raise InvalidTransitionError(str(exc)) from exc
            if result is False:
                raise InvalidTransitionError(
                    f"Trigger '{trigger}' rejected: conditions not met from state '{self._model.state}'"
                )
            return self._model.state

    def to_dict(self) -> dict[str, Any]:
        return self._model.model_dump()
