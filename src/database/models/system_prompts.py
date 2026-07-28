from datetime import datetime
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from ._utils import utcnow
from .base import Base


class SystemPrompt(Base):
    __tablename__ = "system_prompts"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(sa.String(100), nullable=False)
    content: Mapped[str] = mapped_column(sa.Text, nullable=False)
    description: Mapped[str | None] = mapped_column(sa.String(500))
    version: Mapped[int] = mapped_column(sa.Integer, default=1)
    is_active: Mapped[bool] = mapped_column(sa.Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), onupdate=utcnow)

    def __repr__(self) -> str:
        return f"SystemPrompt(name={self.name!r}, version={self.version})"
