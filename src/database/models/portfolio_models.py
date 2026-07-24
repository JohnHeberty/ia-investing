from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ._utils import utcnow
from .base import Base


class Portfolio(Base):
    __tablename__ = "portfolios"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID | None] = mapped_column(
        sa.ForeignKey("organizations.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    name: Mapped[str] = mapped_column(sa.String(200), nullable=False)
    description: Mapped[str] = mapped_column(sa.Text)
    is_paper_trading: Mapped[bool] = mapped_column(sa.Boolean, default=True)

    base_currency: Mapped[str] = mapped_column(sa.String(3), default="BRL")
    initial_capital: Mapped[Decimal] = mapped_column(sa.Numeric(20, 4))

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=utcnow)

    __table_args__ = (sa.UniqueConstraint("organization_id", "name", name="uq_portfolios_org_name"),)

    def __repr__(self) -> str:
        return f"Portfolio(name={self.name!r}, is_paper_trading={self.is_paper_trading})"


class Position(Base):
    __tablename__ = "positions"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    portfolio_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("portfolios.id", ondelete="CASCADE"),
        nullable=False,
    )
    issuer_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("issuers.id", ondelete="SET NULL"),
    )

    ticker_symbol: Mapped[str] = mapped_column(sa.String(10))
    quantity: Mapped[Decimal] = mapped_column(sa.Numeric(20, 4))
    avg_cost_per_share: Mapped[Decimal] = mapped_column(sa.Numeric(14, 6))
    current_price: Mapped[Decimal] = mapped_column(sa.Numeric(14, 6))

    weight_pct: Mapped[float] = mapped_column(sa.Float)
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=utcnow)

    def __repr__(self) -> str:
        return f"Position(ticker_symbol={self.ticker_symbol!r}, quantity={self.quantity})"


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    portfolio_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("portfolios.id", ondelete="CASCADE"),
        nullable=False,
    )
    position_id: Mapped[UUID | None] = mapped_column(sa.ForeignKey("positions.id", ondelete="SET NULL"))

    side: Mapped[str] = mapped_column(sa.String(10))
    ticker_symbol: Mapped[str] = mapped_column(sa.String(10))
    quantity: Mapped[Decimal] = mapped_column(sa.Numeric(20, 4))
    price_per_share: Mapped[Decimal] = mapped_column(sa.Numeric(14, 6))

    execution_date: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), index=True)
    status: Mapped[str] = mapped_column(sa.String(20))

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=utcnow)

    def __repr__(self) -> str:
        return f"Transaction(side={self.side!r}, ticker_symbol={self.ticker_symbol!r}, status={self.status!r})"


class PortfolioConstraint(Base):
    __tablename__ = "portfolio_constraints"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    portfolio_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("portfolios.id", ondelete="CASCADE"),
        nullable=False,
    )

    constraint_type: Mapped[str] = mapped_column(sa.String(50))
    target: Mapped[str] = mapped_column(sa.String(100))
    limit_value: Mapped[float] = mapped_column(sa.Float)

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=utcnow)

    def __repr__(self) -> str:
        return f"PortfolioConstraint(constraint_type={self.constraint_type!r}, target={self.target!r})"


class RiskSnapshot(Base):
    __tablename__ = "risk_snapshots"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    portfolio_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("portfolios.id", ondelete="CASCADE"),
        nullable=False,
    )

    snapshot_date: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True))
    total_exposure: Mapped[Decimal] = mapped_column(sa.Numeric(20, 4))
    sector_concentration: Mapped[dict[str, object]] = mapped_column(JSONB)
    top_risks: Mapped[dict[str, object]] = mapped_column(JSONB)

    sharpe_ratio: Mapped[float] = mapped_column(sa.Float)
    max_drawdown_pct: Mapped[float] = mapped_column(sa.Float)
    volatility_annualized: Mapped[float] = mapped_column(sa.Float)

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=utcnow)

    def __repr__(self) -> str:
        return f"RiskSnapshot(sharpe_ratio={self.sharpe_ratio}, max_drawdown_pct={self.max_drawdown_pct})"


class RebalanceProposal(Base):
    __tablename__ = "rebalance_proposals"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    portfolio_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("portfolios.id", ondelete="CASCADE"),
        nullable=False,
    )

    current_allocation: Mapped[dict[str, object]] = mapped_column(JSONB)
    proposed_allocation: Mapped[dict[str, object]] = mapped_column(JSONB)
    rationale_pt: Mapped[str] = mapped_column(sa.Text)

    expected_return_change: Mapped[float] = mapped_column(sa.Float)
    risk_impact: Mapped[dict[str, object]] = mapped_column(JSONB())

    status: Mapped[str] = mapped_column(sa.String(20), default="pending")
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=utcnow)

    def __repr__(self) -> str:
        return f"RebalanceProposal(status={self.status!r})"


class ProposedTrade(Base):
    __tablename__ = "proposed_trades"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    rebalance_proposal_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("rebalance_proposals.id", ondelete="CASCADE"),
        nullable=False,
    )

    ticker_symbol: Mapped[str] = mapped_column(sa.String(10))
    side: Mapped[str] = mapped_column(sa.String(10))
    quantity: Mapped[Decimal] = mapped_column(sa.Numeric(20, 4))
    target_price: Mapped[Decimal] = mapped_column(sa.Numeric(14, 6))

    rationale_pt: Mapped[str] = mapped_column(sa.Text)
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=utcnow)

    def __repr__(self) -> str:
        return f"ProposedTrade(ticker_symbol={self.ticker_symbol!r}, side={self.side!r})"
