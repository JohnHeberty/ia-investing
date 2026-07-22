"""Relay candidate-intelligence outbox events to idempotent Temporal workflows."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from temporalio import activity
from temporalio.client import Client
from temporalio.exceptions import ApplicationError, WorkflowAlreadyStartedError

from database.models.research import DomainOutboxEvent
from ia_investing.orchestration.activities.candidate_intelligence import (
    CandidateSourceValidationInput,
    CandidateWorkflowInput,
    ExplorationWorkflowInput,
)
from ia_investing.platform.database import DatabaseRuntime
from ia_investing.settings import get_settings

_SUPPORTED_EVENTS = frozenset(
    {
        "candidate.analysis.requested",
        "candidate.source.validation.requested",
        "equity.exploration.requested",
    }
)


def _runtime() -> DatabaseRuntime:
    return DatabaseRuntime.create(get_settings().database.url)


def _uuid(payload: dict[str, Any], key: str) -> UUID:
    try:
        return UUID(str(payload[key]))
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"invalid or missing {key}") from exc


def _datetime(payload: dict[str, Any], key: str) -> datetime:
    try:
        value = datetime.fromisoformat(str(payload[key]).replace("Z", "+00:00"))
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"invalid or missing {key}") from exc
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


async def _dispatch_event(client: Client, event: DomainOutboxEvent) -> None:
    from workflows.candidate_intelligence import (
        AutonomousEquityExplorationWorkflow,
        CandidateAnalysisWorkflow,
        CandidateSourceValidationWorkflow,
    )

    payload = dict(event.payload or {})
    correlation_id = event.correlation_id
    if event.event_type == "candidate.analysis.requested":
        command = CandidateWorkflowInput(
            candidate_id=_uuid(payload, "candidate_id"),
            analysis_run_id=_uuid(payload, "analysis_run_id"),
            organization_id=_uuid(payload, "organization_id"),
            data_as_of=_datetime(payload, "data_as_of"),
            allow_incomplete=bool(payload.get("allow_incomplete", False)),
            correlation_id=correlation_id,
        )
        await client.start_workflow(
            CandidateAnalysisWorkflow.run,
            command,
            id=f"candidate-analysis-{command.analysis_run_id}",
            task_queue="research-agents",
        )
        return

    if event.event_type == "candidate.source.validation.requested":
        command = CandidateSourceValidationInput(
            candidate_id=_uuid(payload, "candidate_id"),
            source_id=_uuid(payload, "source_id"),
            organization_id=_uuid(payload, "organization_id"),
            correlation_id=correlation_id,
        )
        await client.start_workflow(
            CandidateSourceValidationWorkflow.run,
            command,
            id=f"candidate-source-validation-{command.source_id}",
            task_queue="research-agents",
        )
        return

    if event.event_type == "equity.exploration.requested":
        run_id = _uuid(payload, "exploration_run_id")
        organization_id = _uuid(payload, "organization_id")
        command = ExplorationWorkflowInput(
            exploration_run_id=run_id,
            organization_id=organization_id,
            data_as_of=_datetime(payload, "data_as_of"),
            correlation_id=correlation_id,
        )
        await client.start_workflow(
            AutonomousEquityExplorationWorkflow.run,
            command,
            id=f"equity-exploration-{run_id}",
            task_queue="research-agents",
        )
        return

    raise ValueError(f"unsupported candidate event type {event.event_type!r}")


@activity.defn(name="dispatch_candidate_intelligence_events")
async def dispatch_candidate_intelligence_events(
    raw_input: dict[str, Any] | None = None,
) -> dict[str, int]:
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
    invalid = 0
    failed = 0
    try:
        async with runtime.session() as session:
            events = (
                (
                    await session.execute(
                        select(DomainOutboxEvent)
                        .where(
                            DomainOutboxEvent.published_at.is_(None),
                            DomainOutboxEvent.event_type.in_(_SUPPORTED_EVENTS),
                        )
                        .order_by(DomainOutboxEvent.occurred_at, DomainOutboxEvent.id)
                        .with_for_update(skip_locked=True)
                        .limit(batch_size)
                    )
                )
                .scalars()
                .all()
            )
            for event in events:
                try:
                    await _dispatch_event(client, event)
                except WorkflowAlreadyStartedError:
                    pass
                except ValueError as exc:
                    # Invalid durable payloads require operator repair; leave unpublished for visibility.
                    activity.logger.error(
                        "invalid candidate-intelligence outbox event",
                        extra={"event_id": str(event.id), "event_type": event.event_type, "error": str(exc)},
                    )
                    invalid += 1
                    continue
                except Exception:
                    activity.logger.exception(
                        "failed to dispatch candidate-intelligence outbox event",
                        extra={"event_id": str(event.id), "event_type": event.event_type},
                    )
                    failed += 1
                    continue
                event.published_at = datetime.now(UTC)
                dispatched += 1
            await session.commit()
    finally:
        await runtime.dispose()
    return {"dispatched": dispatched, "invalid": invalid, "failed": failed}


@activity.defn(name="create_scheduled_exploration_run")
async def create_scheduled_exploration_run(raw_command: dict[str, Any]) -> dict[str, str]:
    """Create one durable exploration run for a recurring schedule occurrence."""
    from decimal import Decimal
    from uuid import uuid4

    from database.models.investment_candidates import ExplorationRunRecord

    try:
        organization_id = UUID(str(raw_command["organization_id"]))
        strategy_codes = [str(item) for item in raw_command["strategy_codes"]]
        minimum_liquidity = Decimal(str(raw_command["minimum_liquidity"]))
        maximum_suggestions = int(raw_command["maximum_suggestions"])
        requested_by = str(raw_command.get("requested_by", "schedule:autonomous-equity-explorer"))
        correlation_id = UUID(str(raw_command.get("correlation_id") or uuid4()))
    except (KeyError, TypeError, ValueError) as exc:
        raise ApplicationError(
            "invalid scheduled exploration input",
            type="DataValidationError",
            non_retryable=True,
        ) from exc
    if not strategy_codes or not 1 <= maximum_suggestions <= 100 or minimum_liquidity < 0:
        raise ApplicationError(
            "scheduled exploration constraints are invalid",
            type="DataValidationError",
            non_retryable=True,
        )
    now = datetime.now(UTC)
    workflow_id = activity.info().workflow_id
    runtime = _runtime()
    try:
        async with runtime.session() as session:
            existing = await session.scalar(
                select(ExplorationRunRecord).where(
                    ExplorationRunRecord.organization_id == organization_id,
                    ExplorationRunRecord.workflow_id == workflow_id,
                )
            )
            if existing is not None:
                run_id = existing.id
                now = existing.data_as_of
            else:
                run_id = uuid4()
                session.add(
                    ExplorationRunRecord(
                        id=run_id,
                        organization_id=organization_id,
                        status="queued",
                        strategy_codes=strategy_codes,
                        requested_by=requested_by,
                        created_at=now,
                        data_as_of=now,
                        minimum_liquidity=minimum_liquidity,
                        maximum_suggestions=maximum_suggestions,
                        excluded_instrument_ids=[],
                        workflow_id=workflow_id,
                        universe_size=0,
                        eligible_size=0,
                    )
                )
                await session.commit()
    finally:
        await runtime.dispose()
    return {
        "exploration_run_id": str(run_id),
        "organization_id": str(organization_id),
        "data_as_of": now.isoformat(),
        "correlation_id": str(correlation_id),
    }


CANDIDATE_DISPATCH_ACTIVITIES = (
    dispatch_candidate_intelligence_events,
    create_scheduled_exploration_run,
)
