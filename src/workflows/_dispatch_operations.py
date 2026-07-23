"""Periodic recovery workflow for the transactional operation outbox."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from ia_investing.orchestration.policies import EXTERNAL_IO_RETRY_POLICY


@workflow.defn(name="DispatchOperationsWorkflow")
class DispatchOperationsWorkflow:
    @workflow.run
    async def run(self, command: dict[str, Any] | None = None) -> dict[str, int]:
        return await workflow.execute_activity(  # type: ignore[no-any-return]
            "dispatch_pending_operations",
            command or {"batch_size": 50},
            start_to_close_timeout=timedelta(minutes=2),
            retry_policy=EXTERNAL_IO_RETRY_POLICY,
        )
