from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Protocol

from agents import Agent, Runner

from ._pricing import estimate_cost
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


@dataclass(slots=True)
class OpenAIAgentsProvider:
    timeout_seconds: float = 300

    async def complete(
        self,
        *,
        model: str,
        instructions: str,
        input_payload: dict[str, object],
        output_schema: dict[str, object],
    ) -> ProviderResponse:
        if not output_schema:
            raise ProviderError("schema_missing", retryable=False, safe_detail="A versioned output schema is required")
        started = time.monotonic()
        agent = Agent(name="versioned-runtime", instructions=instructions, model=model)
        try:
            result = await Runner.run(
                agent,
                json.dumps(input_payload, ensure_ascii=False, sort_keys=True, default=str),
                max_turns=8,
            )
        except Exception as exc:
            name = type(exc).__name__.lower()
            retryable = any(term in name for term in ("timeout", "rate", "connection", "server"))
            code = "provider_transient" if retryable else "provider_rejected"
            raise ProviderError(code, retryable=retryable, safe_detail="Provider request failed") from exc
        raw_output = result.final_output
        try:
            output = json.loads(raw_output) if isinstance(raw_output, str) else raw_output
        except json.JSONDecodeError as exc:
            raise ProviderError(
                "provider_invalid_json", retryable=False, safe_detail="Provider returned invalid JSON"
            ) from exc
        if not isinstance(output, dict):
            raise ProviderError(
                "provider_invalid_output", retryable=False, safe_detail="Provider output must be a JSON object"
            )
        usage = getattr(getattr(result, "context_wrapper", None), "usage", None)
        prompt_tokens = int(getattr(usage, "input_tokens", 0) or 0)
        completion_tokens = int(getattr(usage, "output_tokens", 0) or 0)
        return ProviderResponse(
            provider_run_id=str(getattr(result, "last_response_id", None) or uuid_from_output(output)),
            output=output,
            usage=ProviderUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                cost_usd=Decimal(str(estimate_cost(model, prompt_tokens, completion_tokens))),
                duration_ms=int((time.monotonic() - started) * 1_000),
            ),
        )


def uuid_from_output(output: dict[str, object]) -> str:
    canonical = json.dumps(output, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)
    return f"output:{hashlib.sha256(canonical.encode()).hexdigest()}"
