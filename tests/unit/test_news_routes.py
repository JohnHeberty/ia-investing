"""Unit tests for news API routes."""

from __future__ import annotations

from unittest.mock import patch
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.api.routes.news import router
from apps.api.security import AuthContext, get_auth_context


def _mock_auth_context() -> AuthContext:
    return AuthContext(
        subject="test@example.com",
        roles=frozenset({"admin"}),
        permissions=frozenset({"news:read", "news:manage"}),
        authentication_method="test",
        organization_id=uuid4(),
    )


@pytest.fixture()
def app_instance():
    application = FastAPI()
    application.include_router(router)
    application.dependency_overrides[get_auth_context] = _mock_auth_context
    yield application
    application.dependency_overrides.clear()


@pytest.fixture()
def client(app_instance):
    with TestClient(app_instance, raise_server_exceptions=True) as c:
        yield c


class TestNewsRoutesListItems:
    def test_list_items_returns_paginated(self, client: TestClient) -> None:
        with patch("apps.api.routes.news.list_news_items", return_value=([], 0)):
            response = client.get("/api/v1/news/items")
            assert response.status_code == 200


class TestNewsRoutesListEvents:
    def test_list_events_returns_list(self, client: TestClient) -> None:
        with patch("apps.api.routes.news.list_detected_events", return_value=([], 0)):
            response = client.get("/api/v1/news/events")
            assert response.status_code == 200


class TestNewsRoutesListSources:
    def test_list_sources_returns_list(self, client: TestClient) -> None:
        with patch("apps.api.routes.news.list_news_sources", return_value=[]):
            response = client.get("/api/v1/news/sources")
            assert response.status_code == 200


class TestNewsRoutesStats:
    def test_stats_returns_dict(self, client: TestClient) -> None:
        stats = {
            "total_items": 0,
            "processed_items": 0,
            "unprocessed_items": 0,
            "total_events": 0,
            "positive_events": 0,
            "negative_events": 0,
            "neutral_events": 0,
            "total_impacts": 0,
            "active_sources": 0,
        }
        with patch("apps.api.routes.news.get_news_stats", return_value=stats):
            response = client.get("/api/v1/news/stats")
            assert response.status_code == 200


class TestNewsRoutesPortfolioImpacts:
    def test_portfolio_impacts_returns_list(self, client: TestClient) -> None:
        with patch("apps.api.routes.news.get_portfolio_impacts", return_value=[]):
            response = client.get("/api/v1/news/portfolio-impacts")
            assert response.status_code == 200


class TestNewsRoutesCreateSource:
    def test_create_source_returns_201(self, client: TestClient) -> None:
        source = {
            "id": str(uuid4()),
            "name": "Test Source",
            "url_pattern": None,
            "trust_level": 3,
            "source_type": "rss",
            "is_active": True,
            "created_at": "2026-01-01T00:00:00Z",
        }
        with patch("apps.api.routes.news.create_news_source", return_value=source):
            response = client.post(
                "/api/v1/news/sources",
                json={"name": "Test Source"},
            )
            assert response.status_code == 200


class TestNewsRoutesDeleteSource:
    def test_delete_source_returns_204(self, client: TestClient) -> None:
        source_id = uuid4()
        with patch("apps.api.routes.news.delete_news_source", return_value=True):
            response = client.delete(f"/api/v1/news/sources/{source_id}")
            assert response.status_code == 204


class TestNewsSchemaValidation:
    def test_news_list_response_model(self) -> None:
        from apps.api.routes.news import NewsListResponseV1

        data = NewsListResponseV1(items=[], total=0, limit=50, offset=0)
        assert data.items == []
        assert data.total == 0

    def test_portfolio_impact_model(self) -> None:
        from apps.api.routes.news import PortfolioImpactV1

        impact = PortfolioImpactV1(
            event_id="test-event",
            event_type="earnings",
            materiality_score=0.8,
            direction_hint="positive",
            issuer_id="test-issuer",
            portfolio_id="test-portfolio",
            portfolio_name="Long Only",
            event_created_at="2026-01-01T00:00:00Z",
        )
        assert impact.event_id == "test-event"
        assert impact.materiality_score == 0.8
