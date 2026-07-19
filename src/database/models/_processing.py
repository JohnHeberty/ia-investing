from datetime import UTC, datetime

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from .base import Base


class DocumentProcessingLog(Base):
    """Rastreabilidade do pipeline de processamento."""

    __tablename__ = "document_processing_log"

    id = sa.Column(UUID(as_uuid=True), primary_key=True, default=sa.func.gen_random_uuid())
    raw_document_id = sa.Column(
        UUID(as_uuid=True), sa.ForeignKey("raw_documents.id", ondelete="CASCADE"), nullable=False,
    )
    step_name = sa.Column(sa.String(100))  # "download", "hash_check", "parse", "validate"
    status = sa.Column(sa.String(20))  # "started", "success", "failed"
    error_message = sa.Column(sa.Text)
    duration_seconds = sa.Column(sa.Float)

    created_at = sa.Column(sa.DateTime(timezone=True), default=lambda: datetime.now(UTC))

    def __repr__(self) -> str:
        return f"DocumentProcessingLog(step_name={self.step_name!r}, status={self.status!r})"


class DocumentDuplicate(Base):
    """Deduplicação de documentos."""

    __tablename__ = "document_duplicates"

    id = sa.Column(UUID(as_uuid=True), primary_key=True, default=sa.func.gen_random_uuid())
    original_id = sa.Column(
        UUID(as_uuid=True), sa.ForeignKey("raw_documents.id", ondelete="CASCADE"), nullable=False,
    )
    duplicate_id = sa.Column(
        UUID(as_uuid=True), sa.ForeignKey("raw_documents.id", ondelete="CASCADE"), nullable=False,
    )

    similarity_method = sa.Column(sa.String(50))  # "sha256", "fuzzy_title"
    similarity_score = sa.Column(sa.Float)

    created_at = sa.Column(sa.DateTime(timezone=True), default=lambda: datetime.now(UTC))

    def __repr__(self) -> str:
        return f"DocumentDuplicate(similarity_method={self.similarity_method!r})"


class DocumentEvent(Base):
    """Eventos publicados pelo pipeline (document.downloaded, document.parsed, etc.)."""

    __tablename__ = "document_events"

    id = sa.Column(UUID(as_uuid=True), primary_key=True, default=sa.func.gen_random_uuid())
    raw_document_id = sa.Column(
        UUID(as_uuid=True), sa.ForeignKey("raw_documents.id", ondelete="CASCADE"), nullable=False,
    )
    event_type = sa.Column(sa.String(100))  # "document.downloaded", "document.parsed"

    payload = JSONB()

    created_at = sa.Column(sa.DateTime(timezone=True), default=lambda: datetime.now(UTC))

    def __repr__(self) -> str:
        return f"DocumentEvent(event_type={self.event_type!r})"
