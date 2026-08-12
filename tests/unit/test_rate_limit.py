"""Tests for apps.api.middleware.rate_limit — sliding window, IP extraction, middleware."""

from __future__ import annotations

import asyncio
import ipaddress
import math
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from starlette.requests import Request
from starlette.responses import Response
from starlette.testclient import TestClient

from apps.api.middleware.rate_limit import (
    RateLimitExceededError,
    RateLimitMiddleware,
    SlidingWindowCounter,
    _find_request,
    _get_client_ip,
    _rate_limit_exception,
    _rate_limit_response,
    rate_limit,
)


# ---------------------------------------------------------------------------
# SlidingWindowCounter
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestSlidingWindowCounter:
    async def test_allows_requests_under_limit(self) -> None:
        counter = SlidingWindowCounter(max_requests=5, window_seconds=60.0)
        for _ in range(5):
            assert await counter.is_allowed("k") is True

    async def test_blocks_at_limit(self) -> None:
        counter = SlidingWindowCounter(max_requests=3, window_seconds=60.0)
        for _ in range(3):
            await counter.is_allowed("k")
        assert await counter.is_allowed("k") is False

    async def test_separate_keys(self) -> None:
        counter = SlidingWindowCounter(max_requests=2, window_seconds=60.0)
        await counter.is_allowed("a")
        await counter.is_allowed("a")
        assert await counter.is_allowed("a") is False
        assert await counter.is_allowed("b") is True

    async def test_retry_after_with_no_timestamps(self) -> None:
        counter = SlidingWindowCounter(max_requests=5, window_seconds=60.0)
        assert await counter.retry_after("missing") == 0.0

    async def test_retry_after_calculates_correctly(self) -> None:
        counter = SlidingWindowCounter(max_requests=1, window_seconds=10.0)
        await counter.is_allowed("k")
        retry = await counter.retry_after("k")
        assert 0 < retry <= 10.0

    async def test_window_expires(self) -> None:
        counter = SlidingWindowCounter(max_requests=1, window_seconds=0.01)
        await counter.is_allowed("k")
        assert await counter.is_allowed("k") is False
        await asyncio.sleep(0.02)
        assert await counter.is_allowed("k") is True


# ---------------------------------------------------------------------------
# _get_client_ip
# ---------------------------------------------------------------------------


class TestGetClientIp:
    def _make_request(
        self,
        client_host: str | None = "1.2.3.4",
        forwarded: str | None = None,
    ) -> Request:
        scope: dict = {
            "type": "http",
            "headers": [],
            "client": (client_host, 0) if client_host else None,
        }
        if forwarded:
            scope["headers"] = [(b"x-forwarded-for", forwarded.encode())]
        return Request(scope)

    def test_direct_ip_returned(self) -> None:
        req = self._make_request(client_host="5.6.7.8")
        assert _get_client_ip(req) == "5.6.7.8"

    def test_no_client_returns_unknown(self) -> None:
        req = self._make_request(client_host=None)
        assert _get_client_ip(req) == "unknown"

    def test_trusted_proxy_uses_forwarded(self) -> None:
        req = self._make_request(client_host="127.0.0.1", forwarded="10.0.0.1, 1.1.1.1")
        assert _get_client_ip(req) == "10.0.0.1"

    def test_private_ip_trusts_forwarded(self) -> None:
        req = self._make_request(client_host="192.168.1.1", forwarded="203.0.113.5")
        assert _get_client_ip(req) == "203.0.113.5"

    def test_loopback_trusts_forwarded(self) -> None:
        req = self._make_request(client_host="127.0.0.1", forwarded="203.0.113.5")
        assert _get_client_ip(req) == "203.0.113.5"

    def test_public_ip_ignores_forwarded(self) -> None:
        req = self._make_request(client_host="8.8.8.8", forwarded="10.0.0.1")
        assert _get_client_ip(req) == "8.8.8.8"

    def test_invalid_forwarded_falls_back(self) -> None:
        req = self._make_request(client_host="127.0.0.1", forwarded="not-an-ip")
        assert _get_client_ip(req) == "127.0.0.1"

    def test_no_forwarded_header(self) -> None:
        req = self._make_request(client_host="1.2.3.4", forwarded=None)
        assert _get_client_ip(req) == "1.2.3.4"


# ---------------------------------------------------------------------------
# _find_request
# ---------------------------------------------------------------------------


