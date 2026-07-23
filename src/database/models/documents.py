from datetime import date, datetime
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ._utils import utcnow
from .base import Base


class RawDocument(Base):
    """Raw Zone: arquivos brutos preservados antes de qualquer transformação."""

    __tablename__ = "raw_documents"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    issuer_id: Mapped[UUID | None] = mapped_column(
        sa.ForeignKey("issuers.id", ondelete="SET NULL"),
    )
    source_url: Mapped[str | None] = mapped_column(sa.Text)
    document_type: Mapped[str] = mapped_column(
        sa.String(50),  # "DFP", "ITR", "FRE", "FCA", "IPE", "PRESS_RELEASE"
        nullable=False,
    )

    storage_path: Mapped[str | None] = mapped_column(sa.Text)  # S3/MinIO path do arquivo original
    content_type: Mapped[str | None] = mapped_column(sa.String(100))  # MIME type: application/pdf, text/html...
    file_size_bytes: Mapped[int | None] = mapped_column(sa.BigInteger)

    sha256_hash: Mapped[str | None] = mapped_column(sa.String(64), index=True)
    http_etag: Mapped[str | None] = mapped_column(sa.Text)
    http_last_modified: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))

    retrieved_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), default=utcnow)
    published_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))  # Data de publicação do documento

    reporting_period_start: Mapped[date | None] = mapped_column(sa.Date, index=True)
    reporting_period_end: Mapped[date | None] = mapped_column(sa.Date, index=True)

    parser_version: Mapped[str | None] = mapped_column(sa.String(50))
    license_policy: Mapped[str | None] = mapped_column(sa.Text)

    created_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), default=utcnow)

    def __repr__(self) -> str:
        return f"RawDocument(document_type={self.document_type!r}, sha256_hash={self.sha256_hash!r})"


class DocumentMetadata(Base):
    """Metadados extraídos do documento após parsing."""

    __tablename__ = "document_metadata"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    raw_document_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("raw_documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    issuer_id: Mapped[UUID | None] = mapped_column(
        sa.ForeignKey("issuers.id", ondelete="SET NULL"),
    )

    title: Mapped[str | None] = mapped_column(sa.Text)
    summary: Mapped[str | None] = mapped_column(sa.Text)
    page_count: Mapped[int | None] = mapped_column(sa.Integer)
    language: Mapped[str | None] = mapped_column(sa.String(10))  # "pt", "en"

    parsed_data: Mapped[dict[str, object] | None] = mapped_column(JSONB)  # Dados estruturados extraídos pelo parser
    extraction_errors: Mapped[dict[str, object] | None] = mapped_column(JSONB)  # Erros encontrados durante parsing

    is_validated: Mapped[bool | None] = mapped_column(sa.Boolean, default=False)
    validation_notes: Mapped[str | None] = mapped_column(sa.Text)

    created_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), default=utcnow)

    def __repr__(self) -> str:
        return f"DocumentMetadata(title={self.title!r}, is_validated={self.is_validated})"


class Document(Base):
    """Dados canônicos após validação — a fonte de verdade."""

    __tablename__ = "documents"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    raw_document_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("raw_documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    issuer_id: Mapped[UUID | None] = mapped_column(
        sa.ForeignKey("issuers.id", ondelete="SET NULL"),
    )

    document_type: Mapped[str | None] = mapped_column(sa.String(50))
    reporting_period_start: Mapped[date | None] = mapped_column(sa.Date)
    reporting_period_end: Mapped[date | None] = mapped_column(sa.Date)
    published_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))  # Data de publicação oficial

    canonical_data: Mapped[dict[str, object] | None] = mapped_column(JSONB)  # Dados canônicos validados e normalizados

    created_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), default=utcnow)

    def __repr__(self) -> str:
        return f"Document(document_type={self.document_type!r}, reporting_period_end={self.reporting_period_end!r})"
