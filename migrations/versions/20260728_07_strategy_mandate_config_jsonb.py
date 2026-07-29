"""StrategyMandate: consolidate 18 columns into config JSONB.

Revision ID: 20260728_07
Revises: 20260728_06
Create Date: 2026-07-28
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "20260728_07"
down_revision = "20260728_06"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Phase 1: Add nullable config JSONB column
    op.add_column("strategy_mandates", sa.Column("config", JSONB, nullable=True))

    # Phase 2: Backfill — build config from existing column values
    op.execute("""
        UPDATE strategy_mandates
        SET config = jsonb_build_object(
            'objective', objective,
            'strategy_type', strategy_type,
            'investment_horizon_days', investment_horizon_days,
            'target_volatility', CASE WHEN target_volatility IS NOT NULL
                THEN target_volatility::text::jsonb ELSE 'null'::jsonb END,
            'max_drawdown', max_drawdown,
            'min_cash_weight', min_cash_weight,
            'max_cash_weight', max_cash_weight,
            'max_turnover', max_turnover,
            'universe_definition', COALESCE(universe_definition, '{}'::jsonb),
            'rebalance_policy', COALESCE(rebalance_policy, '{}'::jsonb),
            'risk_budget', COALESCE(risk_budget, '{}'::jsonb),
            'concentration_limits', COALESCE(concentration_limits, '{}'::jsonb),
            'factor_limits', COALESCE(factor_limits, '{}'::jsonb),
            'liquidity_policy', COALESCE(liquidity_policy, '{}'::jsonb),
            'exclusions', COALESCE(exclusions, '{}'::jsonb),
            'cost_policy', COALESCE(cost_policy, '{}'::jsonb),
            'tax_policy', COALESCE(tax_policy, '{}'::jsonb),
            'approval_policy', COALESCE(approval_policy, '{}'::jsonb)
        )
        WHERE config IS NULL
    """)

    # Phase 3: Drop CHECK constraints that reference dropped columns
    op.drop_constraint("positive_horizon", "strategy_mandates", type_="check")
    op.drop_constraint("cash_range", "strategy_mandates", type_="check")
    op.drop_constraint("turnover_range", "strategy_mandates", type_="check")
    op.drop_constraint("drawdown_range", "strategy_mandates", type_="check")

    # Phase 4: Drop the 18 consolidated columns
    for col in [
        "objective",
        "strategy_type",
        "investment_horizon_days",
        "target_volatility",
        "max_drawdown",
        "min_cash_weight",
        "max_cash_weight",
        "max_turnover",
        "universe_definition",
        "rebalance_policy",
        "risk_budget",
        "concentration_limits",
        "factor_limits",
        "liquidity_policy",
        "exclusions",
        "cost_policy",
        "tax_policy",
        "approval_policy",
    ]:
        op.drop_column("strategy_mandates", col)

    # Phase 5: Set config NOT NULL after backfill
    op.alter_column("strategy_mandates", "config", nullable=False)


def downgrade() -> None:
    # Recreate the 18 columns
    op.add_column("strategy_mandates", sa.Column("objective", sa.Text, nullable=False, server_default=""))
    op.add_column("strategy_mandates", sa.Column("strategy_type", sa.String(50), nullable=False, server_default=""))
    op.add_column("strategy_mandates", sa.Column("investment_horizon_days", sa.Integer, nullable=False, server_default="0"))
    op.add_column("strategy_mandates", sa.Column("target_volatility", sa.Numeric(8, 6), nullable=True))
    op.add_column("strategy_mandates", sa.Column("max_drawdown", sa.Numeric(8, 6), nullable=False, server_default="0"))
    op.add_column("strategy_mandates", sa.Column("min_cash_weight", sa.Numeric(8, 6), nullable=False, server_default="0"))
    op.add_column("strategy_mandates", sa.Column("max_cash_weight", sa.Numeric(8, 6), nullable=False, server_default="0"))
    op.add_column("strategy_mandates", sa.Column("max_turnover", sa.Numeric(8, 6), nullable=False, server_default="0"))
    op.add_column("strategy_mandates", sa.Column("universe_definition", JSONB, nullable=False, server_default="{}"))
    op.add_column("strategy_mandates", sa.Column("rebalance_policy", JSONB, nullable=False, server_default="{}"))
    op.add_column("strategy_mandates", sa.Column("risk_budget", JSONB, nullable=False, server_default="{}"))
    op.add_column("strategy_mandates", sa.Column("concentration_limits", JSONB, nullable=False, server_default="{}"))
    op.add_column("strategy_mandates", sa.Column("factor_limits", JSONB, nullable=False, server_default="{}"))
    op.add_column("strategy_mandates", sa.Column("liquidity_policy", JSONB, nullable=False, server_default="{}"))
    op.add_column("strategy_mandates", sa.Column("exclusions", JSONB, nullable=False, server_default="{}"))
    op.add_column("strategy_mandates", sa.Column("cost_policy", JSONB, nullable=False, server_default="{}"))
    op.add_column("strategy_mandates", sa.Column("tax_policy", JSONB, nullable=False, server_default="{}"))
    op.add_column("strategy_mandates", sa.Column("approval_policy", JSONB, nullable=False, server_default="{}"))

    # Backfill from config
    op.execute("""
        UPDATE strategy_mandates SET
            objective = COALESCE(config->>'objective', ''),
            strategy_type = COALESCE(config->>'strategy_type', ''),
            investment_horizon_days = COALESCE((config->>'investment_horizon_days')::int, 0),
            target_volatility = (config->>'target_volatility')::numeric(8,6),
            max_drawdown = COALESCE((config->>'max_drawdown')::numeric(8,6), 0),
            min_cash_weight = COALESCE((config->>'min_cash_weight')::numeric(8,6), 0),
            max_cash_weight = COALESCE((config->>'max_cash_weight')::numeric(8,6), 0),
            max_turnover = COALESCE((config->>'max_turnover')::numeric(8,6), 0),
            universe_definition = COALESCE(config->'universe_definition', '{}'::jsonb),
            rebalance_policy = COALESCE(config->'rebalance_policy', '{}'::jsonb),
            risk_budget = COALESCE(config->'risk_budget', '{}'::jsonb),
            concentration_limits = COALESCE(config->'concentration_limits', '{}'::jsonb),
            factor_limits = COALESCE(config->'factor_limits', '{}'::jsonb),
            liquidity_policy = COALESCE(config->'liquidity_policy', '{}'::jsonb),
            exclusions = COALESCE(config->'exclusions', '{}'::jsonb),
            cost_policy = COALESCE(config->'cost_policy', '{}'::jsonb),
            tax_policy = COALESCE(config->'tax_policy', '{}'::jsonb),
            approval_policy = COALESCE(config->'approval_policy', '{}'::jsonb)
        WHERE config IS NOT NULL
    """)

    op.drop_column("strategy_mandates", "config")

    # Recreate CHECK constraints
    op.create_check_constraint("positive_horizon", "strategy_mandates", "investment_horizon_days > 0")
    op.create_check_constraint(
        "cash_range",
        "strategy_mandates",
        "min_cash_weight BETWEEN 0 AND 1 AND max_cash_weight BETWEEN min_cash_weight AND 1",
    )
    op.create_check_constraint("turnover_range", "strategy_mandates", "max_turnover BETWEEN 0 AND 2")
    op.create_check_constraint("drawdown_range", "strategy_mandates", "max_drawdown BETWEEN 0 AND 1")
