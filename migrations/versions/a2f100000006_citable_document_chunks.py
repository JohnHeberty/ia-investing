"""citable point-in-time document chunks

Revision ID: a2f100000006
Revises: a2f100000005
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "a2f100000006"
down_revision: str | Sequence[str] | None = "a2f100000005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "document_chunks",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("source_object_version_id", sa.UUID(), nullable=False),
        sa.Column("document_id", sa.UUID(), nullable=True),
        sa.Column("page_start", sa.Integer(), nullable=False),
        sa.Column("page_end", sa.Integer(), nullable=False),
        sa.Column("section_path", postgresql.ARRAY(sa.Text()), nullable=False),
        sa.Column("table_reference", sa.String(200), nullable=True),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("content_sha256", sa.String(64), nullable=False),
        sa.Column("knowledge_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("embedding", Vector(1536), nullable=True),
        sa.Column("embedding_model", sa.String(100), nullable=True),
        sa.Column("embedding_version", sa.String(50), nullable=True),
        sa.Column("embedding_dimension", sa.Integer(), nullable=True),
        sa.Column(
            "search_tsv",
            postgresql.TSVECTOR(),
            sa.Computed("to_tsvector('portuguese', coalesce(text, ''))", persisted=True),
            nullable=False,
        ),
        sa.CheckConstraint("content_sha256 ~ '^[0-9a-f]{64}$'", name=op.f("ck_document_chunks_sha256_format")),
        sa.CheckConstraint(
            "(embedding IS NULL AND embedding_model IS NULL AND embedding_version IS NULL "
            "AND embedding_dimension IS NULL) OR (embedding IS NOT NULL AND embedding_model IS NOT NULL "
            "AND embedding_version IS NOT NULL AND embedding_dimension = 1536)",
            name=op.f("ck_document_chunks_embedding_metadata_complete"),
        ),
        sa.CheckConstraint("ordinal >= 0", name=op.f("ck_document_chunks_nonnegative_ordinal")),
        sa.CheckConstraint("page_start > 0 AND page_end >= page_start", name=op.f("ck_document_chunks_valid_pages")),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            name=op.f("fk_document_chunks_document_id_documents"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["source_object_version_id"],
            ["source_object_versions.id"],
            name=op.f("fk_document_chunks_source_object_version_id_source_object_versions"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_document_chunks")),
        sa.UniqueConstraint(
            "source_object_version_id", "content_sha256", "ordinal", name="uq_document_chunks_source_hash_ordinal"
        ),
    )
    op.create_index(op.f("ix_document_chunks_document_id"), "document_chunks", ["document_id"])
    op.create_index(op.f("ix_document_chunks_knowledge_at"), "document_chunks", ["knowledge_at"])
    op.create_index(
        op.f("ix_document_chunks_source_object_version_id"), "document_chunks", ["source_object_version_id"]
    )
    op.create_index("ix_document_chunks_search_tsv", "document_chunks", ["search_tsv"], postgresql_using="gin")
    op.execute(
        "CREATE INDEX ix_document_chunks_embedding_hnsw ON document_chunks "
        "USING hnsw (embedding vector_cosine_ops) WHERE embedding IS NOT NULL"
    )


def downgrade() -> None:
    op.drop_index("ix_document_chunks_embedding_hnsw", table_name="document_chunks")
    op.drop_index("ix_document_chunks_search_tsv", table_name="document_chunks")
    op.drop_index(op.f("ix_document_chunks_source_object_version_id"), table_name="document_chunks")
    op.drop_index(op.f("ix_document_chunks_knowledge_at"), table_name="document_chunks")
    op.drop_index(op.f("ix_document_chunks_document_id"), table_name="document_chunks")
    op.drop_table("document_chunks")
