"""Periodic recovery workflow for candidate-intelligence outbox events."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from temporalio import workflow
from temporalio.common import RetryPolicy

_DISPATCH_RETRY = RetryPolicy(
    initial_interval=timedelta(seconds=5),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(minutes=2),
    maximum_attempts=5,
)


@workflow.defn(name="CandidateOutboxDispatchWorkflow")
class CandidateOutboxDispatchWorkflow:
    @workflow.run
    async def run(self, command: dict[str, Any] | None = None) -> dict[str, int]:
        return await workflow.execute_activity(  # type: ignore[no-any-return]
            "dispatch_candidate_intelligence_events",
            command or {"batch_size": 50},
            start_to_close_timeout=timedelta(minutes=3),
            retry_policy=_DISPATCH_RETRY,
        )
