from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from workflows._schedule_run import complete_schedule_run, fail_schedule_run, start_schedule_run


@dataclass(frozen=True, slots=True)
class PaperRebalanceInput:
    portfolio_id: str
    portfolio_version_id: str
    input_sha256: str
    approval_timeout_seconds: int
    schedule_id: str = ""


@dataclass(frozen=True, slots=True)
class PaperRebalanceResult:
    portfolio_id: str
    portfolio_version_id: str
    state: str
    execution_environment: str = "paper"


@workflow.defn
class PaperRebalanceWorkflow:
    """Durable approval boundary that can only release work to the paper simulator."""

    def __init__(self) -> None:
        self._state = "awaiting_approval"

    @workflow.run
    async def run(self, command: PaperRebalanceInput) -> PaperRebalanceResult:
        await start_schedule_run(command.schedule_id)
        try:
            if command.approval_timeout_seconds <= 0:
                raise ValueError("approval timeout must be positive")
            try:
                await workflow.wait_condition(
                    lambda: self._state != "awaiting_approval",
                    timeout=timedelta(seconds=command.approval_timeout_seconds),
                )
            except TimeoutError:
                self._state = "expired"
        except Exception as exc:
            await fail_schedule_run(command.schedule_id, exc)
            raise

        status = "completed" if self._state == "approved_for_paper" else "failed"
        await complete_schedule_run(
            command.schedule_id,
            {"portfolio_id": command.portfolio_id, "state": self._state},
            status=status,
            error_message=None if status == "completed" else f"rebalance ended in state {self._state}",
        )

        return PaperRebalanceResult(command.portfolio_id, command.portfolio_version_id, self._state)

    @workflow.signal
    async def decide(self, decision: str) -> None:
        if decision not in {"approved_for_paper", "rejected", "cancelled"}:
            raise ValueError("invalid paper rebalance decision")
        if self._state == "awaiting_approval":
            self._state = decision

    @workflow.signal
    async def kill(self) -> None:
        if self._state in {"awaiting_approval", "approved_for_paper"}:
            self._state = "killed"

    @workflow.query
    def state(self) -> str:
        return self._state
