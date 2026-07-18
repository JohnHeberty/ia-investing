from datetime import UTC, datetime

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from .base import Base


class FinancialStatement(Base):
    """Demonstrações financeiras normalizadas (DRE, Balanço Patrimonial, Fluxo de Caixa)."""

    __tablename__ = "financial_statements"

    id = sa.Column(UUID(as_uuid=True), primary_key=True, default=sa.func.gen_random_uuid())
    issuer_id = sa.Column(
        UUID(as_uuid=True), sa.ForeignKey("issuers.id", ondelete="CASCADE"), nullable=False,
    )
    document_id = sa.Column(
        UUID(as_uuid=True), sa.ForeignKey("documents.id", ondelete="SET NULL"),
    )

    statement_type = sa.Column(sa.String(20))  # "DRE", "BALANCE_SHEET", "CASH_FLOW"
    reporting_period_start = sa.Column(sa.Date, nullable=False)
    reporting_period_end = sa.Column(sa.Date, nullable=False)
    published_at = sa.Column(sa.DateTime(timezone=True), index=True)

    currency_code = sa.Column(sa.String(3))  # "BRL", "USD"
    scale_factor = sa.Column(sa.Integer)  # 1000 (milhares), 1 (unidades)

    line_items = JSONB()  # Dados normalizados: {"receita_liquida": 1e9, ...}
    raw_data = JSONB()  # Dados brutos do parser antes da normalização

    is_audited = sa.Column(sa.Boolean, default=False)
    restatement_flag = sa.Column(sa.Boolean, default=False)

    created_at = sa.Column(sa.DateTime(timezone=True), default=lambda: datetime.now(UTC))

    def __repr__(self) -> str:
        return (
            f"FinancialStatement(statement_type={self.statement_type!r}, "
            f"reporting_period_end={self.reporting_period_end!r})"
        )


class FinancialMetric(Base):
    """Métricas calculadas a partir das demonstrações financeiras."""

    __tablename__ = "financial_metrics"

    id = sa.Column(UUID(as_uuid=True), primary_key=True, default=sa.func.gen_random_uuid())
    issuer_id = sa.Column(
        UUID(as_uuid=True), sa.ForeignKey("issuers.id", ondelete="CASCADE"), nullable=False,
    )
    reporting_period_end = sa.Column(sa.Date, nullable=False)
    published_at = sa.Column(
        sa.DateTime(timezone=True), index=True
    )  # Point-in-time: quando ficou disponível

    metric_name = sa.Column(sa.String(100))  # "revenue_yoy", "ebitda_margin", "roic"
    category = sa.Column(
        sa.String(50)
    )  # "quality_growth", "leverage_debt", "valuation_multiple", "market_technical"

    value = sa.Column(sa.Numeric(20, 10))
    unit = sa.Column(sa.String(20))  # "%", "x", absolute

    previous_value = sa.Column(sa.Numeric(20, 10))
    change_absolute = sa.Column(sa.Numeric(20, 10))
    change_percent = sa.Column(sa.Numeric(20, 4))

    source_statement_id = sa.Column(
        UUID(as_uuid=True), sa.ForeignKey("financial_statements.id", ondelete="SET NULL"),
    )
    calculation_method = JSONB()  # Fórmula aplicada para auditoria

    created_at = sa.Column(sa.DateTime(timezone=True), default=lambda: datetime.now(UTC))

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

    id = sa.Column(UUID(as_uuid=True), primary_key=True, default=sa.func.gen_random_uuid())
    issuer_id = sa.Column(
        UUID(as_uuid=True), sa.ForeignKey("issuers.id", ondelete="CASCADE"), nullable=False,
    )
    ticker_symbol = sa.Column(sa.String(10))  # Ex: "PETR4"

    dividend_type = sa.Column(
        sa.String(20)
    )  # "DIVIDEND", "JSCP", "STOCK_DIVIDEND", "BUYBACK"

    announcement_date = sa.Column(sa.Date, index=True)
    ex_date = sa.Column(sa.Date, index=True)
    payment_date = sa.Column(sa.Date)

    amount_per_share = sa.Column(sa.Numeric(14, 6))
    total_amount = sa.Column(sa.Numeric(20, 2))

    source_url = sa.Column(sa.Text)

    created_at = sa.Column(sa.DateTime(timezone=True), default=lambda: datetime.now(UTC))

    def __repr__(self) -> str:
        return (
            f"Dividend(ticker_symbol={self.ticker_symbol!r}, "
            f"dividend_type={self.dividend_type!r}, ex_date={self.ex_date!r})"
        )


class ShareStatistics(Base):
    """Estatísticas de ações em circulação."""

    __tablename__ = "share_statistics"

    id = sa.Column(UUID(as_uuid=True), primary_key=True, default=sa.func.gen_random_uuid())
    issuer_id = sa.Column(
        UUID(as_uuid=True), sa.ForeignKey("issuers.id", ondelete="CASCADE"), nullable=False,
    )
    as_of_date = sa.Column(sa.Date, index=True)

    common_shares_outstanding = sa.Column(sa.BigInteger)
    preferred_shares_a = sa.Column(sa.BigInteger)
    preferred_shares_b = sa.Column(sa.BigInteger)
    total_shares_outstanding = sa.Column(sa.BigInteger)
    free_float_pct = sa.Column(sa.Numeric(5, 2))

    source_url = sa.Column(sa.Text)

    created_at = sa.Column(sa.DateTime(timezone=True), default=lambda: datetime.now(UTC))

    def __repr__(self) -> str:
        return f"ShareStatistics(issuer_id={self.issuer_id!r}, as_of_date={self.as_of_date!r})"


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

    created_at = sa.Column(sa.DateTime(timezone=True), default=lambda: datetime.now(UTC))

    def __repr__(self) -> str:
        return f"MacroIndicator(indicator_name={self.indicator_name!r}, period_date={self.period_date!r})"


class DataQualityCheck(Base):
    """Validações de qualidade dos dados."""

    __tablename__ = "data_quality_checks"

    id = sa.Column(UUID(as_uuid=True), primary_key=True, default=sa.func.gen_random_uuid())
    entity_type = sa.Column(sa.String(50))  # "financial_statement", "metric", "market_price"
    entity_id = sa.Column(UUID(as_uuid=True))

    check_name = sa.Column(sa.String(100))  # "balance_sheet_balances", "negative_revenue"
    passed = sa.Column(sa.Boolean, nullable=False)
    details = JSONB()

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
