from datetime import datetime
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ._utils import utcnow
from .base import Base


class PromptVersion(Base):
    """Versões dos prompts usados pelos agentes."""

    __tablename__ = "prompt_versions"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    agent_name: Mapped[str | None] = mapped_column(sa.String(100))  # "filing_analyst", "news_analyst"
    version_number: Mapped[int | None] = mapped_column(sa.Integer)

    system_prompt: Mapped[str | None] = mapped_column(sa.Text)
    instructions_pt: Mapped[str | None] = mapped_column(sa.Text)
    structured_output_schema_id: Mapped[UUID | None] = mapped_column()

    is_active: Mapped[bool | None] = mapped_column(sa.Boolean, default=False)
    created_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), default=utcnow)

    def __repr__(self) -> str:
        return f"PromptVersion(agent_name={self.agent_name!r}, version_number={self.version_number})"


class WorkflowRun(Base):
    """Execuções de workflow (Temporal)."""

    __tablename__ = "workflow_runs"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    temporal_workflow_id: Mapped[str | None] = mapped_column(sa.String(200))
    workflow_type: Mapped[str | None] = mapped_column(sa.String(100))  # "ingest_cvm", "analyze_filing"

    status: Mapped[str | None] = mapped_column(sa.String(20), default="running")  # "running", "completed", "failed"
    error_message: Mapped[str | None] = mapped_column(sa.Text)

    started_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))

    def __repr__(self) -> str:
        return f"WorkflowRun(workflow_type={self.workflow_type!r}, status={self.status!r})"


class StructuredOutputSchema(Base):
    """Schemas de saída estruturada dos agentes."""

    __tablename__ = "structured_output_schemas"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str | None] = mapped_column(sa.String(100))  # "filing_review", "news_analysis"
    version_number: Mapped[int | None] = mapped_column(sa.Integer)

    json_schema: Mapped[dict[str, object] | None] = mapped_column(JSONB)  # Schema JSON completo

    is_active: Mapped[bool | None] = mapped_column(sa.Boolean, default=True)
    created_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), default=utcnow)

    def __repr__(self) -> str:
        return f"StructuredOutputSchema(name={self.name!r}, version_number={self.version_number})"
