from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from ia_investing.application.evidence import EvidenceReferenceV1, chunks_from_pages


def test_chunks_preserve_page_order_and_stable_hash() -> None:
    chunks = chunks_from_pages(["Primeiro bloco.\n\nSegundo bloco.", "Tabela da página 2."])
    assert [(chunk.page, chunk.ordinal) for chunk in chunks] == [(1, 0), (1, 1), (2, 2)]
    assert chunks[0].content_sha256 == "75ada1392c9a753d04720a1981b993225ae78830f233f1c19ad26c19a0b39861"


def test_evidence_contract_has_verifiable_location() -> None:
    evidence = EvidenceReferenceV1(
        chunk_id=uuid4(),
        source_object_version_id=uuid4(),
        page_start=2,
        page_end=2,
        section_path=["Notas explicativas", "Receita"],
        table_reference="Tabela 4",
        quote="Receita líquida do período.",
        content_sha256="a" * 64,
        score=0.91,
        data_as_of=datetime(2026, 7, 18, tzinfo=UTC),
    )
    assert evidence.page_start == 2


@pytest.mark.asyncio
async def test_search_accepts_embedding_parameter() -> None:
    from ia_investing.application.evidence import EvidenceRepository

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.all.return_value = []
    mock_session.execute.return_value = mock_result

    repo = EvidenceRepository(mock_session)
    embedding = [0.1] * 1536
    result = await repo.search(
        "receita líquida",
        datetime(2026, 7, 18, tzinfo=UTC),
        embedding=embedding,
    )

    assert result == []
    mock_session.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_search_embedding_wrong_length_raises() -> None:
    from ia_investing.application.evidence import EvidenceRepository

    repo = EvidenceRepository(AsyncMock())
    with pytest.raises(ValueError, match="1536"):
        await repo.search(
            "receita líquida",
            datetime(2026, 7, 18, tzinfo=UTC),
            embedding=[0.1] * 100,
        )
