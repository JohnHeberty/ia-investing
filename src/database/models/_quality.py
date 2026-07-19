from datetime import UTC, datetime

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from .base import Base


class DataQualityCheck(Base):
    """Validações de qualidade dos dados."""

    __tablename__ = "data_quality_checks"

    id = sa.Column(UUID(as_uuid=True), primary_key=True, default=sa.func.gen_random_uuid())
    entity_type = sa.Column(sa.String(50))  # "financial_statement", "metric", "market_price"
    entity_id = sa.Column(UUID(as_uuid=True))

    check_name = sa.Column(sa.String(100))  # "balance_sheet_balances", "negative_revenue"
    passed = sa.Column(sa.Boolean, nullable=False)
    details = sa.Column(JSONB)

    created_at = sa.Column(sa.DateTime(timezone=True), default=lambda: datetime.now(UTC))

    def __repr__(self) -> str:
        return f"DataQualityCheck(check_name={self.check_name!r}, passed={self.passed})"


class DataRefreshLog(Base):
    """Registro de atualizações e refreshes dos dados."""

    __tablename__ = "data_refresh_log"

    id = sa.Column(UUID(as_uuid=True), primary_key=True, default=sa.func.gen_random_uuid())
    source_name = sa.Column(sa.String(100))  # "CVM", "B3", "BCB"
    entity_type = sa.Column(sa.String(50))

    records_fetched = sa.Column(sa.Integer)
    records_inserted = sa.Column(sa.Integer, default=0)
    records_updated = sa.Column(sa.Integer, default=0)
    status = sa.Column(sa.String(20))  # "success", "partial_failure", "failed"
    error_message = sa.Column(sa.Text)

    started_at = sa.Column(sa.DateTime(timezone=True), default=lambda: datetime.now(UTC))
    finished_at = sa.Column(sa.DateTime(timezone=True))

    def __repr__(self) -> str:
        return f"DataRefreshLog(source_name={self.source_name!r}, status={self.status!r})"
