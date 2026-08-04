"""Temporal activities for the governed, versioned agent runtime.

This module replaces the phase-one `research_mock` execution path. It creates a
pinned run, persists tenant and point-in-time context, executes the configured
provider, validates the structured output, and returns only a safe public
summary.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator
from temporalio import activity
from temporalio.exceptions import ApplicationError

from database.models.operations import Operation
from ia_investing.ai.execution import AgentExecutionService
from ia_investing.ai.gateway import GatewayProvider, create_gateway_provider
from ia_investing.application.agent_runtime import AgentRuntimeService
from ia_investing.application.calibration_engine import CalibrationEngine
from ia_investing.platform.database import DatabaseRuntime
from ia_investing.settings import get_settings

from . import _telemetry

logger = logging.getLogger(__name__)


class ExecuteAgentCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation_id: UUID
    organization_id: UUID
    capability: str = Field(min_length=1, max_length=100)
    case_id: UUID | None = None
    input_payload: dict[str, Any]
    data_as_of: datetime
    knowledge_cutoff: datetime
    requested_by: str = Field(min_length=1, max_length=255)
    idempotency_key: str = Field(min_length=8, max_length=255)
    workflow_id: str = Field(min_length=1, max_length=255)

    @field_validator("data_as_of", "knowledge_cutoff")
    @classmethod
    def timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("agent runtime timestamps must be timezone-aware")
        return value


def _provider() -> GatewayProvider:
    settings = get_settings()
    if settings.ai.provider in ("gateway", "litellm"):
        gw = settings.ai.gateway
        return create_gateway_provider(
            provider=gw.provider,
            api_key=gw.api_key.get_secret_value(),
            default_model=gw.model,
            base_url=gw.base_url,
            timeout=gw.timeout,
            max_retries=gw.max_retries,
            rpm=gw.rpm,
            tpm=gw.tpm,
        )
    raise ApplicationError(
        f"AI provider {settings.ai.provider!r} is not supported — set AI__PROVIDER to 'gateway' or 'litellm'",
        type="ConfigurationError",
        non_retryable=True,
    )


def _runtime() -> DatabaseRuntime:
    return DatabaseRuntime.create(get_settings().database.url)


def _calibration_engine() -> CalibrationEngine:
    return CalibrationEngine()


@activity.defn(name="create_and_execute_agent_run")
async def create_and_execute_agent_run(raw_command: dict[str, Any]) -> dict[str, Any]:
    with _telemetry.activity_span("agent.create_and_execute") as correlation_id:
        logger.info(
            "activity agent.create_and_execute started capability=%s org_id=%s correlation_id=%s",
            raw_command.get("capability"),
            raw_command.get("organization_id"),
            correlation_id,
        )
        try:
            command = ExecuteAgentCommand.model_validate(raw_command)
        except Exception as exc:
            raise ApplicationError(
                "invalid governed agent command",
                type="DataValidationError",
                non_retryable=True,
            ) from exc

        operation_id = command.operation_id
        runtime = _runtime()
        try:
            async with runtime.session() as session:
                operation = await session.get(Operation, operation_id)
                if operation is None or operation.organization_id != command.organization_id:
                    raise ApplicationError(
                        "tenant-scoped operation record was not found",
                        type="OperationNotFound",
                        non_retryable=True,
                    )
                operation.state = "running"
                operation.error_code = None
                operation.error_detail = None

                service = AgentRuntimeService(session)
                run = await service.create_run(
                    organization_id=command.organization_id,
                    capability=command.capability,
                    case_id=command.case_id,
                    input_payload=command.input_payload,
                    data_as_of=command.data_as_of,
                    knowledge_cutoff=command.knowledge_cutoff,
                    actor_id=command.requested_by,
                    permissions=frozenset({"agent_runs:create"}),
                    workflow_id=command.workflow_id,
                    trace_id=activity.info().activity_id,
                    idempotency_key=command.idempotency_key,
                )
                run_id = run.id
                await session.flush()

                fetched = await AgentRuntimeService(session).get_run(run_id)
                if fetched is None:
                    raise RuntimeError("agent run disappeared after creation")
                run = fetched
                if run.status == "failed" and run.error_code == "provider_transient":
                    run.status = "queued"
                    run.error_code = None
                    run.error_detail = None
                    run.finished_at = None
                    await session.flush()

                executed = await AgentExecutionService(session, _provider()).execute(
                    run_id,
                    metadata={
                        "org_id": str(command.organization_id),
                        "workflow_id": command.workflow_id or "",
                        "agent_run_id": str(run_id),
                    },
                )

                _calibration_engine().record_prediction(
                    component=command.capability,
                    inputs=command.input_payload,
                    output=executed.output_payload or {},
                    confidence=0.5 if executed.status == "succeeded" else 0.0,
                    tags=[command.capability],
                )

                result = {
                    "operation_id": str(command.operation_id),
                    "run_id": str(executed.id),
                    "status": executed.status,
                    "capability": command.capability,
                    "output": executed.output_payload,
                    "error_code": executed.error_code,
                    "error_detail": executed.error_detail,
                    "prompt_tokens": executed.prompt_tokens,
                    "completion_tokens": executed.completion_tokens,
                    "cost_usd": str(executed.cost_usd),
                    "duration_ms": executed.duration_ms,
                    "evidence_coverage": (
                        str(executed.evidence_coverage) if executed.evidence_coverage is not None else None
                    ),
                }
                operation = await session.get(Operation, operation_id)
                if operation is None or operation.organization_id != command.organization_id:
                    raise RuntimeError("operation disappeared during agent execution")
                operation.state = "succeeded" if executed.status == "succeeded" else "failed"
                operation.result_data = result  # type: ignore[assignment]
                operation.error_code = executed.error_code
                operation.error_detail = executed.error_detail
                await session.commit()

                if executed.status == "failed" and executed.error_code == "provider_transient":
                    raise ApplicationError(
                        "transient AI provider failure",
                        type="ProviderTransientError",
                        non_retryable=False,
                    )
                logger.info(
                    "activity agent.create_and_execute completed run_id=%s status=%s capability=%s",
                    run_id,
                    executed.status,
                    command.capability,
                )
                return result
        except ApplicationError:
            raise
        except asyncio.CancelledError:
            logger.warning(
                "activity agent.create_and_execute cancelled capability=%s",
                command.capability,
            )
            async with runtime.session() as session:
                operation = await session.get(Operation, operation_id)
                if operation is not None and operation.organization_id == command.organization_id:
                    operation.state = "cancelled"
                    operation.error_code = "workflow_cancelled"
                    operation.error_detail = "Operation was cancelled"
                    await session.commit()
            raise
        except Exception as exc:
            logger.warning(
                "activity agent.create_and_execute failed capability=%s error=%s",
                command.capability,
                type(exc).__name__,
            )
            async with runtime.session() as session:
                operation = await session.get(Operation, operation_id)
                if operation is not None and operation.organization_id == command.organization_id:
                    operation.state = "failed"
                    operation.error_code = "agent_activity_failed"
                    operation.error_detail = type(exc).__name__
                    await session.commit()
            raise
        finally:
            await runtime.dispose()


AGENT_RUNTIME_ACTIVITIES = (create_and_execute_agent_run,)
