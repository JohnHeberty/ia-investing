from datetime import datetime
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ._utils import utcnow
from .base import Base


class DocumentProcessingLog(Base):
    """Rastreabilidade do pipeline de processamento."""

    __tablename__ = "document_processing_log"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    raw_document_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("raw_documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    step_name: Mapped[str | None] = mapped_column(sa.String(100))  # "download", "hash_check", "parse", "validate"
    status: Mapped[str | None] = mapped_column(sa.String(20))  # "started", "success", "failed"
    error_message: Mapped[str | None] = mapped_column(sa.Text)
    duration_seconds: Mapped[float | None] = mapped_column(sa.Float)

    created_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), default=utcnow)

    def __repr__(self) -> str:
        return f"DocumentProcessingLog(step_name={self.step_name!r}, status={self.status!r})"


class DocumentDuplicate(Base):
    """Deduplicação de documentos."""

    __tablename__ = "document_duplicates"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    original_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("raw_documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    duplicate_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("raw_documents.id", ondelete="CASCADE"),
        nullable=False,
    )

    similarity_method: Mapped[str | None] = mapped_column(sa.String(50))  # "sha256", "fuzzy_title"
    similarity_score: Mapped[float | None] = mapped_column(sa.Float)

    created_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), default=utcnow)

    def __repr__(self) -> str:
        return f"DocumentDuplicate(similarity_method={self.similarity_method!r})"


class DocumentEvent(Base):
    """Eventos publicados pelo pipeline (document.downloaded, document.parsed, etc.)."""

    __tablename__ = "document_events"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    raw_document_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("raw_documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    event_type: Mapped[str | None] = mapped_column(sa.String(100))  # "document.downloaded", "document.parsed"

    payload: Mapped[dict[str, object] | None] = mapped_column(JSONB)

    created_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), default=utcnow)

    def __repr__(self) -> str:
        return f"DocumentEvent(event_type={self.event_type!r})"
