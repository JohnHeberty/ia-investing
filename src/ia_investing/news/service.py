"""News collection and impact classification service.

Fetches RSS articles, deduplicates, persists to DB, and runs LLM analysis
to detect events and classify impact on investment theses.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from typing import Any
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from connectors.news import NewsArticle, fetch_google_news_rss, fetch_reuters_rss
from database.models.catalog import Ticker
from database.models.news import (
    DetectedEvent,
    EventImpact,
    NewsEntityLink,
    NewsItem,
    NewsSource,
)
from database.models.thesis_domain import ResearchThesis
from schemas._news import NewsAnalysis

logger = logging.getLogger(__name__)

_NEWS_SYSTEM_PROMPT = """\
Você é um analista de notícias financeiras especializado no mercado brasileiro.
Analise a notícia fornecida e retorne um JSON com a seguinte estrutura:
{
  "verdict": "positive" | "negative" | "neutral" | "mixed",
  "confidence": float (0.0 a 1.0),
  "summary_pt": "resumo em português (max 2 frases)",
  "materiality_score": float (-1.0 a +1.0),
  "thesis_effect": "strengthen" | "weaken" | "no_change",
  "event_type": "earnings" | "guidance" | "ma" | "regulation" | "dividend" \
    | "governance" | "market" | "sector" | "other",
  "affected_metrics": ["receita", "margem", "dividend_yield", ...],
  "time_horizon": "immediate" | "short_term" | "medium_term" | "long_term",
  "key_claims": ["claim1", "claim2", ...],
  "affected_issuers": [{"ticker": "PETR4", "relevance": 0.9}, ...]
}
Seja preciso e conservador nas estimativas de materialidade.
Responda APENAS com o JSON, sem texto adicional."""


def _content_hash(title: str, url: str) -> str:
    canonical = f"{(title or '').strip().lower()}|{(url or '').strip().lower()}"
    return hashlib.sha256(canonical.encode()).hexdigest()


async def _get_or_create_source(session: AsyncSession, source_name: str) -> NewsSource:
    result = await session.execute(
        sa.select(NewsSource).where(NewsSource.name == source_name)
    )
    source = result.scalar_one_or_none()
    if source is None:
        source = NewsSource(
            name=source_name,
            trust_level=3,
            source_type="rss",
            is_active=True,
        )
        session.add(source)
        await session.flush()
    return source


async def fetch_and_persist_news_items(
    issuer_id: UUID,
    session: AsyncSession,
    max_results: int = 20,
) -> list[dict[str, Any]]:
    """Fetch RSS articles for an issuer's tickers and persist new items.

    Returns list of newly persisted news item dicts.
    """
    tickers = (await session.execute(
        sa.select(Ticker.symbol).where(Ticker.issuer_id == issuer_id)
    )).scalars().all()

    if not tickers:
        logger.info("No tickers found for issuer %s", issuer_id)
        return []

    all_articles: list[NewsArticle] = []
    for symbol in tickers:
        try:
            articles = await fetch_google_news_rss(symbol, max_results=max_results // len(tickers) + 5)
            all_articles.extend(articles)
        except Exception as exc:
            logger.warning("Failed to fetch Google News for %s: %s", symbol, exc)
        try:
            articles = await fetch_reuters_rss(symbol, max_results=max_results // len(tickers) + 5)
            all_articles.extend(articles)
        except Exception as exc:
            logger.warning("Failed to fetch Reuters for %s: %s", symbol, exc)

    if not all_articles:
        return []

    existing_hashes = set()
    result = await session.execute(
        sa.select(NewsItem.raw_data["content_hash"].as_string()).where(
            NewsItem.raw_data["content_hash"].isnot(None)
        )
    )
    for row in result:
        if row[0]:
            existing_hashes.add(row[0])

    persisted: list[dict[str, Any]] = []
    for article in all_articles:
        content_hash = _content_hash(article.title, article.url)
        if content_hash in existing_hashes:
            continue

        source = await _get_or_create_source(session, article.source)
        item = NewsItem(
            source_id=source.id,
            title=article.title,
            body=article.body,
            url=article.url,
            published_at=article.published_at,
            retrieved_at=article.retrieved_at,
            language=article.language,
            raw_data={"content_hash": content_hash},
            is_processed=False,
        )
        session.add(item)
        existing_hashes.add(content_hash)
        persisted.append({
            "id": item.id,
            "title": article.title,
            "url": article.url,
            "source": article.source,
            "published_at": article.published_at.isoformat(),
        })

    await session.flush()
    logger.info("Persisted %d new news items for issuer %s", len(persisted), issuer_id)
    return persisted


async def generate_llm_news_analysis(title: str, body: str) -> NewsAnalysis | None:
    """Call the LLM to analyze a news article.

    Returns NewsAnalysis or None on failure.
    """
    try:
        from ia_investing.settings import get_settings
        settings = get_settings()

        if settings.ai.provider == "mock":
            return None

        from ia_investing.ai.gateway import ChatCompletionRequest, ChatMessage, create_gateway_provider
        gw = settings.ai.gateway

        if not gw.base_url or not gw.api_key.get_secret_value():
            logger.info("LLM gateway not configured, skipping news analysis")
            return None

        provider = create_gateway_provider(
            provider=gw.provider,
            api_key=gw.api_key.get_secret_value(),
            default_model=gw.model,
            base_url=gw.base_url,
            timeout=min(gw.timeout, 30.0),
            max_retries=1,
        )

        user_msg = f"""Título: {title}

