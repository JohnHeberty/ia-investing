from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ._utils import utcnow
from .base import Base


class FinancialStatement(Base):
    """Demonstrações financeiras normalizadas (DRE, Balanço Patrimonial, Fluxo de Caixa)."""

    __tablename__ = "financial_statements"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    issuer_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("issuers.id", ondelete="CASCADE"),
        nullable=False,
    )
    document_id: Mapped[UUID | None] = mapped_column(
        sa.ForeignKey("documents.id", ondelete="SET NULL"),
    )

    statement_type: Mapped[str | None] = mapped_column(sa.String(20))  # "DRE", "BALANCE_SHEET", "CASH_FLOW"
    reporting_period_start: Mapped[date] = mapped_column(sa.Date, nullable=False)
    reporting_period_end: Mapped[date] = mapped_column(sa.Date, nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), index=True)

    currency_code: Mapped[str | None] = mapped_column(sa.String(3))  # "BRL", "USD"
    scale_factor: Mapped[int | None] = mapped_column(sa.Integer)  # 1000 (milhares), 1 (unidades)

    # Dados normalizados: {"receita_liquida": 1e9, ...}
    line_items: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    # Dados brutos do parser antes da normalização
    raw_data: Mapped[dict[str, object] | None] = mapped_column(JSONB)

    is_audited: Mapped[bool | None] = mapped_column(sa.Boolean, default=False)
    restatement_flag: Mapped[bool | None] = mapped_column(sa.Boolean, default=False)

    created_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), default=utcnow)

    __table_args__ = (
        sa.UniqueConstraint(
            "issuer_id",
            "statement_type",
            "reporting_period_end",
            name="uq_financial_statements_issuer_type_period",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"FinancialStatement(statement_type={self.statement_type!r}, "
            f"reporting_period_end={self.reporting_period_end!r})"
        )


class FinancialMetric(Base):
    """Métricas calculadas a partir das demonstrações financeiras."""

    __tablename__ = "financial_metrics"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    issuer_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("issuers.id", ondelete="CASCADE"),
        nullable=False,
    )
    reporting_period_end: Mapped[date] = mapped_column(sa.Date, nullable=False)
    # Point-in-time: quando ficou disponível
    published_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), index=True)

    # "revenue_yoy", "ebitda_margin", "roic"
    metric_name: Mapped[str | None] = mapped_column(sa.String(100))
    # "quality_growth", "leverage_debt", "valuation_multiple", "market_technical"
    category: Mapped[str | None] = mapped_column(sa.String(50))

    value: Mapped[Decimal | None] = mapped_column(sa.Numeric(20, 10))
    unit: Mapped[str | None] = mapped_column(sa.String(20))  # "%", "x", absolute

    previous_value: Mapped[Decimal | None] = mapped_column(sa.Numeric(20, 10))
    change_absolute: Mapped[Decimal | None] = mapped_column(sa.Numeric(20, 10))
    change_percent: Mapped[Decimal | None] = mapped_column(sa.Numeric(20, 4))

    source_statement_id: Mapped[UUID | None] = mapped_column(
        sa.ForeignKey("financial_statements.id", ondelete="SET NULL"),
    )
    calculation_method: Mapped[dict[str, object] | None] = mapped_column(JSONB)  # Fórmula aplicada para auditoria

    created_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), default=utcnow)

    __table_args__ = (
        sa.Index("ix_financial_metrics_issuer_metric_period", "issuer_id", "metric_name", "reporting_period_end"),
    )

    def __repr__(self) -> str:
        return (
            f"FinancialMetric(metric_name={self.metric_name!r}, value={self.value}, "
            f"reporting_period_end={self.reporting_period_end!r})"
        )


class Dividend(Base):
    """Dados de dividendos e proventos."""

    __tablename__ = "dividends"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    issuer_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("issuers.id", ondelete="CASCADE"),
        nullable=False,
    )
    ticker_symbol: Mapped[str | None] = mapped_column(sa.String(10))  # Ex: "PETR4"

    dividend_type: Mapped[str | None] = mapped_column(sa.String(20))  # "DIVIDEND", "JSCP", "STOCK_DIVIDEND", "BUYBACK"

    announcement_date: Mapped[date | None] = mapped_column(sa.Date, index=True)
    ex_date: Mapped[date | None] = mapped_column(sa.Date, index=True)
    payment_date: Mapped[date | None] = mapped_column(sa.Date)

    amount_per_share: Mapped[Decimal | None] = mapped_column(sa.Numeric(14, 6))
    total_amount: Mapped[Decimal | None] = mapped_column(sa.Numeric(20, 2))

    source_url: Mapped[str | None] = mapped_column(sa.Text)

    created_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), default=utcnow)

    def __repr__(self) -> str:
        return (
            f"Dividend(ticker_symbol={self.ticker_symbol!r}, "
            f"dividend_type={self.dividend_type!r}, ex_date={self.ex_date!r})"
        )


class ShareStatistics(Base):
    """Estatísticas de ações em circulação."""

    __tablename__ = "share_statistics"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    issuer_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("issuers.id", ondelete="CASCADE"),
        nullable=False,
    )
    as_of_date: Mapped[date | None] = mapped_column(sa.Date, index=True)

    common_shares_outstanding: Mapped[int | None] = mapped_column(sa.BigInteger)
    preferred_shares_a: Mapped[int | None] = mapped_column(sa.BigInteger)
    preferred_shares_b: Mapped[int | None] = mapped_column(sa.BigInteger)
    total_shares_outstanding: Mapped[int | None] = mapped_column(sa.BigInteger)
    free_float_pct: Mapped[Decimal | None] = mapped_column(sa.Numeric(5, 2))

    source_url: Mapped[str | None] = mapped_column(sa.Text)

    created_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), default=utcnow)

    def __repr__(self) -> str:
        return f"ShareStatistics(issuer_id={self.issuer_id!r}, as_of_date={self.as_of_date!r})"
