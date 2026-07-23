import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from ._utils import utcnow
from .base import Base


class Scorecard(Base):
    """Scorecards por pilar para ranking de ações."""

    __tablename__ = "scorecards"

    id = sa.Column(UUID(as_uuid=True), primary_key=True, default=sa.func.gen_random_uuid())
    issuer_id = sa.Column(
        UUID(as_uuid=True),
        sa.ForeignKey("issuers.id", ondelete="CASCADE"),
        nullable=False,
    )

    scorecard_type = sa.Column(sa.String(50))  # "bank", "industrial", "utility"
    as_of_date = sa.Column(sa.Date, index=True)

    quality_score = sa.Column(sa.Float)
    growth_score = sa.Column(sa.Float)
    leverage_score = sa.Column(sa.Float)
    valuation_score = sa.Column(sa.Float)
    overall_score = sa.Column(sa.Float)

    veto_conditions_triggered = sa.Column(JSONB)  # Condições de veto ativadas

    created_at = sa.Column(sa.DateTime(timezone=True), default=utcnow)

    def __repr__(self) -> str:
        return f"Scorecard(scorecard_type={self.scorecard_type!r}, overall_score={self.overall_score})"


class BacktestResult(Base):
    """Resultados de backtesting com point-in-time correctness."""

    __tablename__ = "backtest_results"

    id = sa.Column(UUID(as_uuid=True), primary_key=True, default=sa.func.gen_random_uuid())
    strategy_name = sa.Column(sa.String(200))

    start_date = sa.Column(sa.Date)
    end_date = sa.Column(sa.Date)

    cagr_pct = sa.Column(sa.Float)
    sharpe_ratio = sa.Column(sa.Float)
    sortino_ratio = sa.Column(sa.Float)
    calmar_ratio = sa.Column(sa.Float)
    max_drawdown_pct = sa.Column(sa.Float)
    win_rate_pct = sa.Column(sa.Float)

    benchmark_name = sa.Column(sa.String(100))  # "IBOVESPA"
    benchmark_cagr_pct = sa.Column(sa.Float)

    details = sa.Column(JSONB)
    created_at = sa.Column(sa.DateTime(timezone=True), default=utcnow)

    def __repr__(self) -> str:
        return f"BacktestResult(strategy_name={self.strategy_name!r}, cagr_pct={self.cagr_pct})"
