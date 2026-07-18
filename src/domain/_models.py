from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass(slots=True)
class Chunk:
    id: uuid.UUID
    content_type: str
    entity_id: uuid.UUID
    text: str
    embedding: list[float] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(slots=True)
class SearchResult:
    chunk: Chunk
    score: float
    distance: float
