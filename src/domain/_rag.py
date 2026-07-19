from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from ._chunker import TextChunker
from ._embedder import EmbeddingBackend, EmbeddingProvider
from ._models import Chunk, SearchResult
from ._vector_store import VectorStore


class RAGManager:
    def __init__(
        self,
        openai_client: EmbeddingBackend | None = None,
        db_session: AsyncSession | None = None,
        chunker: TextChunker | None = None,
        embedder: EmbeddingProvider | None = None,
        vector_store: VectorStore | None = None,
    ) -> None:
        self._chunker = chunker or TextChunker()
        self._embedder = embedder or EmbeddingProvider(openai_client)
        self._store = vector_store or VectorStore(db_session)

    def chunk_text(self, text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
        return self._chunker.chunk_text(text, chunk_size, overlap)

    async def embed_chunks(self, chunks: list[str], model: str = "text-embedding-3-small") -> list[list[float]]:
        return await self._embedder.embed_chunks(chunks, model)

    async def store_chunks(self, chunks: list[Chunk]) -> None:
        await self._store.store_chunks(chunks)

    async def search(
        self,
        query: str,
        content_type: str | None = None,
        entity_id: uuid.UUID | None = None,
        top_k: int = 10,
    ) -> list[SearchResult]:
        embeddings = await self._embedder.embed_chunks([query])
        if not embeddings:
            return []
        return await self._store.search(embeddings[0], content_type=content_type, entity_id=entity_id, top_k=top_k)

    async def index_document(
        self,
        document_id: uuid.UUID,
        text: str,
        content_type: str,
        metadata: dict | None = None,
    ) -> int:
        text_chunks = self._chunker.chunk_text(text)
        embeddings = await self._embedder.embed_chunks(text_chunks)

        chunks = [
            Chunk(
                id=uuid.uuid4(),
                content_type=content_type,
                entity_id=document_id,
                text=text_chunk,
                embedding=embedding,
                metadata=metadata or {},
            )
            for text_chunk, embedding in zip(text_chunks, embeddings, strict=True)
        ]

        await self._store.store_chunks(chunks)
        return len(chunks)

    async def delete_entity_chunks(self, entity_id: uuid.UUID) -> int:
        return await self._store.delete_entity_chunks(entity_id)
