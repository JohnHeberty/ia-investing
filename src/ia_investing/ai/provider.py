from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Protocol

from .contracts import ProviderResponse, ProviderUsage


class ProviderError(RuntimeError):
    def __init__(self, code: str, *, retryable: bool, safe_detail: str) -> None:
        super().__init__(safe_detail)
        self.code = code
        self.retryable = retryable
        self.safe_detail = safe_detail


class AgentProvider(Protocol):
    async def complete(
        self,
        *,
        model: str,
        instructions: str,
        input_payload: dict[str, object],
        output_schema: dict[str, object],
        metadata: dict[str, str] | None = None,
    ) -> ProviderResponse: ...


@dataclass(slots=True)
class MockProvider:
    responses: dict[str, dict[str, object]] = field(default_factory=dict)

    @staticmethod
    def request_key(model: str, instructions: str, input_payload: dict[str, object]) -> str:
        canonical = json.dumps(
            {"model": model, "instructions": instructions, "input": input_payload},
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            default=str,
        )
        return hashlib.sha256(canonical.encode()).hexdigest()

    async def complete(
        self,
        *,
        model: str,
        instructions: str,
        input_payload: dict[str, object],
        output_schema: dict[str, object],
        metadata: dict[str, str] | None = None,
    ) -> ProviderResponse:
        del output_schema
        key = self.request_key(model, instructions, input_payload)
        if key not in self.responses:
            raise ProviderError("mock_response_missing", retryable=False, safe_detail="No replay fixture for request")
        return ProviderResponse(
            provider_run_id=f"mock:{key}",
            output=self.responses[key],
            usage=ProviderUsage(prompt_tokens=0, completion_tokens=0, cost_usd=Decimal(0), duration_ms=0),
        )


def uuid_from_output(output: dict[str, object]) -> str:
    canonical = json.dumps(output, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)
    return f"output:{hashlib.sha256(canonical.encode()).hexdigest()}"
