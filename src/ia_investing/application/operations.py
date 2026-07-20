from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from temporalio.client import Client

from database.models.agents import AuditLog
from database.models.operations import Operation
from ia_investing.contracts.v1 import OperationAcceptedV1, OperationState, OperationStatusV1
from ia_investing.orchestration.queues import TASK_QUEUES, Capability
from workflows import (
    RunAgentInput,
    RunAgentWorkflow,
)


class IdempotencyConflictError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class AgentRunCommand:
    agent_name: str
    input_data: dict[str, Any]
    actor_subject: str

    def payload(self) -> dict[str, Any]:
        return {"agent_name": self.agent_name, "input_data": self.input_data}


@dataclass(frozen=True, slots=True)
class PortfolioOperationCommand:
    operation_type: str
    payload: dict[str, Any]
    actor_subject: str
    workflow_id: str | None = None
    workflow_class: Any = None
    workflow_input: Any = None
    task_queue: Capability = Capability.PORTFOLIO_RISK


def _request_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode()).hexdigest()


class OperationService:
    def __init__(self, session: AsyncSession, temporal_client: Client) -> None:
        self.session = session
        self.temporal_client = temporal_client

    async def submit_agent_run(self, command: AgentRunCommand, idempotency_key: str) -> OperationAcceptedV1:
        operation_type = "agent-run"
        payload = command.payload()
        request_hash = _request_hash(payload)
        existing = (
            await self.session.execute(
                select(Operation).where(
                    Operation.operation_type == operation_type,
                    Operation.idempotency_key == idempotency_key,
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            if existing.request_hash != request_hash:
                raise IdempotencyConflictError("idempotency key was already used with a different request")
            return OperationAcceptedV1(operation_id=existing.id, state=existing.state)

        operation_id = uuid4()
        operation = Operation(
            id=operation_id,
            operation_type=operation_type,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
            state=OperationState.PENDING,
            request_data=payload,
        )
        self.session.add(operation)
        self.session.add(
            AuditLog(
                actor_type="human",
                actor_id=command.actor_subject,
                action="agent_run.submit",
                entity_type="operation",
                entity_id=operation_id,
                correlation_id=operation_id,
                details={
                    "agent_name": command.agent_name,
                    "idempotency_key_hash": hashlib.sha256(idempotency_key.encode()).hexdigest(),
                },
            )
        )
        await self.session.commit()

        try:
            await self.temporal_client.start_workflow(
                RunAgentWorkflow.run,
                RunAgentInput(
                    operation_id=str(operation_id),
                    agent_name=command.agent_name,
                    input_data=command.input_data,
                ),
                id=f"operation-{operation_id}",
                task_queue=TASK_QUEUES[Capability.RESEARCH_AGENTS],
            )
        except Exception:
            operation.state = OperationState.FAILED
            operation.error_code = "workflow_start_failed"
            operation.error_detail = "Workflow could not be started. Retry with the same idempotency key."
            await self.session.commit()
            raise
        return OperationAcceptedV1(operation_id=operation_id)

    async def submit_portfolio_operation(
        self, command: PortfolioOperationCommand, idempotency_key: str, actor_subject: str
    ) -> OperationAcceptedV1:
        request_hash = _request_hash(command.payload)
        existing = (
            await self.session.execute(
                select(Operation).where(
                    Operation.operation_type == command.operation_type,
                    Operation.idempotency_key == idempotency_key,
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            if existing.request_hash != request_hash:
                raise IdempotencyConflictError("idempotency key was already used with a different request")
            return OperationAcceptedV1(operation_id=existing.id, state=existing.state)

        operation_id = uuid4()
        operation = Operation(
            id=operation_id,
            operation_type=command.operation_type,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
            state=OperationState.PENDING,
            request_data=command.payload,
        )
        self.session.add(operation)
        self.session.add(
            AuditLog(
                actor_type="human",
                actor_id=actor_subject,
                action=f"{command.operation_type}.submit",
                entity_type="operation",
                entity_id=operation_id,
                correlation_id=operation_id,
                details={
                    "idempotency_key_hash": hashlib.sha256(idempotency_key.encode()).hexdigest(),
                },
            )
        )
        await self.session.commit()

        if command.workflow_class is not None and command.workflow_id is not None:
            try:
                await self.temporal_client.start_workflow(
                    command.workflow_class.run,
                    command.workflow_input,
                    id=command.workflow_id,
                    task_queue=TASK_QUEUES[command.task_queue],
                )
            except Exception:
                operation.state = OperationState.FAILED
                operation.error_code = "workflow_start_failed"
                operation.error_detail = "Workflow could not be started. Retry with the same idempotency key."
                await self.session.commit()
                raise
        return OperationAcceptedV1(operation_id=operation_id)

    async def get(self, operation_id: UUID) -> OperationStatusV1 | None:
        operation = await self.session.get(Operation, operation_id)
        if operation is None:
            return None
        return OperationStatusV1(
            operation_id=operation.id,
            state=operation.state,
            created_at=operation.created_at,
            updated_at=operation.updated_at,
            result_url=operation.result_url,
            error_code=operation.error_code,
            error_detail=operation.error_detail,
            metadata={},
        )
