"""News collection and impact classification service.

Fetches RSS articles, deduplicates, persists to DB, and runs LLM analysis
to detect events and classify impact on investment theses.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from datetime import timedelta
from typing import Any
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
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

DEFAULT_SOURCE_TRUST_LEVEL = 3
DEFAULT_MAX_RESULTS = 20
DEFAULT_LIST_LIMIT = 50
DEFAULT_PORTFOLIO_IMPACT_LIMIT = 50
NEWS_DEDUP_WINDOW_DAYS = 7
LLM_ANALYSIS_TIMEOUT_S = 30.0
LLM_BODY_CHAR_LIMIT = 2000

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
    result = await session.execute(sa.select(NewsSource).where(NewsSource.name == source_name))
    source = result.scalar_one_or_none()
    if source is None:
        source = NewsSource(
            name=source_name,
            trust_level=DEFAULT_SOURCE_TRUST_LEVEL,
            source_type="rss",
            is_active=True,
        )
        savepoint = await session.begin_nested()
        try:
            session.add(source)
            await session.flush()
            await savepoint.commit()
        except IntegrityError:
            await savepoint.rollback()
            result = await session.execute(sa.select(NewsSource).where(NewsSource.name == source_name))
            source = result.scalar_one()
    return source


async def _load_existing_hashes(session: AsyncSession) -> set[str]:
    """Load content hashes from the last 7 days for dedup."""
    result = await session.execute(
        sa.select(NewsItem.raw_data["content_hash"].as_string()).where(
            NewsItem.raw_data["content_hash"].isnot(None),
            NewsItem.created_at >= sa.func.now() - timedelta(days=NEWS_DEDUP_WINDOW_DAYS),
        )
    )
    return {row[0] for row in result if row[0]}


async def _persist_articles(
    session: AsyncSession,
    all_articles: list[NewsArticle],
    existing_hashes: set[str],
) -> list[dict[str, Any]]:
    """Persist new articles, deduplicating by content hash. Returns persisted items."""
    persisted: list[dict[str, Any]] = []
    source_cache: dict[str, NewsSource] = {}
    for article in all_articles:
        content_hash = _content_hash(article.title, article.url)
        if content_hash in existing_hashes:
            continue

        if article.source not in source_cache:
            source_cache[article.source] = await _get_or_create_source(session, article.source)
        source = source_cache[article.source]
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
        savepoint = await session.begin_nested()
        try:
            session.add(item)
            await session.flush()
            await savepoint.commit()
        except IntegrityError:
            await savepoint.rollback()
            existing_hashes.add(content_hash)
            continue
        existing_hashes.add(content_hash)
        persisted.append(
            {
                "id": item.id,
                "title": article.title,
                "url": article.url,
                "source": article.source,
                "published_at": article.published_at.isoformat() if article.published_at else None,
            }
        )
    return persisted


async def fetch_and_persist_news_items(
    issuer_id: UUID,
    session: AsyncSession,
    max_results: int = DEFAULT_MAX_RESULTS,
) -> list[dict[str, Any]]:
    """Fetch RSS articles for an issuer's tickers and persist new items.

    Returns list of newly persisted news item dicts.
    """
    tickers = (await session.execute(sa.select(Ticker.symbol).where(Ticker.issuer_id == issuer_id))).scalars().all()

    if not tickers:
        logger.info("No tickers found for issuer %s", issuer_id)
        return []

    all_articles: list[NewsArticle] = []

    async def _safe_fetch(fetch_fn: Any, symbol: str) -> list[NewsArticle]:
        try:
            return await fetch_fn(symbol, max_results=max_results // len(tickers) + 5)
        except Exception as exc:
            logger.warning("Failed to fetch %s for %s: %s", fetch_fn.__name__, symbol, exc)
            return []

    fetch_tasks = []
    for symbol in tickers:
        fetch_tasks.append(_safe_fetch(fetch_google_news_rss, symbol))
        fetch_tasks.append(_safe_fetch(fetch_reuters_rss, symbol))

    results = await asyncio.gather(*fetch_tasks)
    for articles in results:
        all_articles.extend(articles)

    if not all_articles:
        return []

    existing_hashes = await _load_existing_hashes(session)
    persisted = await _persist_articles(session, all_articles, existing_hashes)
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

Corpo: {body[:LLM_BODY_CHAR_LIMIT]}"""

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
            timeout=LLM_ANALYSIS_TIMEOUT_S,
        )
        content = response.content

        json_start = content.find("{")
        json_end = content.rfind("}") + 1
        if json_start >= 0 and json_end > json_start:
            data = json.loads(content[json_start:json_end])
            return NewsAnalysis(**data)

        return None
    except TimeoutError:
        logger.warning("LLM news analysis timed out after %.0fs", LLM_ANALYSIS_TIMEOUT_S)
        return None
    except Exception as exc:
        logger.warning("LLM news analysis failed: %s", exc)
        return None


