from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field


class OperationState(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class OperationStatusV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    operation_id: UUID
    state: OperationState
    created_at: AwareDatetime
    updated_at: AwareDatetime
    result_url: str | None = None
    error_code: str | None = None
    error_detail: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class OperationAcceptedV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    operation_id: UUID
    state: OperationState = OperationState.PENDING
