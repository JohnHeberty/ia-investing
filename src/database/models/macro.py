from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from ._utils import utcnow
from .base import Base


class MacroIndicator(Base):
    """Indicadores macroeconômicos (Banco Central, IBGE)."""

    __tablename__ = "macro_indicators"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    indicator_name: Mapped[str] = mapped_column(sa.String(100))
    source: Mapped[str] = mapped_column(sa.String(50))

    period_date: Mapped[date] = mapped_column(sa.Date, index=True)
    value: Mapped[Decimal] = mapped_column(sa.Numeric(20, 10))
    unit: Mapped[str] = mapped_column(sa.String(20))

    published_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), index=True)

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=utcnow)

    def __repr__(self) -> str:
        return f"MacroIndicator(indicator_name={self.indicator_name!r}, period_date={self.period_date!r})"
