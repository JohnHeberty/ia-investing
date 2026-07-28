from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Protocol

from .contracts import ProviderResponse, ProviderUsage
from .gateway_errors import ProviderError  # re-export canonical definition

__all__ = ["ProviderError"]


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
    _fallback_responses: list[tuple[str, str, dict[str, object]]] = field(default_factory=list)

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

    def add_fallback(self, model_pattern: str, instructions_pattern: str, response: dict[str, object]) -> None:
        self._fallback_responses.append((model_pattern, instructions_pattern, response))

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
        if key in self.responses:
            return ProviderResponse(
                provider_run_id=f"mock:{key}",
                output=self.responses[key],
                usage=ProviderUsage(prompt_tokens=0, completion_tokens=0, cost_usd=Decimal(0), duration_ms=0),
            )
        for model_pattern, instructions_pattern, response in self._fallback_responses:
            model_ok = model == model_pattern if model_pattern != "*" else True
            instr_ok = instructions == instructions_pattern if instructions_pattern != "*" else True
            if model_ok and instr_ok:
                return ProviderResponse(
                    provider_run_id=f"mock:fallback:{hashlib.sha256(instructions.encode()).hexdigest()[:8]}",
                    output=response,
                    usage=ProviderUsage(prompt_tokens=0, completion_tokens=0, cost_usd=Decimal(0), duration_ms=0),
                )
        raise ProviderError("mock_response_missing", retryable=False, safe_detail="No replay fixture for request")


def uuid_from_output(output: dict[str, object]) -> str:
    canonical = json.dumps(output, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)
    return f"output:{hashlib.sha256(canonical.encode()).hexdigest()}"
