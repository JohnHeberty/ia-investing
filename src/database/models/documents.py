from datetime import UTC, datetime

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from .base import Base


class RawDocument(Base):
    """Raw Zone: arquivos brutos preservados antes de qualquer transformação."""

    __tablename__ = "raw_documents"

    id = sa.Column(UUID(as_uuid=True), primary_key=True, default=sa.func.gen_random_uuid())
    issuer_id = sa.Column(
        UUID(as_uuid=True), sa.ForeignKey("issuers.id", ondelete="SET NULL"),
    )
    source_url = sa.Column(sa.Text)
    document_type = sa.Column(
        sa.String(50),  # "DFP", "ITR", "FRE", "FCA", "IPE", "PRESS_RELEASE"
        nullable=False,
    )

    storage_path = sa.Column(sa.Text)  # S3/MinIO path do arquivo original
    content_type = sa.Column(sa.String(100))  # MIME type: application/pdf, text/html...
    file_size_bytes = sa.Column(sa.BigInteger)

    sha256_hash = sa.Column(sa.String(64), index=True)
    http_etag = sa.Column(sa.Text)
    http_last_modified = sa.Column(sa.DateTime(timezone=True))

    retrieved_at = sa.Column(
        sa.DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    published_at = sa.Column(sa.DateTime(timezone=True))  # Data de publicação do documento

    reporting_period_start = sa.Column(sa.Date, index=True)
    reporting_period_end = sa.Column(sa.Date, index=True)

    parser_version = sa.Column(sa.String(50))
    license_policy = sa.Column(sa.Text)

    created_at = sa.Column(sa.DateTime(timezone=True), default=lambda: datetime.now(UTC))

    def __repr__(self) -> str:
        return f"RawDocument(document_type={self.document_type!r}, sha256_hash={self.sha256_hash!r})"


class DocumentMetadata(Base):
    """Metadados extraídos do documento após parsing."""

    __tablename__ = "document_metadata"

    id = sa.Column(UUID(as_uuid=True), primary_key=True, default=sa.func.gen_random_uuid())
    raw_document_id = sa.Column(
        UUID(as_uuid=True), sa.ForeignKey("raw_documents.id", ondelete="CASCADE"), nullable=False,
    )
    issuer_id = sa.Column(
        UUID(as_uuid=True), sa.ForeignKey("issuers.id", ondelete="SET NULL"),
    )

    title = sa.Column(sa.Text)
    summary = sa.Column(sa.Text)
    page_count = sa.Column(sa.Integer)
    language = sa.Column(sa.String(10))  # "pt", "en"

    parsed_data = JSONB()  # Dados estruturados extraídos pelo parser
    extraction_errors = sa.Column(JSONB)  # Erros encontrados durante parsing

    is_validated = sa.Column(sa.Boolean, default=False)
    validation_notes = sa.Column(sa.Text)

    created_at = sa.Column(sa.DateTime(timezone=True), default=lambda: datetime.now(UTC))

    def __repr__(self) -> str:
        return f"DocumentMetadata(title={self.title!r}, is_validated={self.is_validated})"


class Document(Base):
    """Dados canônicos após validação — a fonte de verdade."""

    __tablename__ = "documents"

    id = sa.Column(UUID(as_uuid=True), primary_key=True, default=sa.func.gen_random_uuid())
    raw_document_id = sa.Column(
        UUID(as_uuid=True), sa.ForeignKey("raw_documents.id", ondelete="CASCADE"), nullable=False,
    )
    issuer_id = sa.Column(
        UUID(as_uuid=True), sa.ForeignKey("issuers.id", ondelete="SET NULL"),
    )

    document_type = sa.Column(sa.String(50))
    reporting_period_start = sa.Column(sa.Date)
    reporting_period_end = sa.Column(sa.Date)
    published_at = sa.Column(sa.DateTime(timezone=True))  # Data de publicação oficial

    canonical_data = JSONB()  # Dados canônicos validados e normalizados

    created_at = sa.Column(sa.DateTime(timezone=True), default=lambda: datetime.now(UTC))

    def __repr__(self) -> str:
        return f"Document(document_type={self.document_type!r}, reporting_period_end={self.reporting_period_end!r})"
