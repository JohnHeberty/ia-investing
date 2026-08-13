"""Unit tests for the news collection and impact classification service."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from ia_investing.news.service import (
    DEFAULT_MAX_RESULTS,
    DEFAULT_SOURCE_TRUST_LEVEL,
    LLM_BODY_CHAR_LIMIT,
    NEWS_DEDUP_WINDOW_DAYS,
    _content_hash,
)

MATERIALITY_ALERT_THRESHOLD = 0.7


def _truncate_body(body: str) -> str:
    return body[:LLM_BODY_CHAR_LIMIT]


class TestDeduplication:
    def test_dedup_key_stable_for_same_content(self) -> None:
        key1 = _content_hash("Petrobras anuncia dividendos", "https://example.com/1")
        key2 = _content_hash("Petrobras anuncia dividendos", "https://example.com/1")
        assert key1 == key2
        assert isinstance(key1, str)
        assert len(key1) == 64

    def test_dedup_key_differs_for_different_titles(self) -> None:
        key1 = _content_hash("Title A", "https://example.com/1")
        key2 = _content_hash("Title B", "https://example.com/1")
        assert key1 != key2

    def test_dedup_key_differs_for_different_urls(self) -> None:
        key1 = _content_hash("Title", "https://example.com/1")
        key2 = _content_hash("Title", "https://example.com/2")
        assert key1 != key2


class TestTruncateBody:
    def test_short_body_unchanged(self) -> None:
        body = "Short body"
        assert _truncate_body(body) == body

    def test_long_body_truncated(self) -> None:
        body = "x" * (LLM_BODY_CHAR_LIMIT + 500)
        result = _truncate_body(body)
        assert len(result) == LLM_BODY_CHAR_LIMIT

    def test_exact_limit_unchanged(self) -> None:
        body = "x" * LLM_BODY_CHAR_LIMIT
        assert _truncate_body(body) == body


    def test_max_results_default(self) -> None:
        assert DEFAULT_MAX_RESULTS == 20

    def test_source_trust_level_default(self) -> None:
        assert DEFAULT_SOURCE_TRUST_LEVEL == 3

    def test_materiality_alert_threshold(self) -> None:
        assert MATERIALITY_ALERT_THRESHOLD == 0.7

    def test_llm_body_char_limit(self) -> None:
        assert LLM_BODY_CHAR_LIMIT == 2000


class TestNewsAnalysisSchema:
    def test_imports(self) -> None:
        from schemas._news import NewsAnalysis

        assert NewsAnalysis is not None

    def test_news_analysis_has_affected_issuers(self) -> None:
        from schemas._news import NewsAnalysis

        fields = NewsAnalysis.model_fields
        assert "affected_issuers" in fields

    def test_news_analysis_default_affected_issuers(self) -> None:
        from schemas._news import NewsAnalysis

        analysis = NewsAnalysis(
            verdict="neutral",
            confidence=0.5,
            summary_pt="Teste",
            materiality_score=0.0,
            thesis_effect="no_change",
            event_type="market",
            affected_metrics=[],
            time_horizon="immediate",
            key_claims=[],
        )
        assert analysis.affected_issuers == []


class TestNewsExtractionActivities:
    def test_fetch_news_items_exists(self) -> None:
        from ia_investing.orchestration.activities.news_extraction import fetch_news_items

        assert callable(fetch_news_items)

    def test_analyze_single_news_item_exists(self) -> None:
        from ia_investing.orchestration.activities.news_extraction import analyze_single_news_item

        assert callable(analyze_single_news_item)

    def test_batch_analyze_news_exists(self) -> None:
        from ia_investing.orchestration.activities.news_extraction import batch_analyze_news

        assert callable(batch_analyze_news)

    def test_batch_analysis_uses_valid_issuer_scoped_postgres_query(self) -> None:
        from sqlalchemy.dialects import postgresql

        from ia_investing.orchestration.activities.news_extraction import (
            _pending_news_item_ids_statement,
        )

        statement = _pending_news_item_ids_statement(
            "00000000-0000-0000-0000-000000000002",
            10,
        )
        sql = str(statement.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))

        assert "EXISTS" in sql
        assert "news_entity_links.issuer_id" in sql
        assert "DISTINCT" not in sql
        assert "ORDER BY news_items.created_at DESC" in sql

    def test_detect_event_duplicates_exists(self) -> None:
        from ia_investing.orchestration.activities.news_extraction import detect_event_duplicates

        assert callable(detect_event_duplicates)

    def test_check_alert_threshold_exists(self) -> None:
        from ia_investing.orchestration.activities.news_extraction import check_alert_threshold

        assert callable(check_alert_threshold)

    def test_news_extraction_activities_tuple_count(self) -> None:
        from ia_investing.orchestration.activities.news_extraction import NEWS_EXTRACTION_ACTIVITIES

        assert len(NEWS_EXTRACTION_ACTIVITIES) == 6

    @pytest.mark.asyncio
    async def test_check_alert_threshold_alerts_on_high_materiality(self) -> None:
        from ia_investing.orchestration.activities.news_extraction import check_alert_threshold

        with patch("ia_investing.orchestration.activities.news_extraction.activity_span"):
            result = await check_alert_threshold(
                {
                    "news_item_id": "test-id",
                    "materiality_score": 0.85,
                    "event_type": "earnings",
                    "affected_issuers": [],
                    "direction_hint": "positive",
                }
            )
        assert result["alert"] is True
        assert result["materiality_score"] == 0.85

    @pytest.mark.asyncio
    async def test_check_alert_threshold_no_alert_on_low_materiality(self) -> None:
        from ia_investing.orchestration.activities.news_extraction import check_alert_threshold

        with patch("ia_investing.orchestration.activities.news_extraction.activity_span"):
            result = await check_alert_threshold(
                {
                    "news_item_id": "test-id",
                    "materiality_score": 0.3,
                    "event_type": "market",
                    "affected_issuers": [],
                    "direction_hint": "neutral",
                }
            )
        assert result["alert"] is False

    @pytest.mark.asyncio
    async def test_check_alert_threshold_negative_materiality(self) -> None:
        from ia_investing.orchestration.activities.news_extraction import check_alert_threshold

        with patch("ia_investing.orchestration.activities.news_extraction.activity_span"):
            result = await check_alert_threshold(
                {
                    "news_item_id": "test-id",
                    "materiality_score": -0.9,
                    "event_type": "governance",
                    "affected_issuers": [],
                    "direction_hint": "negative",
                }
            )
        assert result["alert"] is True
        assert result["materiality_score"] == 0.9

    @pytest.mark.asyncio
    async def test_check_alert_threshold_boundary(self) -> None:
        from ia_investing.orchestration.activities.news_extraction import check_alert_threshold

        with patch("ia_investing.orchestration.activities.news_extraction.activity_span"):
            result = await check_alert_threshold(
                {
                    "news_item_id": "test-id",
                    "materiality_score": 0.7,
                    "event_type": "market",
                    "affected_issuers": [],
                    "direction_hint": "neutral",
                }
            )
        assert result["alert"] is True


class TestExtractNewsWorkflow:
    def test_extract_news_input_defaults(self) -> None:
        from workflows._extract_news import ExtractNewsInput

        inp = ExtractNewsInput(issuer_id="test-issuer")
        assert inp.max_results == 20
        assert inp.analyze_limit == 10
        assert inp.organization_id == ""
        assert inp.schedule_id == ""
