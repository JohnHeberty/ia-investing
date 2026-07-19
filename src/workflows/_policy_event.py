from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from temporalio import workflow


@dataclass(frozen=True, slots=True)
class PolicyEventInput:
    policy_object_id: str
    version: int
    input_sha256: str
    material: bool
    review_timeout_seconds: int = 86_400


@dataclass(frozen=True, slots=True)
class PolicyEventResult:
    policy_object_id: str
    version: int
    decision: str
    thesis_changed: bool = False


@workflow.defn
class PolicyEventWorkflow:
    """Durable material-impact gate; it never mutates a thesis or portfolio."""

    def __init__(self) -> None:
        self._decision: str | None = None

    @workflow.run
    async def run(self, command: PolicyEventInput) -> PolicyEventResult:
        if command.version <= 0 or command.review_timeout_seconds <= 0:
            raise ValueError("version and review timeout must be positive")
        if command.material:
            try:
                await workflow.wait_condition(
                    lambda: self._decision is not None,
                    timeout=timedelta(seconds=command.review_timeout_seconds),
                )
            except TimeoutError:
                self._decision = "expired"
        else:
            self._decision = "not_required"
        return PolicyEventResult(command.policy_object_id, command.version, self._decision or "expired")

    @workflow.signal
    async def review(self, decision: str) -> None:
        if decision not in {"approved", "rejected", "cancelled"}:
            raise ValueError("invalid policy review decision")
        if self._decision is None:
            self._decision = decision

    @workflow.query
    def state(self) -> str:
        return self._decision or "awaiting_review"
