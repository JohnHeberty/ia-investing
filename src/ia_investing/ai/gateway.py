from __future__ import annotations

import asyncio
import json
import logging
import time
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel

from ._pricing import estimate_cost
from .contracts import ProviderResponse, ProviderUsage
from .gateway_errors import (
    ProviderAuthError,
    ProviderBadRequestError,
    ProviderError,
    ProviderRateLimitError,
    ProviderTimeoutError,
)
from .rate_limiter import TokenBucketRateLimiter

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Request / response contracts
# ---------------------------------------------------------------------------


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: str


class ChatCompletionRequest(BaseModel):
    messages: list[ChatMessage]
    model: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    stream: bool = False


class ChatCompletionResponse(BaseModel):
    content: str
    provider_run_id: str
    usage: ProviderUsage


class EmbeddingRequest(BaseModel):
    input: list[str]
    model: str | None = None


class EmbeddingResponse(BaseModel):
    embeddings: list[list[float]]
    usage: ProviderUsage


# ---------------------------------------------------------------------------
# Abstract gateway
# ---------------------------------------------------------------------------


class AIGateway(ABC):
    def __init__(self, rate_limiter: TokenBucketRateLimiter, default_model: str) -> None:
        self.rate_limiter = rate_limiter
        self.default_model = default_model

    @abstractmethod
    async def chat_completion(self, request: ChatCompletionRequest) -> ChatCompletionResponse: ...

    async def stream_chat_completion(self, request: ChatCompletionRequest) -> AsyncIterator[str]:
        raise NotImplementedError("Streaming is not supported by this gateway implementation")
        if False:
            yield ""

    @abstractmethod
    async def embed(self, request: EmbeddingRequest) -> EmbeddingResponse: ...


# ---------------------------------------------------------------------------
# OpenAI gateway
# ---------------------------------------------------------------------------