Corpo: {body[:2000]}"""

        request = ChatCompletionRequest(
            messages=[
                ChatMessage(role="system", content=_NEWS_SYSTEM_PROMPT),
                ChatMessage(role="user", content=user_msg),
            ],
            model=gw.model,
            temperature=0.2,
            max_tokens=800,
        )

        response = await asyncio.wait_for(
            provider.gateway.chat_completion(request),
            timeout=30.0,
        )
        content = response.content

        json_start = content.find("{")
        json_end = content.rfind("}") + 1
        if json_start >= 0 and json_end > json_start:
            data = json.loads(content[json_start:json_end])
            return NewsAnalysis(**data)

        return None
    except TimeoutError:
        logger.warning("LLM news analysis timed out after 30s")
        return None
    except Exception as exc:
        logger.warning("LLM news analysis failed: %s", exc)
        return None


async def _resolve_issuer_ids_from_tickers(
    session: AsyncSession, affected_issuers: list[dict[str, Any]]
) -> list[UUID]:
    """Resolve ticker symbols to issuer UUIDs."""
    tickers = [item.get("ticker", "") for item in affected_issuers if item.get("ticker")]
    if not tickers:
        return []
    result = await session.execute(
        sa.select(Ticker.issuer_id, Ticker.symbol).where(Ticker.symbol.in_(tickers))
    )
    return [row[0] for row in result]


async def analyze_news_item(
    news_item_id: UUID,
    session: AsyncSession,
) -> dict[str, Any] | None:
    """Analyze a news item via LLM and persist DetectedEvent + EventImpact records.

    Returns the analysis dict or None if analysis fails.
    """
    item = await session.get(NewsItem, news_item_id)
    if item is None:
        logger.warning("News item %s not found", news_item_id)
        return None

    title = item.title or ""
    body = item.body or ""
    analysis = await generate_llm_news_analysis(title, body)
    if analysis is None:
        return {"status": "llm_unavailable", "news_item_id": str(news_item_id)}

    affected_issuer_ids = await _resolve_issuer_ids_from_tickers(
        session, [{"ticker": t} for t in (analysis.model_dump().get("affected_issuers") or [])]
    )

    event = DetectedEvent(
        news_item_id=news_item_id,
        issuer_id=affected_issuer_ids[0] if affected_issuer_ids else None,
        event_type=analysis.event_type,
        description=analysis.summary_pt,
        materiality_score=analysis.materiality_score,
        direction_hint=analysis.verdict,
        time_horizon=analysis.time_horizon,
        affected_metrics={"metrics": analysis.affected_metrics, "key_claims": analysis.key_claims},
    )
    session.add(event)
    await session.flush()

    for issuer_id in affected_issuer_ids:
        link = NewsEntityLink(
            news_item_id=news_item_id,
            issuer_id=issuer_id,
            relevance_score=abs(analysis.materiality_score),
        )
        session.add(link)

    active_theses = (await session.execute(
        sa.select(ResearchThesis.id).where(
            ResearchThesis.issuer_id.in_(affected_issuer_ids),
            ResearchThesis.status == "active",
        )
    )).scalars().all()

    for thesis_id in active_theses:
        impact = EventImpact(
            event_id=event.id,
            thesis_id=thesis_id,
            impact_score=analysis.materiality_score,
            confidence=analysis.confidence,
            reasoning=analysis.summary_pt,
            thesis_effect=analysis.thesis_effect,
        )
        session.add(impact)

    item.is_processed = True
    item.sentiment_score = analysis.materiality_score
    await session.flush()

    logger.info(
        "Analyzed news item %s: event_type=%s verdict=%s materiality=%.2f",
        news_item_id, analysis.event_type, analysis.verdict, analysis.materiality_score,
    )
    return {
        "status": "analyzed",
        "news_item_id": str(news_item_id),
        "event_id": str(event.id),
        "event_type": analysis.event_type,
        "verdict": analysis.verdict,
        "materiality_score": analysis.materiality_score,
        "thesis_effect": analysis.thesis_effect,
        "affected_issuer_ids": [str(i) for i in affected_issuer_ids],
    }


async def list_news_items(
    session: AsyncSession,
    issuer_id: UUID | None = None,
    is_processed: bool | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    """List news items with optional filtering. Returns (items, total)."""
    query = sa.select(NewsItem)
    count_query = sa.select(sa.func.count(NewsItem.id))

    if issuer_id is not None:
        query = query.join(NewsEntityLink, NewsEntityLink.news_item_id == NewsItem.id).where(
            NewsEntityLink.issuer_id == issuer_id
        )
        count_query = count_query.join(NewsEntityLink, NewsEntityLink.news_item_id == NewsItem.id).where(
            NewsEntityLink.issuer_id == issuer_id
        )

    if is_processed is not None:
        query = query.where(NewsItem.is_processed == is_processed)
        count_query = count_query.where(NewsItem.is_processed == is_processed)

    total = (await session.execute(count_query)).scalar() or 0

    result = await session.execute(
        query.order_by(NewsItem.created_at.desc()).limit(limit).offset(offset)
    )
    items = []
    for row in result.scalars():
        items.append({
            "id": str(row.id),
            "title": row.title,
            "body": row.body,
            "url": row.url,
            "source_id": str(row.source_id),
            "published_at": row.published_at.isoformat() if row.published_at else None,
            "language": row.language,
            "sentiment_score": row.sentiment_score,
            "is_processed": row.is_processed,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        })

    return items, total


async def list_detected_events(
    session: AsyncSession,
    issuer_id: UUID | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    """List detected events with optional issuer filtering."""
    query = sa.select(DetectedEvent)
    count_query = sa.select(sa.func.count(DetectedEvent.id))

    if issuer_id is not None:
        query = query.where(DetectedEvent.issuer_id == issuer_id)
        count_query = count_query.where(DetectedEvent.issuer_id == issuer_id)

    total = (await session.execute(count_query)).scalar() or 0

    result = await session.execute(
        query.order_by(DetectedEvent.created_at.desc()).limit(limit).offset(offset)
    )
    events = []
    for row in result.scalars():
        events.append({
            "id": str(row.id),
            "news_item_id": str(row.news_item_id) if row.news_item_id else None,
            "issuer_id": str(row.issuer_id) if row.issuer_id else None,
            "event_type": row.event_type,
            "description": row.description,
            "materiality_score": row.materiality_score,
            "direction_hint": row.direction_hint,
            "time_horizon": row.time_horizon,
            "affected_metrics": row.affected_metrics,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        })

    return events, total
