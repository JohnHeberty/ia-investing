from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from ia_investing.orchestration.policies import EXTERNAL_IO_RETRY_POLICY
    from workflows._schedule_run import complete_schedule_run, fail_schedule_run, start_schedule_run


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


@dataclass(frozen=True, slots=True)
class PolicyCollectionInput:
    authority: str
    schedule_id: str = ""
    since: str | None = None


@dataclass(frozen=True, slots=True)
class PolicyCollectionResult:
    authority: str
    fetched: int = 0
    ingested: int = 0
    status: str = "completed"


@workflow.defn(name="PolicyCollectionWorkflow")
class PolicyCollectionWorkflow:
    @workflow.run
    async def run(self, command: PolicyCollectionInput) -> PolicyCollectionResult:
        await start_schedule_run(command.schedule_id)
        try:
            result = await self._collect(command)
        except Exception as exc:
            await fail_schedule_run(command.schedule_id, exc)
            raise
        await complete_schedule_run(command.schedule_id, result.__dict__)
        return result

    async def _collect(self, command: PolicyCollectionInput) -> PolicyCollectionResult:
        fetched: dict[str, Any] = await workflow.execute_activity(
            "fetch_policy_objects",
            {"authority": command.authority, "since": command.since},
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=EXTERNAL_IO_RETRY_POLICY,
        )

        ingested: dict[str, Any] = await workflow.execute_activity(
            "ingest_policy_objects",
            {"authority": command.authority, "records": fetched.get("records", [])},
            start_to_close_timeout=timedelta(minutes=10),
            retry_policy=EXTERNAL_IO_RETRY_POLICY,
        )

        return PolicyCollectionResult(
            authority=command.authority,
            fetched=fetched.get("count", 0),
            ingested=ingested.get("ingested", 0),
        )
