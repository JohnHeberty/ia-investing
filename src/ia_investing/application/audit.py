from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4


@dataclass(frozen=True, slots=True)
class SecurityEvent:
    event_id: UUID
    event_type: str
    timestamp: datetime
    actor_subject: str | None
    resource: str | None
    action: str | None
    outcome: str
    detail: str | None
    correlation_id: UUID | None = None
    extra: dict[str, str] = field(default_factory=dict)


_security_events: list[SecurityEvent] = []


def emit_security_event(
    event_type: str,
    actor: str | None = None,
    resource: str | None = None,
    action: str | None = None,
    outcome: str = "deny",
    detail: str | None = None,
    correlation_id: UUID | None = None,
    **extra: str,
) -> SecurityEvent:
    event = SecurityEvent(
        event_id=uuid4(),
        event_type=event_type,
        timestamp=datetime.now(UTC),
        actor_subject=actor,
        resource=resource,
        action=action,
        outcome=outcome,
        detail=detail,
        correlation_id=correlation_id,
        extra=extra,
    )
    _security_events.append(event)
    return event


def get_security_events() -> list[SecurityEvent]:
    return list(_security_events)


def clear_security_events() -> None:
    _security_events.clear()
