from __future__ import annotations

import asyncio
from uuid import uuid4

from temporalio.client import Client
from temporalio.worker import Replayer, Worker

from ia_investing.settings import get_settings
from workflows import ApprovalGateInput, ApprovalGateWorkflow


async def verify() -> None:
    settings = get_settings()
    client = await Client.connect(settings.temporal.address, namespace=settings.temporal.namespace)
    task_queue = f"verify-approval-{uuid4()}"
    workflow_id = f"verify-approval-{uuid4()}"
    command = ApprovalGateInput(
        run_id=str(uuid4()),
        agent_version_id=str(uuid4()),
        input_sha256="a" * 64,
        timeout_seconds=30,
    )
    async with Worker(client, task_queue=task_queue, workflows=[ApprovalGateWorkflow]):
        handle = await client.start_workflow(
            ApprovalGateWorkflow.run,
            command,
            id=workflow_id,
            task_queue=task_queue,
        )
        assert await handle.query(ApprovalGateWorkflow.state) == "awaiting_approval"
        await handle.signal(ApprovalGateWorkflow.decide, "approved")
        result = await handle.result()
        assert result.decision == "approved"
        assert result.agent_version_id == command.agent_version_id
        assert result.input_sha256 == command.input_sha256
        history = await handle.fetch_history()
        cancelled = await client.start_workflow(
            ApprovalGateWorkflow.run,
            ApprovalGateInput(str(uuid4()), str(uuid4()), "b" * 64, 30),
            id=f"verify-approval-cancel-{uuid4()}",
            task_queue=task_queue,
        )
        await cancelled.signal(ApprovalGateWorkflow.decide, "cancelled")
        assert (await cancelled.result()).decision == "cancelled"
        expired = await client.start_workflow(
            ApprovalGateWorkflow.run,
            ApprovalGateInput(str(uuid4()), str(uuid4()), "c" * 64, 1),
            id=f"verify-approval-expiry-{uuid4()}",
            task_queue=task_queue,
        )
        assert (await expired.result()).decision == "expired"
    replay = await Replayer(workflows=[ApprovalGateWorkflow]).replay_workflow(history)
    assert replay.replay_failure is None
    print(
        "temporal-approval-ok decision=approved version_pinned=true input_pinned=true",
        "cancel=true expiry=true replay=true",
    )


if __name__ == "__main__":
    asyncio.run(verify())
