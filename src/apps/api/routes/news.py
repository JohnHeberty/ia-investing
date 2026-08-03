"""News items and detected events endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.security import AuthContext, require_permission
from database.core import get_async_session
from ia_investing.news.service import (
    analyze_news_item,
    create_news_source,
    fetch_and_persist_news_items,
    get_detected_event,
    get_news_stats,
    get_portfolio_impacts,
    list_detected_events,
    list_news_items,
    list_news_sources,
)

router = APIRouter(prefix="/api/v1/news", tags=["news"])


class NewsItemV1(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str | None
    body: str | None
    url: str | None
    source_id: UUID
    published_at: datetime | None
    language: str | None
    sentiment_score: float | None
    is_processed: bool | None
    created_at: datetime | None


class NewsListResponseV1(BaseModel):
    items: list[NewsItemV1]
    total: int
    limit: int
    offset: int


class DetectedEventV1(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    news_item_id: UUID | None
    issuer_id: UUID | None
    event_type: str | None
    description: str | None
    materiality_score: float | None
    direction_hint: str | None
    time_horizon: str | None
    affected_metrics: dict[str, Any] | None
    created_at: datetime | None


class EventsListResponseV1(BaseModel):
    items: list[DetectedEventV1]
    total: int
    limit: int
    offset: int


class AnalyzeResponseV1(BaseModel):
    status: str
    news_item_id: str
    event_id: str | None = None
    event_type: str | None = None
    verdict: str | None = None
    materiality_score: float | None = None
    thesis_effect: str | None = None


class FetchResponseV1(BaseModel):
    persisted: list[dict[str, Any]]
    count: int


@router.get("/items", response_model=NewsListResponseV1)
async def get_news_items(
    issuer_id: UUID | None = Query(default=None),
    is_processed: bool | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    _auth: AuthContext = Depends(require_permission("news:read")),
    session: AsyncSession = Depends(get_async_session),
) -> NewsListResponseV1:
    items, total = await list_news_items(
        session, issuer_id=issuer_id, is_processed=is_processed, limit=limit, offset=offset
    )
    return NewsListResponseV1(
        items=[NewsItemV1(**item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/items/{item_id}", response_model=NewsItemV1)
async def get_news_item(
    item_id: UUID,
    _auth: AuthContext = Depends(require_permission("news:read")),
    session: AsyncSession = Depends(get_async_session),
) -> NewsItemV1:
    items, _ = await list_news_items(session, limit=200)
    for item in items:
        if item["id"] == str(item_id):
            return NewsItemV1(**item)
    raise HTTPException(status_code=404, detail="News item not found")


@router.post("/fetch/{issuer_id}", response_model=FetchResponseV1)
async def fetch_news(
    issuer_id: UUID,
    max_results: int = Query(default=20, ge=1, le=100),
    _auth: AuthContext = Depends(require_permission("news:write")),
    session: AsyncSession = Depends(get_async_session),
) -> FetchResponseV1:
    persisted = await fetch_and_persist_news_items(issuer_id, session, max_results=max_results)
    return FetchResponseV1(persisted=persisted, count=len(persisted))


@router.post("/analyze/{item_id}", response_model=AnalyzeResponseV1)
async def analyze_news(
    item_id: UUID,
    _auth: AuthContext = Depends(require_permission("news:write")),
    session: AsyncSession = Depends(get_async_session),
) -> AnalyzeResponseV1:
    result = await analyze_news_item(item_id, session)
    if result is None:
        raise HTTPException(status_code=503, detail="LLM analysis unavailable")
    return AnalyzeResponseV1(**result)


@router.get("/events", response_model=EventsListResponseV1)
async def get_events(
    issuer_id: UUID | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    _auth: AuthContext = Depends(require_permission("news:read")),
    session: AsyncSession = Depends(get_async_session),
) -> EventsListResponseV1:
    events, total = await list_detected_events(
        session, issuer_id=issuer_id, limit=limit, offset=offset
    )
    return EventsListResponseV1(
        items=[DetectedEventV1(**e) for e in events],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/events/{event_id}")
async def get_event_detail(
    event_id: UUID,
    _auth: AuthContext = Depends(require_permission("news:read")),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    result = await get_detected_event(session, event_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Event not found")
    return result


class NewsSourceV1(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    url_pattern: str | None
    trust_level: int | None
    source_type: str | None
    is_active: bool | None
    created_at: datetime | None


class SourceCreateRequestV1(BaseModel):
    name: str
    url_pattern: str | None = None
    source_type: str | None = None
    trust_level: int = 3


@router.get("/sources", response_model=list[NewsSourceV1])
async def get_sources(
    is_active: bool | None = Query(default=None),
    _auth: AuthContext = Depends(require_permission("news:read")),
    session: AsyncSession = Depends(get_async_session),
) -> list[NewsSourceV1]:
    sources = await list_news_sources(session, is_active=is_active)
    return [NewsSourceV1(**s) for s in sources]


@router.post("/sources", response_model=NewsSourceV1)
async def create_source(
    body: SourceCreateRequestV1,
    _auth: AuthContext = Depends(require_permission("news:manage")),
    session: AsyncSession = Depends(get_async_session),
) -> NewsSourceV1:
    source = await create_news_source(
        session,
        name=body.name,
        url_pattern=body.url_pattern,
        source_type=body.source_type,
        trust_level=body.trust_level,
    )
    return NewsSourceV1(**source)


class NewsStatsResponseV1(BaseModel):
    total_items: int
    processed_items: int
    unprocessed_items: int
    total_events: int
    positive_events: int
    negative_events: int
    neutral_events: int
    total_impacts: int
    active_sources: int


@router.get("/stats", response_model=NewsStatsResponseV1)
async def get_stats(
    _auth: AuthContext = Depends(require_permission("news:read")),
    session: AsyncSession = Depends(get_async_session),
) -> NewsStatsResponseV1:
    stats = await get_news_stats(session)
    return NewsStatsResponseV1(**stats)


class PortfolioImpactV1(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    event_id: str
    event_type: str | None
    materiality_score: float | None
    direction_hint: str | None
    issuer_id: str
    portfolio_id: str
    portfolio_name: str
    event_created_at: str | None


@router.get("/portfolio-impacts", response_model=list[PortfolioImpactV1])
async def get_portfolio_impacts_endpoint(
    limit: int = Query(default=50, ge=1, le=200),
    _auth: AuthContext = Depends(require_permission("news:read")),
    session: AsyncSession = Depends(get_async_session),
) -> list[PortfolioImpactV1]:
    impacts = await get_portfolio_impacts(session, limit=limit)
    return [PortfolioImpactV1(**i) for i in impacts]
