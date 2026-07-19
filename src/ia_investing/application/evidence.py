from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from uuid import UUID

import sqlalchemy as sa
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.evidence import DocumentChunk
from ia_investing.application.financial_facts import require_aware


class EvidenceReferenceV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    chunk_id: UUID
    source_object_version_id: UUID
    page_start: int = Field(gt=0)
    page_end: int = Field(gt=0)
    section_path: list[str]
    table_reference: str | None
    quote: str
    content_sha256: str
    score: float
    data_as_of: datetime


@dataclass(frozen=True, slots=True)
class PageChunk:
    page: int
    ordinal: int
    text: str
    content_sha256: str
    section_path: tuple[str, ...] = ()
    table_reference: str | None = None


def chunks_from_pages(pages: list[str]) -> list[PageChunk]:
    chunks: list[PageChunk] = []
    ordinal = 0
    for page_number, page_text in enumerate(pages, start=1):
        for block in (block.strip() for block in page_text.split("\n\n")):
            if not block:
                continue
            chunks.append(
                PageChunk(
                    page=page_number,
                    ordinal=ordinal,
                    text=block,
                    content_sha256=hashlib.sha256(block.encode("utf-8")).hexdigest(),
                )
            )
            ordinal += 1
    return chunks


class EvidenceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def search(
        self,
        query: str,
        as_of: datetime,
        embedding: list[float] | None = None,
        minimum_score: float = 0.05,
        limit: int = 20,
    ) -> list[EvidenceReferenceV1]:
        require_aware(as_of, "as_of")
        if not query.strip():
            raise ValueError("query cannot be empty")
        if embedding is not None and len(embedding) != 1536:
            raise ValueError("embedding must contain 1536 dimensions")
        text_query = sa.func.plainto_tsquery("portuguese", query)
        lexical = sa.func.ts_rank_cd(DocumentChunk.search_tsv, text_query)
        score = lexical
        conditions = [DocumentChunk.knowledge_at <= as_of]
        if embedding is not None:
            semantic = 1 - DocumentChunk.embedding.cosine_distance(embedding)
            score = lexical * 0.4 + semantic * 0.6
            conditions.append(DocumentChunk.embedding.is_not(None))
        statement = (
            sa.select(DocumentChunk, score.label("score"))
            .where(*conditions, score >= minimum_score)
            .order_by(sa.desc("score"), DocumentChunk.ordinal)
            .limit(min(max(limit, 1), 100))
        )
        rows = (await self.session.execute(statement)).all()
        return [
            EvidenceReferenceV1(
                chunk_id=chunk.id,
                source_object_version_id=chunk.source_object_version_id,
                page_start=chunk.page_start,
                page_end=chunk.page_end,
                section_path=list(chunk.section_path),
                table_reference=chunk.table_reference,
                quote=chunk.text,
                content_sha256=chunk.content_sha256,
                score=float(row_score),
                data_as_of=as_of,
            )
            for chunk, row_score in rows
        ]
