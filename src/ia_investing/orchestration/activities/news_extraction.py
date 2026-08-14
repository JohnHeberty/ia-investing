"""Temporal activities for news extraction pipeline."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from temporalio import activity

from ia_investing.orchestration.activities._telemetry import activity_span

logger = logging.getLogger(__name__)


def _pending_news_item_ids_statement(issuer_id: str, limit: int) -> Any:
    import sqlalchemy as sa

    from database.models.news import NewsEntityLink, NewsItem

    statement = sa.select(NewsItem.id).where(NewsItem.is_processed.is_(False))
    if issuer_id:
        issuer_link = sa.exists(
            sa.select(NewsEntityLink.id).where(
                NewsEntityLink.news_item_id == NewsItem.id,
                NewsEntityLink.issuer_id == UUID(issuer_id),
            )
        )
        statement = statement.where(issuer_link)
    return statement.order_by(NewsItem.created_at.desc()).limit(limit)


@activity.defn(name="fetch_news_items")
async def fetch_news_items(params: dict[str, Any]) -> list[dict[str, Any]]:
    """Fetch RSS news items for an issuer and persist to DB."""
    with activity_span("fetch_news_items"):
        from database.core import session_scope
        from ia_investing.news.service import fetch_and_persist_news_items

        issuer_id = params["issuer_id"]
        max_results = params.get("max_results", 20)
        async with session_scope() as session:
            items = await fetch_and_persist_news_items(UUID(issuer_id), session, max_results=max_results)
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
async def batch_analyze_news(params: dict[str, Any]) -> dict[str, Any]:
    """Analyze unprocessed news items for an issuer."""
    with activity_span("batch_analyze_news"):
        from database.core import session_scope
        from ia_investing.news.service import analyze_news_item

        issuer_id = params.get("issuer_id", "")
        limit = params.get("limit", 10)

        async with session_scope() as session:
            statement = _pending_news_item_ids_statement(issuer_id, limit)
            result = await session.execute(statement)
            item_ids = list(result.scalars().all())
            total = len(item_ids)

            results = []
            for item_id in item_ids:
                savepoint = await session.begin_nested()
                try:
                    analysis = await analyze_news_item(item_id, session)
                    await savepoint.commit()
                    if analysis is not None:
                        results.append(analysis)
                except Exception as exc:
                    await savepoint.rollback()
                    logger.warning("Failed to analyze news item %s: %s", item_id, exc)
                    results.append({"status": "failed", "news_item_id": str(item_id)})
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
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        from database.core import session_scope
        from database.models.news import DetectedEvent, EventDuplicate

        async with session_scope() as session:
            event = await session.get(DetectedEvent, UUID(event_id))
            if event is None:
                return {"event_id": event_id, "is_duplicate": False}

            similar = (
                (
                    await session.execute(
                        sa.select(DetectedEvent)
                        .where(
                            DetectedEvent.id != event.id,
                            DetectedEvent.event_type == event.event_type,
                            DetectedEvent.issuer_id == event.issuer_id,
                            DetectedEvent.created_at < event.created_at,
                            DetectedEvent.created_at >= event.created_at - timedelta(hours=24),
                        )
                        .order_by(DetectedEvent.created_at, DetectedEvent.id)
                    )
                )
                .scalars()
                .first()
            )

            if similar:
                await session.execute(
                    pg_insert(EventDuplicate)
                    .values(
                        original_id=similar.id,
                        duplicate_id=event.id,
                        similarity_method="type+issuer+time",
                        similarity_score=0.8,
                    )
                    .on_conflict_do_nothing(index_elements=[EventDuplicate.duplicate_id])
                )
                return {
                    "event_id": event_id,
                    "is_duplicate": True,
                    "original_id": str(similar.id),
                }

            return {"event_id": event_id, "is_duplicate": False}


@activity.defn(name="deduplicate_recent_events")
async def deduplicate_recent_events(params: dict[str, Any]) -> dict[str, int]:
    """Idempotently mark recent events that repeat issuer/type within 24 hours."""
    with activity_span("deduplicate_recent_events"):
        import sqlalchemy as sa
        from sqlalchemy.dialects.postgresql import insert as pg_insert
        from sqlalchemy.orm import aliased

        from database.core import session_scope
        from database.models.news import DetectedEvent, EventDuplicate

        lookback_hours = int(params.get("lookback_hours", 24))
        batch_size = int(params.get("batch_size", 500))
        if lookback_hours < 1 or lookback_hours > 24 * 30:
            raise ValueError("lookback_hours must be between 1 and 720")
        if batch_size < 1 or batch_size > 5000:
            raise ValueError("batch_size must be between 1 and 5000")

        current = aliased(DetectedEvent)
        previous = aliased(DetectedEvent)
        original_id = (
            sa.select(previous.id)
            .where(
                previous.id != current.id,
                previous.issuer_id == current.issuer_id,
                previous.event_type == current.event_type,
                previous.created_at < current.created_at,
                previous.created_at >= current.created_at - timedelta(hours=24),
            )
            .order_by(previous.created_at, previous.id)
            .limit(1)
            .correlate(current)
            .scalar_subquery()
        )
        already_marked = sa.exists(sa.select(EventDuplicate.id).where(EventDuplicate.duplicate_id == current.id))

        async with session_scope() as session:
            rows = (
                await session.execute(
                    sa.select(current.id, original_id.label("original_id"))
                    .where(
                        current.created_at >= datetime.now(UTC) - timedelta(hours=lookback_hours),
                        current.issuer_id.is_not(None),
                        current.event_type.is_not(None),
                        ~already_marked,
                    )
                    .order_by(current.created_at, current.id)
                    .limit(batch_size)
                )
            ).all()
            pairs = [
                {
                    "original_id": row.original_id,
                    "duplicate_id": row.id,
                    "similarity_method": "type+issuer+time",
                    "similarity_score": 0.8,
                }
                for row in rows
                if row.original_id is not None
            ]
            inserted = 0
            if pairs:
                statement = (
                    pg_insert(EventDuplicate)
                    .values(pairs)
                    .on_conflict_do_nothing(index_elements=[EventDuplicate.duplicate_id])
                    .returning(EventDuplicate.id)
                )
                inserted = len((await session.execute(statement)).scalars().all())
            return {"scanned": len(rows), "duplicates_created": inserted}


NEWS_EXTRACTION_ACTIVITIES = (
    fetch_news_items,
    analyze_single_news_item,
    batch_analyze_news,
    detect_event_duplicates,
    deduplicate_recent_events,
)
