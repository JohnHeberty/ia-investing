import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from ._utils import utcnow
from .base import Base


class MacroIndicator(Base):
    """Indicadores macroeconômicos (Banco Central, IBGE)."""

    __tablename__ = "macro_indicators"

    id = sa.Column(UUID(as_uuid=True), primary_key=True, default=sa.func.gen_random_uuid())
    indicator_name = sa.Column(sa.String(100))  # "selic", "ipca", "usd_brl"
    source = sa.Column(sa.String(50))  # "BCB", "IBGE", "SIDRA"

    period_date = sa.Column(sa.Date, index=True)
    value = sa.Column(sa.Numeric(20, 10))
    unit = sa.Column(sa.String(20))

    published_at = sa.Column(sa.DateTime(timezone=True), index=True)

    created_at = sa.Column(sa.DateTime(timezone=True), default=utcnow)

    def __repr__(self) -> str:
        return f"MacroIndicator(indicator_name={self.indicator_name!r}, period_date={self.period_date!r})"
