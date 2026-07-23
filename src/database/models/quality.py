from datetime import datetime
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ._utils import utcnow
from .base import Base


class DataQualityCheck(Base):
    """Validações de qualidade dos dados."""

    __tablename__ = "data_quality_checks"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    entity_type: Mapped[str | None] = mapped_column(sa.String(50))  # "financial_statement", "metric", "market_price"
    entity_id: Mapped[UUID | None] = mapped_column()
    check_name: Mapped[str | None] = mapped_column(sa.String(100))  # "balance_sheet_balances", "negative_revenue"
    passed: Mapped[bool] = mapped_column(sa.Boolean, nullable=False)
    details: Mapped[dict[str, object] | None] = mapped_column(JSONB)

    created_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), default=utcnow)

    def __repr__(self) -> str:
        return f"DataQualityCheck(check_name={self.check_name!r}, passed={self.passed})"


class DataRefreshLog(Base):
    """Registro de atualizações e refreshes dos dados."""

    __tablename__ = "data_refresh_log"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    source_name: Mapped[str | None] = mapped_column(sa.String(100))  # "CVM", "B3", "BCB"
    entity_type: Mapped[str | None] = mapped_column(sa.String(50))

    records_fetched: Mapped[int | None] = mapped_column(sa.Integer)
    records_inserted: Mapped[int | None] = mapped_column(sa.Integer, default=0)
    records_updated: Mapped[int | None] = mapped_column(sa.Integer, default=0)
    status: Mapped[str | None] = mapped_column(sa.String(20))  # "success", "partial_failure", "failed"
    error_message: Mapped[str | None] = mapped_column(sa.Text)

    started_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))

    def __repr__(self) -> str:
        return f"DataRefreshLog(source_name={self.source_name!r}, status={self.status!r})"
