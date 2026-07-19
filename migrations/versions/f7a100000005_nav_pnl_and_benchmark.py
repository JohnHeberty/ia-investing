"""add NAV PnL and benchmark performance

Revision ID: f7a100000005
Revises: f7a100000004
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f7a100000005"
down_revision: str | Sequence[str] | None = "f7a100000004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("market_indices", sa.Column("instrument_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        op.f("fk_market_indices_instrument_id_instruments"),
        "market_indices",
        "instruments",
        ["instrument_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.add_column("nav_publications", sa.Column("gross_pnl", sa.Numeric(28, 8), nullable=True))
    op.add_column("nav_publications", sa.Column("net_pnl", sa.Numeric(28, 8), nullable=True))
    op.add_column("nav_publications", sa.Column("benchmark_return", sa.Numeric(18, 10), nullable=True))
    op.execute("UPDATE nav_publications SET gross_pnl = 0, net_pnl = 0 WHERE gross_pnl IS NULL OR net_pnl IS NULL")
    op.alter_column("nav_publications", "gross_pnl", nullable=False)
    op.alter_column("nav_publications", "net_pnl", nullable=False)


def downgrade() -> None:
    op.drop_column("nav_publications", "benchmark_return")
    op.drop_column("nav_publications", "net_pnl")
    op.drop_column("nav_publications", "gross_pnl")
    op.drop_constraint(op.f("fk_market_indices_instrument_id_instruments"), "market_indices", type_="foreignkey")
    op.drop_column("market_indices", "instrument_id")
