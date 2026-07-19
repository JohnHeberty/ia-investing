from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from temporalio import workflow


@dataclass(frozen=True, slots=True)
class ApprovalGateInput:
    run_id: str
    agent_version_id: str
    input_sha256: str
    timeout_seconds: int


@dataclass(frozen=True, slots=True)
class ApprovalGateResult:
    run_id: str
    agent_version_id: str
    input_sha256: str
    decision: str


@workflow.defn
class ApprovalGateWorkflow:
    def __init__(self) -> None:
        self._decision: str | None = None

    @workflow.run
    async def run(self, command: ApprovalGateInput) -> ApprovalGateResult:
        if command.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        try:
            await workflow.wait_condition(
                lambda: self._decision is not None,
                timeout=timedelta(seconds=command.timeout_seconds),
            )
        except TimeoutError:
            self._decision = "expired"
        return ApprovalGateResult(
            run_id=command.run_id,
            agent_version_id=command.agent_version_id,
            input_sha256=command.input_sha256,
            decision=self._decision or "expired",
        )

    @workflow.signal
    async def decide(self, decision: str) -> None:
        if decision not in {"approved", "rejected", "cancelled"}:
            raise ValueError("invalid approval decision")
        if self._decision is None:
            self._decision = decision

    @workflow.query
    def state(self) -> str:
        return self._decision or "awaiting_approval"
