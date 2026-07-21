"""Integration test: verify Alembic migrations applied and schema is correct.

Checks:
  - All expected tables exist
  - pgvector extension loaded
  - btree_gist extension loaded
  - Key columns present on critical tables
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

EXPECTED_TABLES = frozenset(
    {
        "source_licenses",
        "data_sources",
        "source_slas",
        "source_objects",
        "source_object_versions",
        "ingestion_attempts",
        "reporting_periods",
        "taxonomy_accounts",
        "account_mapping_rules",
        "financial_facts",
        "metric_definitions",
        "metric_observations",
        "metric_fact_lineage",
        "document_chunks",
        "research_cases",
        "research_questions",
        "research_assignments",
        "domain_outbox_events",
        "research_theses",
        "research_thesis_versions",
        "thesis_version_evidence",
        "thesis_version_claims",
        "valuation_runs",
        "valuation_assumptions",
        "valuation_results",
        "organizations",
        "user_identities",
        "teams",
        "roles",
        "permissions",
        "strategy_mandates",
        "model_portfolios",
        "market_bars",
        "market_quotes",
        "corporate_actions",
        "fx_rates",
        "trading_sessions",
        "policy_objects",
        "policy_object_versions",
        "policy_stage_events",
        "policy_actors",
        "policy_votes",
        "policy_corroboration",
        "policy_graph_nodes",
        "policy_graph_edges",
        "policy_probability_forecasts",
        "macro_series_definitions",
        "macro_observation_revisions",
        "trade_intents",
        "paper_orders",
        "paper_fills",
        "reconciliation_breaks",
        "operational_alerts",
        "paper_kill_switches",
        "paper_post_mortems",
        "agent_capabilities",
        "agent_artifacts",
        "agent_versions",
        "agent_runtime_runs",
        "quality_rules",
        "quality_incidents",
    }
)


async def test_extensions_loaded(session: AsyncSession) -> None:
    """pgvector and btree_gist extensions must be installed."""
    result = await session.execute(
        sa.text("SELECT extname FROM pg_extension WHERE extname IN ('vector', 'btree_gist')")
    )
    extensions = {row[0] for row in result.fetchall()}
    assert "vector" in extensions, "pgvector extension not installed"
    assert "btree_gist" in extensions, "btree_gist extension not installed"


async def test_all_tables_exist(session: AsyncSession) -> None:
    """All expected ORM tables should exist in the public schema."""
    result = await session.execute(sa.text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'"))
    actual = {row[0] for row in result.fetchall()}
    missing = EXPECTED_TABLES - actual
    assert not missing, f"Tables missing from schema: {sorted(missing)}"


async def test_financial_facts_columns(session: AsyncSession) -> None:
    """FinancialFact must have PIT columns."""
    result = await session.execute(
        sa.text("SELECT column_name FROM information_schema.columns WHERE table_name = 'financial_facts'")
    )
    columns = {row[0] for row in result.fetchall()}
    for col in ("knowledge_at", "valid_from", "valid_to", "revision_number", "value_status", "currency_code"):
        assert col in columns, f"financial_facts.{col} missing"


async def test_document_chunks_embedding(session: AsyncSession) -> None:
    """DocumentChunk must have pgvector embedding column."""
    result = await session.execute(
        sa.text("SELECT column_name, udt_name FROM information_schema.columns WHERE table_name = 'document_chunks'")
    )
    cols = {row[0]: row[1] for row in result.fetchall()}
    assert "embedding" in cols, "document_chunks.embedding column missing"
    assert cols["embedding"] == "vector", f"embedding column type is {cols['embedding']}, expected vector"