class OpenAIGateway(AIGateway):
    def __init__(
        self,
        *,
        api_key: str,
        default_model: str,
        rate_limiter: TokenBucketRateLimiter,
        base_url: str | None = None,
        timeout: float = 120.0,
        max_retries: int = 3,
    ) -> None:
        super().__init__(rate_limiter, default_model)
        import openai

        self._openai = openai
        self._client = openai.AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout,
            max_retries=max_retries,
        )

    async def chat_completion(self, request: ChatCompletionRequest) -> ChatCompletionResponse:
        model = request.model or self.default_model
        kwargs: dict = {
            "model": model,
            "messages": [{"role": m.role, "content": m.content} for m in request.messages],
        }
        if request.temperature is not None:
            kwargs["temperature"] = request.temperature
        if request.max_tokens is not None:
            kwargs["max_tokens"] = request.max_tokens

        estimated = sum(max(len(m.content) // 4, 1) for m in request.messages)
        wait = await self.rate_limiter.acquire(estimated)
        if wait > 0:
            await asyncio.sleep(wait)

        started = time.monotonic()
        try:
            response = await self._client.chat.completions.create(**kwargs)
        except self._openai.APITimeoutError as exc:
            raise ProviderTimeoutError("OpenAI request timed out") from exc
        except self._openai.RateLimitError as exc:
            raise ProviderRateLimitError("OpenAI rate limit exceeded") from exc
        except self._openai.AuthenticationError as exc:
            raise ProviderAuthError("OpenAI authentication failed") from exc
        except self._openai.BadRequestError as exc:
            raise ProviderBadRequestError(str(exc)) from exc
        except self._openai.APIError as exc:
            raise ProviderError("OpenAI API error", retryable=False, safe_detail="Provider request failed") from exc

        duration = int((time.monotonic() - started) * 1_000)
        choice = response.choices[0]
        content = choice.message.content or ""
        usage_data = response.usage
        prompt_tokens = int(getattr(usage_data, "prompt_tokens", 0) or 0)
        completion_tokens = int(getattr(usage_data, "completion_tokens", 0) or 0)
        cost = estimate_cost(model, prompt_tokens, completion_tokens)

        return ChatCompletionResponse(
            content=content,
            provider_run_id=response.id,
            usage=ProviderUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                cost_usd=Decimal(str(cost)),
                duration_ms=duration,
            ),
        )

    async def stream_chat_completion(self, request: ChatCompletionRequest) -> AsyncIterator[str]:
        model = request.model or self.default_model
        kwargs: dict = {
            "model": model,
            "messages": [{"role": m.role, "content": m.content} for m in request.messages],
            "stream": True,
        }
        if request.temperature is not None:
            kwargs["temperature"] = request.temperature
        if request.max_tokens is not None:
            kwargs["max_tokens"] = request.max_tokens

        estimated = sum(max(len(m.content) // 4, 1) for m in request.messages)
        wait = await self.rate_limiter.acquire(estimated)
        if wait > 0:
            await asyncio.sleep(wait)

        try:
            stream = await self._client.chat.completions.create(**kwargs)
            async for chunk in stream:
                delta = chunk.choices[0].delta if chunk.choices else None
                if delta and delta.content:
                    yield delta.content
        except self._openai.APITimeoutError as exc:
            raise ProviderTimeoutError("OpenAI streaming request timed out") from exc
        except self._openai.RateLimitError as exc:
            raise ProviderRateLimitError("OpenAI rate limit exceeded") from exc
        except self._openai.AuthenticationError as exc:
            raise ProviderAuthError("OpenAI authentication failed") from exc
        except self._openai.BadRequestError as exc:
            raise ProviderBadRequestError(str(exc)) from exc
        except self._openai.APIError as exc:
            raise ProviderError("OpenAI API error", retryable=False, safe_detail="Provider request failed") from exc

    async def embed(self, request: EmbeddingRequest) -> EmbeddingResponse:
        model = request.model or self.default_model
        started = time.monotonic()
        try:
            response = await self._client.embeddings.create(model=model, input=request.input)
        except self._openai.APITimeoutError as exc:
            raise ProviderTimeoutError("OpenAI embedding request timed out") from exc
        except self._openai.RateLimitError as exc:
            raise ProviderRateLimitError("OpenAI embedding rate limit exceeded") from exc
        except self._openai.AuthenticationError as exc:
            raise ProviderAuthError("OpenAI authentication failed") from exc
        except self._openai.BadRequestError as exc:
            raise ProviderBadRequestError(str(exc)) from exc
        except self._openai.APIError as exc:
            raise ProviderError("OpenAI API error", retryable=False, safe_detail="Provider request failed") from exc

        duration = int((time.monotonic() - started) * 1_000)
        embeddings = [item.embedding for item in response.data]
        usage_data = response.usage
        prompt_tokens = int(getattr(usage_data, "prompt_tokens", 0) or 0)
        cost = estimate_cost(model, prompt_tokens, 0)
        return EmbeddingResponse(
            embeddings=embeddings,
            usage=ProviderUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=0,
                cost_usd=Decimal(str(cost)),
                duration_ms=duration,
            ),
        )


# ---------------------------------------------------------------------------
# Anthropic gateway
# ---------------------------------------------------------------------------


class AnthropicGateway(AIGateway):
    def __init__(
        self,
        *,
        api_key: str,
        default_model: str,
        rate_limiter: TokenBucketRateLimiter,
        base_url: str | None = None,
        timeout: float = 120.0,
        max_retries: int = 3,
    ) -> None:
        super().__init__(rate_limiter, default_model)
        import anthropic

        self._anthropic = anthropic
        self._client = anthropic.AsyncAnthropic(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout,
            max_retries=max_retries,
        )

    async def chat_completion(self, request: ChatCompletionRequest) -> ChatCompletionResponse:
        model = request.model or self.default_model
        system, messages = self._split_messages(request.messages)

        estimated = sum(max(len(m.content) // 4, 1) for m in request.messages)
        wait = await self.rate_limiter.acquire(estimated)
        if wait > 0:
            await asyncio.sleep(wait)

        started = time.monotonic()
        try:
            response = await self._client.messages.create(
                model=model,
                system=system,
                messages=messages,
                max_tokens=request.max_tokens or 4096,
                temperature=request.temperature,
            )
        except self._anthropic.APITimeoutError as exc:
            raise ProviderTimeoutError("Anthropic request timed out") from exc
        except self._anthropic.RateLimitError as exc:
            raise ProviderRateLimitError("Anthropic rate limit exceeded") from exc
        except self._anthropic.AuthenticationError as exc:
            raise ProviderAuthError("Anthropic authentication failed") from exc
        except self._anthropic.BadRequestError as exc:
            raise ProviderBadRequestError(str(exc)) from exc
        except self._anthropic.APIError as exc:
            raise ProviderError("Anthropic API error", retryable=False, safe_detail="Provider request failed") from exc

        duration = int((time.monotonic() - started) * 1_000)
        content = "".join(block.text for block in response.content if hasattr(block, "text"))
        usage_data = response.usage
        prompt_tokens = int(getattr(usage_data, "input_tokens", 0) or 0)
        completion_tokens = int(getattr(usage_data, "output_tokens", 0) or 0)
        cost = estimate_cost(model, prompt_tokens, completion_tokens)

        return ChatCompletionResponse(
            content=content,
            provider_run_id=response.id,
            usage=ProviderUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                cost_usd=Decimal(str(cost)),
                duration_ms=duration,
            ),
        )

    async def stream_chat_completion(self, request: ChatCompletionRequest) -> AsyncIterator[str]:
        model = request.model or self.default_model
        system, messages = self._split_messages(request.messages)

        estimated = sum(max(len(m.content) // 4, 1) for m in request.messages)
        wait = await self.rate_limiter.acquire(estimated)
        if wait > 0:
            await asyncio.sleep(wait)

        try:
            async with self._client.messages.stream(
                model=model,
                system=system,
                messages=messages,
                max_tokens=request.max_tokens or 4096,
                temperature=request.temperature,
            ) as stream:
                async for text in stream.text_stream:
                    yield text
        except self._anthropic.APITimeoutError as exc:
            raise ProviderTimeoutError("Anthropic streaming request timed out") from exc
        except self._anthropic.RateLimitError as exc:
            raise ProviderRateLimitError("Anthropic rate limit exceeded") from exc
        except self._anthropic.AuthenticationError as exc:
            raise ProviderAuthError("Anthropic authentication failed") from exc
        except self._anthropic.BadRequestError as exc:
            raise ProviderBadRequestError(str(exc)) from exc
        except self._anthropic.APIError as exc:
            raise ProviderError("Anthropic API error", retryable=False, safe_detail="Provider request failed") from exc

    async def embed(self, request: EmbeddingRequest) -> EmbeddingResponse:
        raise NotImplementedError("Anthropic does not expose a public embedding API")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _split_messages(
        messages: list[ChatMessage],
    ) -> tuple[str | None, list[dict[str, str]]]:
        system: str | None = None
        msgs: list[dict[str, str]] = []
        for msg in messages:
            if msg.role == "system":
                system = (system or "") + msg.content
            elif msg.role == "tool":
                msgs.append({"role": "user", "content": f"[tool result]\n{msg.content}"})
            else:
                msgs.append({"role": msg.role, "content": msg.content})
        return system, msgs


# ---------------------------------------------------------------------------
# Adapter: AIGateway → AgentProvider protocol
# ---------------------------------------------------------------------------


class GatewayProvider:
    def __init__(self, gateway: AIGateway) -> None:
        self.gateway = gateway

    async def complete(
        self,
        *,
        model: str,
        instructions: str,
        input_payload: dict[str, object],
        output_schema: dict[str, object],
    ) -> ProviderResponse:
        _ = output_schema
        messages = [
            ChatMessage(role="system", content=instructions),
            ChatMessage(role="user", content=json.dumps(input_payload, ensure_ascii=False, default=str)),
        ]
        started = time.monotonic()
        try:
            result = await self.gateway.chat_completion(
                ChatCompletionRequest(messages=messages, model=model),
            )
        except ProviderError as exc:
            retryable = isinstance(exc, (ProviderTimeoutError, ProviderRateLimitError))
            code = "provider_transient" if retryable else "provider_rejected"
            raise ProviderError(code, retryable=retryable, safe_detail="Provider request failed") from exc

        raw_output = result.content
        try:
            output = json.loads(raw_output) if isinstance(raw_output, str) else raw_output
        except json.JSONDecodeError as exc:
            raise ProviderError(
                "provider_invalid_json", retryable=False, safe_detail="Provider returned invalid JSON",
            ) from exc
        if not isinstance(output, dict):
            raise ProviderError(
                "provider_invalid_output", retryable=False, safe_detail="Provider output must be a JSON object",
            )

        duration = int((time.monotonic() - started) * 1_000)
        usage = ProviderUsage(
            prompt_tokens=result.usage.prompt_tokens,
            completion_tokens=result.usage.completion_tokens,
            cost_usd=result.usage.cost_usd,
            duration_ms=duration,
        )

        return ProviderResponse(
            provider_run_id=result.provider_run_id,
            output=output,
            usage=usage,
        )


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def create_gateway_provider(
    *,
    provider: str,
    api_key: str,
    default_model: str,
    base_url: str | None = None,
    timeout: float = 120.0,
    max_retries: int = 3,
    rpm: int = 60,
    tpm: int = 100_000,
) -> GatewayProvider:
    rate_limiter = TokenBucketRateLimiter(rpm=rpm, tpm=tpm)

    if provider == "openai":
        gateway: AIGateway = OpenAIGateway(
            api_key=api_key,
            default_model=default_model,
            rate_limiter=rate_limiter,
            base_url=base_url,
            timeout=timeout,
            max_retries=max_retries,
        )
    elif provider == "anthropic":
        gateway = AnthropicGateway(
            api_key=api_key,
            default_model=default_model,
            rate_limiter=rate_limiter,
            base_url=base_url,
            timeout=timeout,
            max_retries=max_retries,
        )
    else:
        raise ValueError(f"Unknown AI gateway provider: {provider}")

    return GatewayProvider(gateway)
