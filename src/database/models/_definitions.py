from datetime import UTC, datetime

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from .base import Base


class AgentDefinition(Base):
    __tablename__ = "agent_definitions"

    id = sa.Column(UUID(as_uuid=True), primary_key=True, default=sa.func.gen_random_uuid())
    name = sa.Column(sa.String(100), nullable=False)  # "filing_analyst", "news_analyst"
    display_name_pt = sa.Column(sa.String(200))

    system_prompt_id = sa.Column(UUID(as_uuid=True))
    model_config = JSONB()

    is_active = sa.Column(sa.Boolean, default=True)
    created_at = sa.Column(sa.DateTime(timezone=True), default=lambda: datetime.now(UTC))

    def __repr__(self) -> str:
        return f"AgentDefinition(name={self.name!r}, is_active={self.is_active})"


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id = sa.Column(UUID(as_uuid=True), primary_key=True, default=sa.func.gen_random_uuid())
    agent_definition_id = sa.Column(
        UUID(as_uuid=True), sa.ForeignKey("agent_definitions.id", ondelete="CASCADE"),
        nullable=False,
    )

    input_data = JSONB()
    output_data = JSONB()

    model_used = sa.Column(sa.String(100))
    tokens_prompt = sa.Column(sa.Integer)
    tokens_completion = sa.Column(sa.Integer)
    cost_usd = sa.Column(sa.Float)

    status = sa.Column(sa.String(20), default="running")  # "running", "completed", "failed"
    error_message = sa.Column(sa.Text)

    started_at = sa.Column(sa.DateTime(timezone=True), default=lambda: datetime.now(UTC))
    finished_at = sa.Column(sa.DateTime(timezone=True))

    def __repr__(self) -> str:
        return f"AgentRun(status={self.status!r}, model_used={self.model_used!r})"


class AgentToolCall(Base):
    __tablename__ = "agent_tool_calls"

    id = sa.Column(UUID(as_uuid=True), primary_key=True, default=sa.func.gen_random_uuid())
    agent_run_id = sa.Column(
        UUID(as_uuid=True), sa.ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=False,
    )

    tool_name = sa.Column(sa.String(100))
    input_params = JSONB()
    output_result = JSONB()

    status = sa.Column(sa.String(20))  # "success", "failed"
    duration_ms = sa.Column(sa.Float)
    created_at = sa.Column(sa.DateTime(timezone=True), default=lambda: datetime.now(UTC))

    def __repr__(self) -> str:
        return f"AgentToolCall(tool_name={self.tool_name!r}, status={self.status!r})"
