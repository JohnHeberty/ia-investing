from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import ARRAY, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    source_object_version_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("source_object_versions.id", ondelete="RESTRICT"), index=True
    )
    document_id: Mapped[UUID | None] = mapped_column(sa.ForeignKey("documents.id", ondelete="SET NULL"), index=True)
    page_start: Mapped[int]
    page_end: Mapped[int]
    section_path: Mapped[list[str]] = mapped_column(ARRAY(sa.Text), default=list)
    table_reference: Mapped[str | None] = mapped_column(sa.String(200))
    ordinal: Mapped[int]
    text: Mapped[str] = mapped_column(sa.Text)
    content_sha256: Mapped[str] = mapped_column(sa.String(64))
    knowledge_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), index=True)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1536))
    embedding_model: Mapped[str | None] = mapped_column(sa.String(100))
    embedding_version: Mapped[str | None] = mapped_column(sa.String(50))
    embedding_dimension: Mapped[int | None]
    search_tsv: Mapped[object] = mapped_column(
        TSVECTOR,
        sa.Computed("to_tsvector('portuguese', coalesce(text, ''))", persisted=True),
    )

    __table_args__ = (
        sa.Index("ix_document_chunks_search_tsv", "search_tsv", postgresql_using="gin"),
        sa.Index(
            "ix_document_chunks_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
            postgresql_where=sa.text("embedding IS NOT NULL"),
        ),
        sa.UniqueConstraint(
            "source_object_version_id", "content_sha256", "ordinal", name="uq_document_chunks_source_hash_ordinal"
        ),
        sa.CheckConstraint("page_start > 0 AND page_end >= page_start", name="valid_pages"),
        sa.CheckConstraint("ordinal >= 0", name="nonnegative_ordinal"),
        sa.CheckConstraint("content_sha256 ~ '^[0-9a-f]{64}$'", name="sha256_format"),
        sa.CheckConstraint(
            "(embedding IS NULL AND embedding_model IS NULL AND embedding_version IS NULL "
            "AND embedding_dimension IS NULL) OR (embedding IS NOT NULL AND embedding_model IS NOT NULL "
            "AND embedding_version IS NOT NULL AND embedding_dimension = 1536)",
            name="embedding_metadata_complete",
        ),
    )
