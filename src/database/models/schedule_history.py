from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ._utils import utcnow
from .base import Base


class ScheduleRunHistory(Base):
    __tablename__ = "schedule_run_history"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    schedule_id: Mapped[str] = mapped_column(sa.String(200), nullable=False, index=True)
    workflow_id: Mapped[str | None] = mapped_column(sa.String(200))
    status: Mapped[str] = mapped_column(sa.String(20), nullable=False, default="running")
    started_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    result_summary: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    error_message: Mapped[str | None] = mapped_column(sa.Text)
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=utcnow)

    __table_args__ = (
        sa.CheckConstraint("status IN ('running','completed','failed')", name="ck_schedule_run_history_status"),
        sa.UniqueConstraint("schedule_id", "workflow_id", name="uq_schedule_run_history_schedule_workflow"),
    )

    def __repr__(self) -> str:
        return f"ScheduleRunHistory(schedule_id={self.schedule_id!r}, status={self.status!r})"
