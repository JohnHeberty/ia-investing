"""Dispatch transactional command outbox rows to Temporal workflows."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from temporalio import activity
from temporalio.client import Client
from temporalio.exceptions import ApplicationError, WorkflowAlreadyStartedError

from database.models.operations import Operation, OperationDispatchOutbox
from ia_investing.platform.database import DatabaseRuntime
from ia_investing.settings import get_settings
from workflows._run_agent import RunAgentInput, RunAgentWorkflow

_MAX_ATTEMPTS = 10


def _runtime() -> DatabaseRuntime:
    return DatabaseRuntime.create(get_settings().database.url)


def _retry_delay(attempts: int) -> timedelta:
    return timedelta(minutes=min(2 ** max(0, attempts - 1), 60))


@activity.defn(name="dispatch_pending_operations")
async def dispatch_pending_operations(raw_input: dict[str, Any] | None = None) -> dict[str, int]:
    raw_input = raw_input or {}
    batch_size = int(raw_input.get("batch_size", 50))
    if batch_size < 1 or batch_size > 200:
        raise ApplicationError(
            "batch_size must be between 1 and 200",
            type="DataValidationError",
            non_retryable=True,
        )

    settings = get_settings()
    client = await Client.connect(settings.temporal.address, namespace=settings.temporal.namespace)
    runtime = _runtime()
    dispatched = 0
    retried = 0
    failed = 0
    now = datetime.now(UTC)
    try:
        async with runtime.session() as session:
            rows = (
                (
                    await session.execute(
                        select(OperationDispatchOutbox)
                        .where(
                            OperationDispatchOutbox.state == "pending",
                            OperationDispatchOutbox.next_attempt_at <= now,
                        )
                        .order_by(OperationDispatchOutbox.created_at, OperationDispatchOutbox.id)
                        .with_for_update(skip_locked=True)
                        .limit(batch_size)
                    )
                )
                .scalars()
                .all()
            )

            for outbox in rows:
                operation = await session.get(Operation, outbox.operation_id)
                if operation is None or operation.organization_id != outbox.organization_id:
                    outbox.state = "failed"  # type: ignore[assignment]
                    outbox.last_error = "operation_missing_or_tenant_mismatch"  # type: ignore[assignment]
                    failed += 1
                    continue
                if operation.state in {"succeeded", "failed", "cancelled"}:
                    outbox.state = "dispatched"  # type: ignore[assignment]
                    outbox.dispatched_at = now  # type: ignore[assignment]
                    dispatched += 1
                    continue
                if outbox.topic != "agent-run" or operation.operation_type != "agent-run":
                    outbox.state = "failed"  # type: ignore[assignment]
                    outbox.last_error = "unsupported_operation_topic"  # type: ignore[assignment]
                    operation.state = "failed"  # type: ignore[assignment]
                    operation.error_code = "unsupported_operation_topic"  # type: ignore[assignment]
                    operation.error_detail = "No dispatcher is registered for this operation topic"  # type: ignore[assignment]
                    failed += 1
                    continue

                payload: dict[str, Any] = operation.request_data or {}  # type: ignore[assignment]
                try:
                    command = RunAgentInput(
                        operation_id=str(operation.id),
                        organization_id=str(operation.organization_id),
                        capability=str(payload["capability"]),
                        case_id=str(payload["case_id"]) if payload.get("case_id") else None,
                        input_payload=dict(payload["input_payload"]),
                        data_as_of=str(payload["data_as_of"]),
                        knowledge_cutoff=str(payload["knowledge_cutoff"]),
                        requested_by=str(payload["requested_by"]),
                        idempotency_key=operation.idempotency_key,  # type: ignore[arg-type]
                    )
                    await client.start_workflow(
                        RunAgentWorkflow.run,
                        command,
                        id=f"operation-{operation.id}",
                        task_queue="research-agents",
                    )
                except WorkflowAlreadyStartedError:
                    pass
                except (KeyError, TypeError, ValueError) as exc:
                    outbox.state = "failed"  # type: ignore[assignment]
                    outbox.last_error = f"invalid_operation_payload:{type(exc).__name__}"  # type: ignore[assignment]
                    operation.state = "failed"  # type: ignore[assignment]
                    operation.error_code = "invalid_operation_payload"  # type: ignore[assignment]
                    operation.error_detail = "The durable operation payload failed validation"  # type: ignore[assignment]
                    failed += 1
                    continue
                except Exception as exc:
                    outbox.attempts += 1  # type: ignore[assignment]
                    outbox.last_error = type(exc).__name__[:200]  # type: ignore[assignment]
                    if outbox.attempts >= _MAX_ATTEMPTS:
                        outbox.state = "failed"  # type: ignore[assignment]
                        operation.state = "failed"  # type: ignore[assignment]
                        operation.error_code = "workflow_dispatch_exhausted"  # type: ignore[assignment]
                        operation.error_detail = "Temporal dispatch retries were exhausted"  # type: ignore[assignment]
                        failed += 1
                    else:
                        outbox.next_attempt_at = now + _retry_delay(outbox.attempts)  # type: ignore[arg-type]
                        retried += 1
                    continue

                outbox.state = "dispatched"  # type: ignore[assignment]
                outbox.dispatched_at = now  # type: ignore[assignment]
                outbox.last_error = None  # type: ignore[assignment]
                dispatched += 1

            await session.commit()
    finally:
        await runtime.dispose()

    return {"dispatched": dispatched, "retried": retried, "failed": failed}


OPERATION_DISPATCH_ACTIVITIES = (dispatch_pending_operations,)
