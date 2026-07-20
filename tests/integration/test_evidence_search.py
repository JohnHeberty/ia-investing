"""Integration test: evidence search — lexical and hybrid search.

Verifies:
  - DocumentChunk insert with pgvector embedding
  - Lexical search (ts_rank_cd) returns relevant results
  - Hybrid search (lexical 0.4 + semantic 0.6) works when embedding provided
  - Temporal filter (knowledge_at <= as_of) applies correctly
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.data_foundation import SourceObject, SourceObjectVersion
from database.models.evidence import DocumentChunk

_TZ = UTC


def _dt(y: int, m: int, d: int) -> datetime:
    return datetime(y, m, d, tzinfo=_TZ)


@pytest.fixture
async def seed_evidence(session: AsyncSession):
    """Seed a DocumentChunk with text search and embedding."""
    ds_id = uuid4()
    so = SourceObject(id=uuid4(), source_id=ds_id, logical_uri="test://doc/1", object_type="pdf")
    session.add(so)
    await session.flush()

    sov = SourceObjectVersion(
        source_object_id=so.id,
        version_number=1,
        content_sha256="a" * 64,
        storage_key="test/key",
        media_type="application/pdf",
        size_bytes=1024,
    )
    session.add(sov)
    await session.flush()

    chunk = DocumentChunk(
        source_object_version_id=sov.id,
        page_start=1,
        page_end=1,
        ordinal=0,
        text="A receita líquida do período foi de R$ 50 bilhões, resultado da venda de petróleo e derivados.",
        content_sha256="b" * 64,
        knowledge_at=_dt(2025, 1, 15),
        embedding_model="text-embedding-3-small",
        embedding_version="1",
        embedding_dimension=1536,
        embedding=[0.1] * 1536,
    )
    session.add(chunk)
    await session.flush()
    return chunk


@pytest.mark.asyncio
async def test_lexical_search_returns_results(session: AsyncSession, seed_evidence) -> None:
    """Lexical search finds chunk by Portuguese full-text."""
    from ia_investing.application.evidence import EvidenceRepository

    repo = EvidenceRepository(session)
    results = await repo.search("receita líquida petróleo", _dt(2025, 6, 1))
    assert len(results) >= 1
    assert results[0].chunk_id == seed_evidence.id


@pytest.mark.asyncio
async def test_lexical_search_miss_returns_empty(session: AsyncSession, seed_evidence) -> None:
    """Search for unrelated term returns empty."""
    from ia_investing.application.evidence import EvidenceRepository

    repo = EvidenceRepository(session)
    results = await repo.search("futebol copa do mundo", _dt(2025, 6, 1))
    assert len(results) == 0


@pytest.mark.asyncio
async def test_hybrid_search_with_embedding(session: AsyncSession, seed_evidence) -> None:
    """Hybrid search with embedding produces results."""
    from ia_investing.application.evidence import EvidenceRepository

    repo = EvidenceRepository(session)
    results = await repo.search(
        "receita líquida",
        _dt(2025, 6, 1),
        embedding=[0.1] * 1536,
    )
    assert len(results) >= 1
    assert results[0].score > 0


@pytest.mark.asyncio
async def test_temporal_filter_excludes_future(session: AsyncSession, seed_evidence) -> None:
    """Search as_of before knowledge_at returns no results."""
    from ia_investing.application.evidence import EvidenceRepository

    repo = EvidenceRepository(session)
    results = await repo.search("receita líquida", _dt(2024, 1, 1))
    assert len(results) == 0
