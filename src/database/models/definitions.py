from datetime import datetime
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ._utils import utcnow
from .base import Base


class AgentDefinition(Base):
    __tablename__ = "agent_definitions"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(sa.String(100), nullable=False)
    display_name_pt: Mapped[str] = mapped_column(sa.String(200))

    system_prompt_id: Mapped[UUID] = mapped_column()
    model_config: Mapped[dict[str, object]] = mapped_column(JSONB)

    is_active: Mapped[bool] = mapped_column(sa.Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=utcnow)

    def __repr__(self) -> str:
        return f"AgentDefinition(name={self.name!r}, is_active={self.is_active})"


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    agent_definition_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("agent_definitions.id", ondelete="CASCADE"),
        nullable=False,
    )

    input_data: Mapped[dict[str, object]] = mapped_column(JSONB)
    output_data: Mapped[dict[str, object]] = mapped_column(JSONB)

    model_used: Mapped[str] = mapped_column(sa.String(100))
    tokens_prompt: Mapped[int] = mapped_column(sa.Integer)
    tokens_completion: Mapped[int] = mapped_column(sa.Integer)
    cost_usd: Mapped[float] = mapped_column(sa.Float)

    status: Mapped[str] = mapped_column(sa.String(20), default="running")
    error_message: Mapped[str] = mapped_column(sa.Text)

    started_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True))

    def __repr__(self) -> str:
        return f"AgentRun(status={self.status!r}, model_used={self.model_used!r})"


class AgentToolCall(Base):
    __tablename__ = "agent_tool_calls"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    agent_run_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("agent_runs.id", ondelete="CASCADE"),
        nullable=False,
    )

    tool_name: Mapped[str] = mapped_column(sa.String(100))
    input_params: Mapped[dict[str, object]] = mapped_column(JSONB)
    output_result: Mapped[dict[str, object]] = mapped_column(JSONB)

    status: Mapped[str] = mapped_column(sa.String(20))
    duration_ms: Mapped[float] = mapped_column(sa.Float)
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=utcnow)

    def __repr__(self) -> str:
        return f"AgentToolCall(tool_name={self.tool_name!r}, status={self.status!r})"
