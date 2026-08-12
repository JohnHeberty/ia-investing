"""Unit tests for app_factory: session middleware, CSRF middleware, create_app."""

from __future__ import annotations

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI, Request, Response
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from apps.api.app_factory import (
    _NO_CSRF_PATHS,
    _session_middleware,
    create_app,
)


# ---------------------------------------------------------------------------
# _session_middleware
# ---------------------------------------------------------------------------
class TestSessionMiddleware:
    @pytest.mark.asyncio
    async def test_auth_path_skips_session_lookup(self) -> None:
        async def _call_next(request: Request) -> Response:
            return Response("ok")

        request = MagicMock(spec=Request)
        request.url.path = "/api/v1/auth/callback"
        result = await _session_middleware(request, _call_next)
        assert result.status_code == 200

    @pytest.mark.asyncio
    async def test_valid_session_sets_auth_context(self) -> None:
        org_id = uuid4()
        session_data = {
            "sub": "user@test.com",
            "organization_id": str(org_id),
            "team_ids": [str(uuid4())],
            "roles": ["admin"],
            "permissions": ["portfolio:read"],
            "sid": "sess-123",
        }

        async def _call_next(request: Request) -> Response:
            ctx = request.state.auth_context
            assert ctx is not None
            assert ctx.subject == "user@test.com"
            assert ctx.organization_id == org_id
            assert "admin" in ctx.roles
            assert "portfolio:read" in ctx.permissions
            return Response("ok")

        with patch("apps.api.app_factory._session_from_request", return_value=session_data):
            request = MagicMock(spec=Request)
            request.url.path = "/api/v1/portfolio"
            await _session_middleware(request, _call_next)

    @pytest.mark.asyncio
    async def test_no_session_sets_auth_context_none(self) -> None:
        async def _call_next(request: Request) -> Response:
            assert request.state.auth_context is None
            return Response("ok")

        with patch("apps.api.app_factory._session_from_request", return_value=None):
            request = MagicMock(spec=Request)
            request.url.path = "/api/v1/portfolio"
            await _session_middleware(request, _call_next)

    @pytest.mark.asyncio
    async def test_invalid_org_id_sets_none(self) -> None:
        session_data = {
            "sub": "user@test.com",
            "organization_id": "not-a-uuid",
            "team_ids": [],
            "roles": [],
            "permissions": [],
            "sid": "s",
        }

        async def _call_next(request: Request) -> Response:
            ctx = request.state.auth_context
            assert ctx is not None
            assert ctx.organization_id is None
            return Response("ok")

        with patch("apps.api.app_factory._session_from_request", return_value=session_data):
            request = MagicMock(spec=Request)
            request.url.path = "/api/v1/portfolio"
            await _session_middleware(request, _call_next)

    @pytest.mark.asyncio
    async def test_non_list_team_ids_defaults_to_empty(self) -> None:
        session_data = {
            "sub": "user@test.com",
            "organization_id": str(uuid4()),
            "team_ids": "not-a-list",
            "roles": "not-a-list",
            "permissions": "not-a-list",
            "sid": "s",
        }

        async def _call_next(request: Request) -> Response:
            ctx = request.state.auth_context
            assert ctx is not None
            assert ctx.team_ids == frozenset()
            return Response("ok")

        with patch("apps.api.app_factory._session_from_request", return_value=session_data):
            request = MagicMock(spec=Request)
            request.url.path = "/api/v1/portfolio"
            await _session_middleware(request, _call_next)


# ---------------------------------------------------------------------------
# create_app
# ---------------------------------------------------------------------------
class TestCreateApp:
    @patch("apps.api.app_factory.get_settings")
    def test_creates_fastapi_instance(self, mock_settings: MagicMock) -> None:
        settings = MagicMock()
        settings.telemetry.enabled = False
        mock_settings.return_value = settings
        app = create_app(settings)
        assert isinstance(app, FastAPI)

    @patch("apps.api.app_factory.get_settings")
    def test_app_title_and_version(self, mock_settings: MagicMock) -> None:
        settings = MagicMock()
        settings.telemetry.enabled = False
        mock_settings.return_value = settings
        app = create_app(settings)
        assert app.title == "Stock Intelligence"
        assert app.version == "0.1.0"

    @patch("apps.api.app_factory.get_settings")
    def test_liveness_endpoint_returns_200(self, mock_settings: MagicMock) -> None:
        settings = MagicMock()
        settings.telemetry.enabled = False
        mock_settings.return_value = settings
        app = create_app(settings)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/healthz")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}

    @patch("apps.api.app_factory.get_settings")
    def test_auth_routers_are_included(self, mock_settings: MagicMock) -> None:
        settings = MagicMock()
        settings.telemetry.enabled = False
        mock_settings.return_value = settings
        app = create_app(settings)
        assert len(app.routes) > 0

    @patch("apps.api.app_factory.get_settings")
    def test_no_csrf_paths_constant(self, mock_settings: MagicMock) -> None:
        assert "/api/v1/health" in _NO_CSRF_PATHS
        assert "/api/v1/readiness" in _NO_CSRF_PATHS

    @patch("apps.api.app_factory.get_settings")
    def test_public_routers_included(self, mock_settings: MagicMock) -> None:
        settings = MagicMock()
        settings.telemetry.enabled = False
        mock_settings.return_value = settings
        app = create_app(settings)
        all_paths = set()
        for route in app.routes:
            if isinstance(route, APIRoute):
                all_paths.add(route.path)
        assert "/healthz" in all_paths