class TestFindRequest:
    def test_finds_in_args(self) -> None:
        req = MagicMock(spec=Request)
        assert _find_request((req,), {}) is req

    def test_finds_in_kwargs(self) -> None:
        req = MagicMock(spec=Request)
        assert _find_request((), {"request": req}) is req

    def test_returns_none_when_not_found(self) -> None:
        assert _find_request(("hello",), {"x": 1}) is None

    def test_prefers_args_over_kwargs(self) -> None:
        req1 = MagicMock(spec=Request)
        req2 = MagicMock(spec=Request)
        assert _find_request((req1,), {"r": req2}) is req1


# ---------------------------------------------------------------------------
# rate_limit decorator
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestRateLimitDecorator:
    async def test_allows_within_limit(self) -> None:
        @rate_limit("test", max_requests=3, window_seconds=60.0)
        async def handler(request: Request) -> str:
            return "ok"

        req = MagicMock(spec=Request)
        req.client = MagicMock(host="1.2.3.4")
        req.headers = {}
        assert await handler(req) == "ok"

    async def test_raises_when_exceeded(self) -> None:
        @rate_limit("test", max_requests=2, window_seconds=60.0)
        async def handler(request: Request) -> str:
            return "ok"

        req = MagicMock(spec=Request)
        req.client = MagicMock(host="1.2.3.4")
        req.headers = {}
        await handler(req)
        await handler(req)
        with pytest.raises(RateLimitExceededError):
            await handler(req)

    async def test_no_request_arg_passes_through(self) -> None:
        @rate_limit("test", max_requests=1, window_seconds=60.0)
        async def handler() -> str:
            return "ok"

        assert await handler() == "ok"


# ---------------------------------------------------------------------------
# RateLimitMiddleware
# ---------------------------------------------------------------------------


class TestRateLimitMiddleware:
    @pytest.fixture(autouse=True)
    def _reset_global_limiters(self) -> None:
        """Reset shared global limiters so tests are independent."""
        import apps.api.middleware.rate_limit as rl
        rl._global_limiter = SlidingWindowCounter(1000, 60.0)
        rl._auth_limiter = SlidingWindowCounter(10, 60.0)
        rl._api_limiter = SlidingWindowCounter(100, 60.0)

    @pytest.mark.asyncio
    async def test_health_endpoint_bypasses(self) -> None:
        app = MagicMock()
        middleware = RateLimitMiddleware(app)

        async def call_next(request: Request) -> Response:
            return Response("ok")

        scope = {"type": "http", "path": "/api/v1/health", "headers": [], "client": ("1.2.3.4", 0)}
        request = Request(scope)
        response = await middleware.dispatch(request, call_next)
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_readiness_endpoint_bypasses(self) -> None:
        app = MagicMock()
        middleware = RateLimitMiddleware(app)

        async def call_next(request: Request) -> Response:
            return Response("ok")

        scope = {"type": "http", "path": "/api/v1/readiness", "headers": [], "client": ("1.2.3.4", 0)}
        request = Request(scope)
        response = await middleware.dispatch(request, call_next)
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_healthz_bypasses(self) -> None:
        app = MagicMock()
        middleware = RateLimitMiddleware(app)

        async def call_next(request: Request) -> Response:
            return Response("ok")

        scope = {"type": "http", "path": "/healthz", "headers": [], "client": ("1.2.3.4", 0)}
        request = Request(scope)
        response = await middleware.dispatch(request, call_next)
        assert response.status_code == 200

    @pytest.mark.asyncio
    @patch("apps.api.middleware.rate_limit.get_security_auditor")
    async def test_global_rate_limit_returns_429(self, mock_auditor: MagicMock) -> None:
        mock_auditor.return_value = MagicMock()
        app = MagicMock()
        middleware = RateLimitMiddleware(app)

        async def call_next(request: Request) -> Response:
            return Response("ok")

        response = Response("ok")
        for _ in range(1001):
            scope = {"type": "http", "path": "/api/v1/data", "headers": [], "client": ("1.2.3.4", 0)}
            request = Request(scope)
            response = await middleware.dispatch(request, call_next)
        assert response.status_code == 429


# ---------------------------------------------------------------------------
# _rate_limit_response / _rate_limit_exception
# ---------------------------------------------------------------------------


class TestRateLimitHelpers:
    def test_rate_limit_response_status(self) -> None:
        resp = _rate_limit_response()
        assert resp.status_code == 429
        assert "Retry-After" in resp.headers

    def test_rate_limit_exception_message(self) -> None:
        exc = _rate_limit_exception(30)
        assert isinstance(exc, RateLimitExceededError)
        assert exc.retry_after == 30
        assert "30" in str(exc)

    def test_rate_limit_exception_default(self) -> None:
        exc = RateLimitExceededError()
        assert exc.retry_after == 60
