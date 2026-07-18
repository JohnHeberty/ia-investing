from datetime import UTC, datetime

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from .base import Base


class Portfolio(Base):
    __tablename__ = "portfolios"

    id = sa.Column(UUID(as_uuid=True), primary_key=True, default=sa.func.gen_random_uuid())
    name = sa.Column(sa.String(200), nullable=False)
    description = sa.Column(sa.Text)
    is_paper_trading = sa.Column(sa.Boolean, default=True)

    base_currency = sa.Column(sa.String(3), default="BRL")
    initial_capital = sa.Column(sa.Numeric(20, 4))

    created_at = sa.Column(sa.DateTime(timezone=True), default=lambda: datetime.now(UTC))

    def __repr__(self) -> str:
        return f"Portfolio(name={self.name!r}, is_paper_trading={self.is_paper_trading})"


class Position(Base):
    __tablename__ = "positions"

    id = sa.Column(UUID(as_uuid=True), primary_key=True, default=sa.func.gen_random_uuid())
    portfolio_id = sa.Column(
        UUID(as_uuid=True), sa.ForeignKey("portfolios.id", ondelete="CASCADE"), nullable=False,
    )
    issuer_id = sa.Column(
        UUID(as_uuid=True), sa.ForeignKey("issuers.id", ondelete="SET NULL"),
    )

    ticker_symbol = sa.Column(sa.String(10))
    quantity = sa.Column(sa.Numeric(20, 4))
    avg_cost_per_share = sa.Column(sa.Numeric(14, 6))
    current_price = sa.Column(sa.Numeric(14, 6))

    weight_pct = sa.Column(sa.Float)
    created_at = sa.Column(sa.DateTime(timezone=True), default=lambda: datetime.now(UTC))

    def __repr__(self) -> str:
        return f"Position(ticker_symbol={self.ticker_symbol!r}, quantity={self.quantity})"


class Transaction(Base):
    __tablename__ = "transactions"

    id = sa.Column(UUID(as_uuid=True), primary_key=True, default=sa.func.gen_random_uuid())
    portfolio_id = sa.Column(
        UUID(as_uuid=True), sa.ForeignKey("portfolios.id", ondelete="CASCADE"), nullable=False,
    )
    position_id = sa.Column(UUID(as_uuid=True), sa.ForeignKey("positions.id", ondelete="SET NULL"), nullable=True)

    side = sa.Column(sa.String(10))  # "BUY", "SELL"
    ticker_symbol = sa.Column(sa.String(10))
    quantity = sa.Column(sa.Numeric(20, 4))
    price_per_share = sa.Column(sa.Numeric(14, 6))

    execution_date = sa.Column(sa.DateTime(timezone=True), index=True)
    status = sa.Column(sa.String(20))  # "pending", "executed", "cancelled"

    created_at = sa.Column(sa.DateTime(timezone=True), default=lambda: datetime.now(UTC))

    def __repr__(self) -> str:
        return f"Transaction(side={self.side!r}, ticker_symbol={self.ticker_symbol!r}, status={self.status!r})"


class PortfolioConstraint(Base):
    __tablename__ = "portfolio_constraints"

    id = sa.Column(UUID(as_uuid=True), primary_key=True, default=sa.func.gen_random_uuid())
    portfolio_id = sa.Column(
        UUID(as_uuid=True), sa.ForeignKey("portfolios.id", ondelete="CASCADE"), nullable=False,
    )

    constraint_type = sa.Column(sa.String(50))  # "max_position", "sector_limit"
    target = sa.Column(sa.String(100))
    limit_value = sa.Column(sa.Float)

    created_at = sa.Column(sa.DateTime(timezone=True), default=lambda: datetime.now(UTC))

    def __repr__(self) -> str:
        return f"PortfolioConstraint(constraint_type={self.constraint_type!r}, target={self.target!r})"


class RiskSnapshot(Base):
    __tablename__ = "risk_snapshots"

    id = sa.Column(UUID(as_uuid=True), primary_key=True, default=sa.func.gen_random_uuid())
    portfolio_id = sa.Column(
        UUID(as_uuid=True), sa.ForeignKey("portfolios.id", ondelete="CASCADE"), nullable=False,
    )

    snapshot_date = sa.Column(sa.DateTime(timezone=True))
    total_exposure = sa.Column(sa.Numeric(20, 4))
    sector_concentration = JSONB()
    top_risks = JSONB()

    sharpe_ratio = sa.Column(sa.Float)
    max_drawdown_pct = sa.Column(sa.Float)
    volatility_annualized = sa.Column(sa.Float)

    created_at = sa.Column(sa.DateTime(timezone=True), default=lambda: datetime.now(UTC))

    def __repr__(self) -> str:
        return f"RiskSnapshot(sharpe_ratio={self.sharpe_ratio}, max_drawdown_pct={self.max_drawdown_pct})"


class RebalanceProposal(Base):
    __tablename__ = "rebalance_proposals"

    id = sa.Column(UUID(as_uuid=True), primary_key=True, default=sa.func.gen_random_uuid())
    portfolio_id = sa.Column(
        UUID(as_uuid=True), sa.ForeignKey("portfolios.id", ondelete="CASCADE"), nullable=False,
    )

    current_allocation = JSONB()
    proposed_allocation = JSONB()
    rationale_pt = sa.Column(sa.Text)

    expected_return_change = sa.Column(sa.Float)
    risk_impact = sa.Column(JSONB())

    status = sa.Column(sa.String(20), default="pending")  # "pending", "approved", "rejected"
    created_at = sa.Column(sa.DateTime(timezone=True), default=lambda: datetime.now(UTC))

    def __repr__(self) -> str:
        return f"RebalanceProposal(status={self.status!r})"


class ProposedTrade(Base):
    __tablename__ = "proposed_trades"

    id = sa.Column(UUID(as_uuid=True), primary_key=True, default=sa.func.gen_random_uuid())
    rebalance_proposal_id = sa.Column(
        UUID(as_uuid=True), sa.ForeignKey("rebalance_proposals.id", ondelete="CASCADE"),
        nullable=False,
    )

    ticker_symbol = sa.Column(sa.String(10))
    side = sa.Column(sa.String(10))  # "BUY", "SELL"
    quantity = sa.Column(sa.Numeric(20, 4))
    target_price = sa.Column(sa.Numeric(14, 6))

    rationale_pt = sa.Column(sa.Text)
    created_at = sa.Column(sa.DateTime(timezone=True), default=lambda: datetime.now(UTC))

    def __repr__(self) -> str:
        return f"ProposedTrade(ticker_symbol={self.ticker_symbol!r}, side={self.side!r})"
