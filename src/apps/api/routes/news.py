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
    fetch_and_persist_news_items,
    list_detected_events,
    list_news_items,
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
