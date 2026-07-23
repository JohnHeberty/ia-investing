from datetime import date, datetime
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ._utils import utcnow
from .base import Base


class Scorecard(Base):
    """Scorecards por pilar para ranking de ações."""

    __tablename__ = "scorecards"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    issuer_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("issuers.id", ondelete="CASCADE"),
        nullable=False,
    )

    scorecard_type: Mapped[str] = mapped_column(sa.String(50))
    as_of_date: Mapped[date] = mapped_column(sa.Date, index=True)

    quality_score: Mapped[float] = mapped_column(sa.Float)
    growth_score: Mapped[float] = mapped_column(sa.Float)
    leverage_score: Mapped[float] = mapped_column(sa.Float)
    valuation_score: Mapped[float] = mapped_column(sa.Float)
    overall_score: Mapped[float] = mapped_column(sa.Float)

    veto_conditions_triggered: Mapped[dict[str, object]] = mapped_column(JSONB)

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=utcnow)

    def __repr__(self) -> str:
        return f"Scorecard(scorecard_type={self.scorecard_type!r}, overall_score={self.overall_score})"


class BacktestResult(Base):
    """Resultados de backtesting com point-in-time correctness."""

    __tablename__ = "backtest_results"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    strategy_name: Mapped[str] = mapped_column(sa.String(200))

    start_date: Mapped[date] = mapped_column(sa.Date)
    end_date: Mapped[date] = mapped_column(sa.Date)

    cagr_pct: Mapped[float] = mapped_column(sa.Float)
    sharpe_ratio: Mapped[float] = mapped_column(sa.Float)
    sortino_ratio: Mapped[float] = mapped_column(sa.Float)
    calmar_ratio: Mapped[float] = mapped_column(sa.Float)
    max_drawdown_pct: Mapped[float] = mapped_column(sa.Float)
    win_rate_pct: Mapped[float] = mapped_column(sa.Float)

    benchmark_name: Mapped[str] = mapped_column(sa.String(100))
    benchmark_cagr_pct: Mapped[float] = mapped_column(sa.Float)

    details: Mapped[dict[str, object]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=utcnow)

    def __repr__(self) -> str:
        return f"BacktestResult(strategy_name={self.strategy_name!r}, cagr_pct={self.cagr_pct})"
