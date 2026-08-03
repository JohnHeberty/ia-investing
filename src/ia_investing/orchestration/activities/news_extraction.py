"""Temporal activities for news extraction pipeline."""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from temporalio import activity

from ia_investing.orchestration.activities._telemetry import activity_span

logger = logging.getLogger(__name__)


@activity.defn(name="fetch_news_items")
async def fetch_news_items(issuer_id: str, max_results: int = 20) -> list[dict[str, Any]]:
    """Fetch RSS news items for an issuer and persist to DB."""
    with activity_span("fetch_news_items"):
        from database.core import session_scope
        from ia_investing.news.service import fetch_and_persist_news_items

        async with session_scope() as session:
            items = await fetch_and_persist_news_items(
                UUID(issuer_id), session, max_results=max_results
            )
            return items


@activity.defn(name="analyze_single_news_item")
async def analyze_single_news_item(news_item_id: str) -> dict[str, Any]:
    """Run LLM analysis on a single news item and persist results."""
    with activity_span("analyze_single_news_item"):
        from database.core import session_scope
        from ia_investing.news.service import analyze_news_item

        async with session_scope() as session:
            result = await analyze_news_item(UUID(news_item_id), session)
            return result or {"status": "failed", "news_item_id": news_item_id}


@activity.defn(name="batch_analyze_news")
async def batch_analyze_news(issuer_id: str, limit: int = 10) -> dict[str, Any]:
    """Analyze unprocessed news items for an issuer."""
    with activity_span("batch_analyze_news"):
        from database.core import session_scope
        from ia_investing.news.service import analyze_news_item, list_news_items

        async with session_scope() as session:
            items, total = await list_news_items(
                session, issuer_id=UUID(issuer_id), is_processed=False, limit=limit
            )
            results = []
            for item in items:
                result = await analyze_news_item(UUID(item["id"]), session)
                results.append(result)
            return {
                "issuer_id": issuer_id,
                "total_unprocessed": total,
                "analyzed": len(results),
                "results": results,
            }


@activity.defn(name="detect_event_duplicates")
async def detect_event_duplicates(event_id: str) -> dict[str, Any]:
    """Check if a detected event is a duplicate of an existing one."""
    with activity_span("detect_event_duplicates"):
        import sqlalchemy as sa

        from database.core import session_scope
        from database.models.news import DetectedEvent, EventDuplicate

        async with session_scope() as session:
            event = await session.get(DetectedEvent, UUID(event_id))
            if event is None:
                return {"event_id": event_id, "is_duplicate": False}

            similar = (await session.execute(
                sa.select(DetectedEvent).where(
                    DetectedEvent.id != event.id,
                    DetectedEvent.event_type == event.event_type,
                    DetectedEvent.issuer_id == event.issuer_id,
                    DetectedEvent.created_at >= event.created_at - __import__("datetime").timedelta(hours=24),
                )
            )).scalars().first()

            if similar:
                dup = EventDuplicate(
                    original_id=similar.id,
                    duplicate_id=event.id,
                    similarity_method="type+issuer+time",
                    similarity_score=0.8,
                )
                session.add(dup)
                await session.flush()
                return {
                    "event_id": event_id,
                    "is_duplicate": True,
                    "original_id": str(similar.id),
                }

            return {"event_id": event_id, "is_duplicate": False}


NEWS_EXTRACTION_ACTIVITIES = (
    fetch_news_items,
    analyze_single_news_item,
    batch_analyze_news,
    detect_event_duplicates,
)
