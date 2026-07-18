from datetime import UTC, datetime

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from .base import Base


class PromptVersion(Base):
    """Versões dos prompts usados pelos agentes."""

    __tablename__ = "prompt_versions"

    id = sa.Column(UUID(as_uuid=True), primary_key=True, default=sa.func.gen_random_uuid())
    agent_name = sa.Column(sa.String(100))  # "filing_analyst", "news_analyst"
    version_number = sa.Column(sa.Integer)

    system_prompt = sa.Column(sa.Text)
    instructions_pt = sa.Column(sa.Text)
    structured_output_schema_id = sa.Column(UUID(as_uuid=True))

    is_active = sa.Column(sa.Boolean, default=False)
    created_at = sa.Column(sa.DateTime(timezone=True), default=lambda: datetime.now(UTC))

    def __repr__(self) -> str:
        return f"PromptVersion(agent_name={self.agent_name!r}, version_number={self.version_number})"


class WorkflowRun(Base):
    """Execuções de workflow (Temporal)."""

    __tablename__ = "workflow_runs"

    id = sa.Column(UUID(as_uuid=True), primary_key=True, default=sa.func.gen_random_uuid())
    temporal_workflow_id = sa.Column(sa.String(200))
    workflow_type = sa.Column(sa.String(100))  # "ingest_cvm", "analyze_filing"

    status = sa.Column(sa.String(20), default="running")  # "running", "completed", "failed"
    error_message = sa.Column(sa.Text)

    started_at = sa.Column(sa.DateTime(timezone=True), default=lambda: datetime.now(UTC))
    finished_at = sa.Column(sa.DateTime(timezone=True))

    def __repr__(self) -> str:
        return f"WorkflowRun(workflow_type={self.workflow_type!r}, status={self.status!r})"


class StructuredOutputSchema(Base):
    """Schemas de saída estruturada dos agentes."""

    __tablename__ = "structured_output_schemas"

    id = sa.Column(UUID(as_uuid=True), primary_key=True, default=sa.func.gen_random_uuid())
    name = sa.Column(sa.String(100))  # "filing_review", "news_analysis"
    version_number = sa.Column(sa.Integer)

    json_schema = JSONB()  # Schema JSON completo

    is_active = sa.Column(sa.Boolean, default=True)
    created_at = sa.Column(sa.DateTime(timezone=True), default=lambda: datetime.now(UTC))

    def __repr__(self) -> str:
        return f"StructuredOutputSchema(name={self.name!r}, version_number={self.version_number})"
