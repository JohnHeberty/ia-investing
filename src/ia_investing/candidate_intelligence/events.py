from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from .models import utcnow


@dataclass(frozen=True, slots=True)
class CandidateEvent:
    id: UUID
    candidate_id: UUID
    organization_id: UUID
    event_type: str
    actor_type: str
    actor_id: str
    occurred_at: datetime
    aggregate_version: int
    payload: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        *,
        candidate_id: UUID,
        organization_id: UUID,
        event_type: str,
        actor_type: str,
        actor_id: str,
        aggregate_version: int,
        payload: dict[str, Any] | None = None,
    ) -> CandidateEvent:
        return cls(
            id=uuid4(),
            candidate_id=candidate_id,
            organization_id=organization_id,
            event_type=event_type,
            actor_type=actor_type,
            actor_id=actor_id,
            occurred_at=utcnow(),
            aggregate_version=aggregate_version,
            payload=payload or {},
        )
