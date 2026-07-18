from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from openai import AsyncOpenAI


class _EmbeddingsAPI(Protocol):
    async def create(self, *, input: list[str], model: str) -> Any: ...


@runtime_checkable
class EmbeddingBackend(Protocol):
    embeddings: _EmbeddingsAPI


class EmbeddingProvider:
    def __init__(self, backend: EmbeddingBackend | None = None) -> None:
        self._backend = backend or AsyncOpenAI()

    async def embed_chunks(
        self, chunks: list[str], model: str = "text-embedding-3-small"
    ) -> list[list[float]]:
        if not chunks:
            return []

        response = await self._backend.embeddings.create(input=chunks, model=model)
        return [item.embedding for item in response.data]
