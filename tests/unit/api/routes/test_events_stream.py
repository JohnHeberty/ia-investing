"""Unit tests for apps.api.routes.events_stream."""

from __future__ import annotations

import json
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from apps.api.routes.events_stream import event_generator, router
from apps.api.security import AuthContext, get_auth_context


def _mock_auth() -> AuthContext:
    return AuthContext(
        subject="user@test.com",
        roles=frozenset({"admin"}),
        permissions=frozenset(),
        authentication_method="test",
        organization_id=uuid4(),
    )


async def _finite_event_generator() -> AsyncGenerator[str, None]:
    """Yields one heartbeat then stops, for testing the streaming response."""
    yield f"data: {json.dumps({'type': 'heartbeat', 'timestamp': '2026-01-01T00:00:00Z'})}\n\n"


@pytest.fixture()
def client() -> TestClient:
    app = FastAPI()
    app.dependency_overrides[get_auth_context] = _mock_auth
    app.include_router(router)
    return TestClient(app, raise_server_exceptions=False)


class TestEventsStreamRoute:
    def test_stream_returns_event_stream_content_type(self, client: TestClient) -> None:
        with patch("apps.api.routes.events_stream.event_generator", _finite_event_generator):
            resp = client.get("/api/v1/events-stream/stream")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "text/event-stream; charset=utf-8"

    def test_stream_returns_no_cache_header(self, client: TestClient) -> None:
        with patch("apps.api.routes.events_stream.event_generator", _finite_event_generator):
            resp = client.get("/api/v1/events-stream/stream")
        assert resp.headers["cache-control"] == "no-cache"

    def test_stream_returns_connection_keep_alive(self, client: TestClient) -> None:
        with patch("apps.api.routes.events_stream.event_generator", _finite_event_generator):
            resp = client.get("/api/v1/events-stream/stream")
        assert resp.headers["connection"] == "keep-alive"

    def test_stream_requires_authentication(self) -> None:
        app = FastAPI()
        app.include_router(router)
        unauthed = TestClient(app, raise_server_exceptions=False)
        resp = unauthed.get("/api/v1/events-stream/stream")
        assert resp.status_code == 401

    def test_stream_body_contains_sse_data(self, client: TestClient) -> None:
        with patch("apps.api.routes.events_stream.event_generator", _finite_event_generator):
            resp = client.get("/api/v1/events-stream/stream")
        assert resp.text.startswith("data: ")
        payload = json.loads(resp.text.removeprefix("data: ").strip())
        assert payload["type"] == "heartbeat"


class TestEventGenerator:
    @pytest.mark.asyncio()
    async def test_yields_sse_format(self) -> None:
        with patch("apps.api.routes.events_stream.asyncio.sleep", new_callable=AsyncMock):
            gen = event_generator()
            first = await gen.__anext__()
        assert first.startswith("data: ")
        assert first.endswith("\n\n")

    @pytest.mark.asyncio()
    async def test_yields_heartbeat_type(self) -> None:
        with patch("apps.api.routes.events_stream.asyncio.sleep", new_callable=AsyncMock):
            gen = event_generator()
            raw = await gen.__anext__()
        payload = json.loads(raw.removeprefix("data: ").strip())
        assert payload["type"] == "heartbeat"
        assert "timestamp" in payload

    @pytest.mark.asyncio()
    async def test_yields_valid_json(self) -> None:
        with patch("apps.api.routes.events_stream.asyncio.sleep", new_callable=AsyncMock):
            gen = event_generator()
            raw = await gen.__anext__()
        data_str = raw.removeprefix("data: ").strip()
        parsed = json.loads(data_str)
        assert isinstance(parsed, dict)
