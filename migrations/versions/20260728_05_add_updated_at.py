"""Add updated_at column to all active tables that lack it.

Revision ID: 20260728_05
Revises: 20260728_04
Create Date: 2026-07-28

Adds updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() to every table
that has created_at but no updated_at. Excludes:
- Tables dropped in 20260728_04 (dead tables)
- Tables that already have updated_at
- Immutable/audit tables where mutation tracking is inappropriate
"""

import sqlalchemy as sa
from alembic import op

revision: str = "20260728_05"
down_revision: str | None = "20260728_04"
branch_labels: str | None = None
depends_on: str | None = None

# All active tables that have created_at but no updated_at.
# Excludes dead tables dropped in previous migration and immutable tables.
TABLES = [
    # data_foundation
    "data_sources",
    "source_objects",
    # evaluation
    "scorecards",
    "backtest_results",
    # documents
    "raw_documents",
    "document_metadata",
    "documents",
    # macro
    "macro_indicators",
    # research
    "claim_contradictions",
    # workflow
    "prompt_versions",
    "structured_output_schemas",
    # portfolio_versions
    "institutional_portfolio_versions",
    "portfolio_ledger_entries",
    "nav_publications",
    # policy_intelligence
    "policy_objects",
    "regulatory_actions",
    # valuation
    "valuation_runs",
    # quality
    "data_quality_checks",
    # audit
    "audit_log_entries",
    # instrument_master
    "legal_entities",
    "instruments",
    "listings",
    # portfolio_models (active ones only)
    "portfolios",
    "positions",
    "transactions",
    "portfolio_constraints",
    "risk_snapshots",
    # portfolio_risk
    "institutional_risk_snapshots",
    # committee
    "committee_votes",
    "committee_decisions",
    # operations
    "operation_dispatch_dead_letter",
    # data_governance
    "quarantine_records",
    # portfolio_optimization
    "optimization_runs",
    "portfolio_approval_evidence",
    "institutional_backtest_runs",
    # universe
    "universe_filters",
    # news
    "news_sources",
    "news_items",
    "news_entity_links",
    "detected_events",
    "event_impacts",
    "event_duplicates",
    # agent_runtime
    "agent_capabilities",
    "agent_artifacts",
    "agent_versions",
    "agent_runtime_runs",
    "agent_runtime_tool_calls",
    "agent_eval_datasets",
    "agent_eval_runs",
    # investment_candidates
    "candidate_sources",
    "candidate_gaps",
    "exploration_runs",
    "exploration_suggestions",
    "restricted_instruments",
    # rebalance (active)
    "portfolio_rebalance_trades",
    "drift_snapshots",
    # paper_execution
    "execution_model_versions",
    "paper_orders",
    "operational_alerts",
    "paper_post_mortems",
    # thesis_domain
    "research_theses",
    "research_thesis_versions",
    # financial_facts
    "financial_facts",
    "restatement_logs",
    # financials
    "financial_statements",
    "financial_metrics",
    "dividends",
    "share_statistics",
    # identity
    "organizations",
    "user_identities",
    # catalog
    "sectors",
    "industries",
    "tickers",
    "market_prices",
    "embeddings",
    # processing
    "document_processing_log",
    "document_duplicates",
    "document_events",
    # review
    "research_assessments",
]


def upgrade() -> None:
    conn = op.get_bind()
    for table in TABLES:
        # Check if table exists
        result = conn.execute(
            sa.text("SELECT EXISTS (  SELECT 1 FROM information_schema.tables   WHERE table_name = :table)"),
            {"table": table},
        )
        if not result.scalar():
            continue
        # Check if column already exists
        result = conn.execute(
            sa.text(
                "SELECT EXISTS ("
                "  SELECT 1 FROM information_schema.columns "
                "  WHERE table_name = :table AND column_name = 'updated_at'"
                ")"
            ),
            {"table": table},
        )
        if result.scalar():
            continue
        op.add_column(
            table,
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
        )


def downgrade() -> None:
    for table in TABLES:
        op.drop_column(table, "updated_at")