async def _resolve_issuer_ids_from_tickers(session: AsyncSession, affected_issuers: list[dict[str, Any]]) -> list[UUID]:
    """Resolve ticker symbols to issuer UUIDs."""
    tickers = list({item.get("ticker", "") for item in affected_issuers if item.get("ticker")})
    if not tickers:
        return []
    result = await session.execute(sa.select(Ticker.issuer_id).where(Ticker.symbol.in_(tickers)).distinct())
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
        return {"status": "not_found", "news_item_id": str(news_item_id)}

    existing = (
        await session.execute(sa.select(DetectedEvent.id).where(DetectedEvent.news_item_id == news_item_id).limit(1))
    ).scalar_one_or_none()
    if existing is not None:
        logger.info("News item %s already analyzed (event %s), skipping", news_item_id, existing)
        return {"status": "already_analyzed", "news_item_id": str(news_item_id), "event_id": str(existing)}

    title = item.title or ""
    body = item.body or ""
    analysis = await generate_llm_news_analysis(title, body)
    if analysis is None:
        return {"status": "llm_unavailable", "news_item_id": str(news_item_id)}

    affected_issuer_ids = await _resolve_issuer_ids_from_tickers(session, analysis.affected_issuers or [])

    if not affected_issuer_ids:
        logger.info(
            "News item %s: no issuer matched for tickers %s — creating unresolved event",
            news_item_id,
            [i.get("ticker") for i in (analysis.affected_issuers or [])],
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

    active_theses: list[UUID] = []
    if affected_issuer_ids:
        active_theses = list(
            (
                await session.execute(
                    sa.select(ResearchThesis.id).where(
                        ResearchThesis.issuer_id.in_(affected_issuer_ids),
                        ResearchThesis.status == "active",
                    )
                )
            )
            .scalars()
            .all()
        )

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
        news_item_id,
        analysis.event_type,
        analysis.verdict,
        analysis.materiality_score,
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
    limit: int = DEFAULT_LIST_LIMIT,
    offset: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    """List news items with optional filtering. Returns (items, total)."""
    base = sa.select(NewsItem.id).distinct()
    if issuer_id is not None:
        base = base.join(NewsEntityLink, NewsEntityLink.news_item_id == NewsItem.id).where(
            NewsEntityLink.issuer_id == issuer_id
        )
    if is_processed is not None:
        base = base.where(NewsItem.is_processed.is_(is_processed))

    count_query = sa.select(sa.func.count()).select_from(base.subquery())
    total = (await session.execute(count_query)).scalar() or 0

    query = (
        sa.select(NewsItem, NewsSource.name.label("source_name"))
        .join(NewsSource, NewsSource.id == NewsItem.source_id, isouter=True)
        .distinct()
    )
    if issuer_id is not None:
        query = query.join(NewsEntityLink, NewsEntityLink.news_item_id == NewsItem.id).where(
            NewsEntityLink.issuer_id == issuer_id
        )
    if is_processed is not None:
        query = query.where(NewsItem.is_processed.is_(is_processed))

    result = await session.execute(query.order_by(NewsItem.created_at.desc()).limit(limit).offset(offset))
    items = []
    for row in result:
        item = row[0]
        source_name = row[1]
        items.append(
            {
                "id": str(item.id),
                "title": item.title,
                "body": item.body,
                "url": item.url,
                "source_id": str(item.source_id),
                "source_name": source_name,
                "published_at": item.published_at.isoformat() if item.published_at else None,
                "language": item.language,
                "sentiment_score": item.sentiment_score,
                "is_processed": item.is_processed,
                "created_at": item.created_at.isoformat() if item.created_at else None,
            }
        )

    return items, total


async def list_detected_events(
    session: AsyncSession,
    issuer_id: UUID | None = None,
    limit: int = DEFAULT_LIST_LIMIT,
    offset: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    """List detected events with optional issuer filtering."""
    query = sa.select(DetectedEvent)
    count_query = sa.select(sa.func.count(DetectedEvent.id))

    if issuer_id is not None:
        query = query.where(DetectedEvent.issuer_id == issuer_id)
        count_query = count_query.where(DetectedEvent.issuer_id == issuer_id)

    total = (await session.execute(count_query)).scalar() or 0

    result = await session.execute(query.order_by(DetectedEvent.created_at.desc()).limit(limit).offset(offset))
    events = []
    for row in result.scalars():
        events.append(
            {
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
            }
        )

    return events, total


async def get_detected_event(session: AsyncSession, event_id: UUID) -> dict[str, Any] | None:
    """Get a detected event with its impacts."""
    event = await session.get(DetectedEvent, event_id)
    if event is None:
        return None

    impacts = (await session.execute(sa.select(EventImpact).where(EventImpact.event_id == event_id))).scalars().all()

    return {
        "id": str(event.id),
        "news_item_id": str(event.news_item_id) if event.news_item_id else None,
        "issuer_id": str(event.issuer_id) if event.issuer_id else None,
        "event_type": event.event_type,
        "description": event.description,
        "materiality_score": event.materiality_score,
        "direction_hint": event.direction_hint,
        "time_horizon": event.time_horizon,
        "affected_metrics": event.affected_metrics,
        "created_at": event.created_at.isoformat() if event.created_at else None,
        "impacts": [
            {
                "id": str(imp.id),
                "thesis_id": str(imp.thesis_id) if imp.thesis_id else None,
                "impact_score": imp.impact_score,
                "confidence": imp.confidence,
                "reasoning": imp.reasoning,
                "thesis_effect": imp.thesis_effect,
                "created_at": imp.created_at.isoformat() if imp.created_at else None,
            }
            for imp in impacts
        ],
    }


async def list_news_sources(
    session: AsyncSession,
    is_active: bool | None = None,
) -> list[dict[str, Any]]:
    """List all news sources."""
    query = sa.select(NewsSource)
    if is_active is not None:
        query = query.where(NewsSource.is_active == is_active)
    result = await session.execute(query.order_by(NewsSource.name))
    return [
        {
            "id": str(row.id),
            "name": row.name,
            "url_pattern": row.url_pattern,
            "trust_level": row.trust_level,
            "source_type": row.source_type,
            "is_active": row.is_active,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        for row in result.scalars()
    ]


async def create_news_source(
    session: AsyncSession,
    name: str,
    url_pattern: str | None = None,
    source_type: str | None = None,
    trust_level: int = DEFAULT_SOURCE_TRUST_LEVEL,
) -> dict[str, Any]:
    """Create a new news source. Raises ValueError on duplicate name."""
    existing = (await session.execute(sa.select(NewsSource).where(NewsSource.name == name))).scalar_one_or_none()
    if existing is not None:
        raise ValueError(f"A source with name '{name}' already exists")

    source = NewsSource(
        name=name,
        url_pattern=url_pattern,
        source_type=source_type,
        trust_level=trust_level,
        is_active=True,
    )
    session.add(source)
    await session.flush()
    return {
        "id": str(source.id),
        "name": source.name,
        "url_pattern": source.url_pattern,
        "trust_level": source.trust_level,
        "source_type": source.source_type,
        "is_active": source.is_active,
    }


async def get_news_stats(session: AsyncSession) -> dict[str, Any]:
    """Get aggregated news statistics using separate subqueries to avoid cartesian products."""
    total_items = (await session.execute(sa.select(sa.func.count(NewsItem.id)))).scalar() or 0
    processed_items = (
        await session.execute(sa.select(sa.func.count(NewsItem.id)).where(NewsItem.is_processed.is_(True)))
    ).scalar() or 0

    total_events = (await session.execute(sa.select(sa.func.count(DetectedEvent.id)))).scalar() or 0
    positive_events = (
        await session.execute(
            sa.select(sa.func.count(DetectedEvent.id)).where(DetectedEvent.direction_hint == "positive")
        )
    ).scalar() or 0
    negative_events = (
        await session.execute(
            sa.select(sa.func.count(DetectedEvent.id)).where(DetectedEvent.direction_hint == "negative")
        )
    ).scalar() or 0

    total_impacts = (await session.execute(sa.select(sa.func.count(EventImpact.id)))).scalar() or 0
    active_sources = (
        await session.execute(sa.select(sa.func.count(NewsSource.id)).where(NewsSource.is_active.is_(True)))
    ).scalar() or 0

    return {
        "total_items": total_items,
        "processed_items": processed_items,
        "unprocessed_items": total_items - processed_items,
        "total_events": total_events,
        "positive_events": positive_events,
        "negative_events": negative_events,
        "neutral_events": total_events - positive_events - negative_events,
        "total_impacts": total_impacts,
        "active_sources": active_sources,
    }


async def get_portfolio_impacts(
    session: AsyncSession,
    limit: int = DEFAULT_PORTFOLIO_IMPACT_LIMIT,
) -> list[dict[str, Any]]:
    """Cross-reference news impacts with portfolio positions."""
    from database.models.portfolio_models import Portfolio, Position

    recent_events = (
        (
            await session.execute(
                sa.select(DetectedEvent)
                .where(DetectedEvent.created_at >= sa.func.now() - timedelta(days=NEWS_DEDUP_WINDOW_DAYS))
                .order_by(DetectedEvent.materiality_score.desc().nullslast())
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )

    if not recent_events:
        return []

    issuer_ids = {e.issuer_id for e in recent_events if e.issuer_id}

    if not issuer_ids:
        return []

    positions = (
        await session.execute(
            sa.select(
                Position.issuer_id,
                Position.portfolio_id,
                Position.quantity,
                Position.ticker_symbol,
                Portfolio.name.label("portfolio_name"),
            )
            .join(Portfolio, Portfolio.id == Position.portfolio_id)
            .where(
                Position.issuer_id.in_(issuer_ids),
            )
        )
    ).all()

    issuer_portfolios: dict[str, list[dict[str, Any]]] = {}
    for pos in positions:
        key = str(pos.issuer_id)
        if key not in issuer_portfolios:
            issuer_portfolios[key] = []
        issuer_portfolios[key].append(
            {
                "portfolio_id": str(pos.portfolio_id),
                "portfolio_name": pos.portfolio_name,
                "quantity": str(pos.quantity) if pos.quantity else "0",
                "ticker_symbol": pos.ticker_symbol,
            }
        )

    results = []
    for event in recent_events:
        if not event.issuer_id:
            continue
        key = str(event.issuer_id)
        if key in issuer_portfolios:
            for port_info in issuer_portfolios[key]:
                results.append(
                    {
                        "event_id": str(event.id),
                        "event_type": event.event_type,
                        "materiality_score": event.materiality_score,
                        "direction_hint": event.direction_hint,
                        "issuer_id": key,
                        "portfolio_id": port_info["portfolio_id"],
                        "portfolio_name": port_info["portfolio_name"],
                        "event_created_at": event.created_at.isoformat() if event.created_at else None,
                    }
                )

    return results[:limit]
