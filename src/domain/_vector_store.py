from __future__ import annotations

import uuid

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.catalog import Embedding

from ._models import Chunk, SearchResult


class VectorStore:
    def __init__(self, session: AsyncSession | None = None) -> None:
        self._session = session

    async def store_chunks(self, chunks: list[Chunk]) -> None:
        if not chunks or self._session is None:
            return

        rows = [
            {
                "id": chunk.id,
                "content_type": chunk.content_type,
                "entity_id": chunk.entity_id,
                "text_snippet": chunk.text,
                "vector": chunk.embedding,
                "created_at": chunk.created_at,
            }
            for chunk in chunks
            if chunk.embedding is not None
        ]

        if not rows:
            return

        stmt = sa.dialects.postgresql.insert(Embedding).values(rows)
        stmt = stmt.on_conflict_do_update(
            index_elements=[Embedding.__table__.c.id],
            set_={
                "text_snippet": stmt.excluded.text_snippet,
                "vector": stmt.excluded.vector,
            },
        )
        await self._session.execute(stmt)

    async def search(
        self,
        query_embedding: list[float],
        content_type: str | None = None,
        entity_id: uuid.UUID | None = None,
        top_k: int = 10,
    ) -> list[SearchResult]:
        if self._session is None:
            return []

        distance_col = Embedding.__table__.c.vector.cosine_distance(query_embedding).label("distance")
        score_col = (1 - distance_col).label("score")

        stmt = (
            sa.select(Embedding, score_col, distance_col)
            .order_by(distance_col)
            .limit(top_k)
        )

        if content_type is not None:
            stmt = stmt.where(Embedding.content_type == content_type)
        if entity_id is not None:
            stmt = stmt.where(Embedding.entity_id == entity_id)

        result = await self._session.execute(stmt)
        rows = result.all()

        return [
            SearchResult(
                chunk=Chunk(
                    id=row.Embedding.id,
                    content_type=row.Embedding.content_type,
                    entity_id=row.Embedding.entity_id,
                    text=row.Embedding.text_snippet,
                    embedding=None,
                    created_at=row.Embedding.created_at,
                ),
                score=float(row.score),
                distance=float(row.distance),
            )
            for row in rows
        ]

    async def delete_entity_chunks(self, entity_id: uuid.UUID) -> int:
        if self._session is None:
            return 0

        stmt = sa.delete(Embedding).where(Embedding.entity_id == entity_id)
        result = await self._session.execute(stmt)
        return result.rowcount or 0
