"""Unit tests for RequestHostValidator middleware."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Route
from starlette.testclient import TestClient

from apps.api.middleware.request_host_validator import (
    RequestHostValidator,
    _is_host_allowed,
    _is_private_ip,
)


# ---------------------------------------------------------------------------
# Pure function tests — _is_private_ip
# ---------------------------------------------------------------------------
class TestIsPrivateIp:
    def test_10_x_is_private(self) -> None:
        assert _is_private_ip("10.0.0.1") is True

    def test_172_16_is_private(self) -> None:
        assert _is_private_ip("172.16.0.1") is True

    def test_192_168_is_private(self) -> None:
        assert _is_private_ip("192.168.1.1") is True

    def test_127_is_private(self) -> None:
        assert _is_private_ip("127.0.0.1") is True

    def test_169_254_is_private(self) -> None:
        assert _is_private_ip("169.254.0.1") is True

    def test_public_ip_not_private(self) -> None:
        assert _is_private_ip("8.8.8.8") is False

    def test_public_ip_203_not_private(self) -> None:
        assert _is_private_ip("203.0.113.1") is False

    def test_ipv6_loopback_is_private(self) -> None:
        assert _is_private_ip("::1") is True

    def test_ipv6_link_local_is_private(self) -> None:
        assert _is_private_ip("fe80::1") is True

    def test_ipv6_unique_local_is_private(self) -> None:
        assert _is_private_ip("fc00::1") is True

    def test_ipv6_public_not_private(self) -> None:
        assert _is_private_ip("2001:db8::1") is False

    def test_hostname_not_ip_returns_false(self) -> None:
        assert _is_private_ip("example.com") is False


# ---------------------------------------------------------------------------
# Pure function tests — _is_host_allowed
# ---------------------------------------------------------------------------
class TestIsHostAllowed:
    def test_allowed_returns_true(self) -> None:
        assert _is_host_allowed("localhost", {"localhost"}) is True

    def test_not_allowed_returns_false(self) -> None:
        assert _is_host_allowed("evil.com", {"localhost"}) is False

    def test_empty_allowed_set_returns_false(self) -> None:
        assert _is_host_allowed("localhost", set()) is False


# ---------------------------------------------------------------------------
# Middleware dispatch tests
# ---------------------------------------------------------------------------
async def _dummy_handler(request: Request) -> Response:
    return Response("ok")


def _build_app(allowed_hosts: list[str] | None = None) -> Starlette:
    settings = MagicMock()
    settings.security.ssrf_allowed_internal_hosts = allowed_hosts or []
    with patch("apps.api.middleware.request_host_validator.get_settings", return_value=settings):
        app = Starlette(
            routes=[Route("/test", _dummy_handler)],
            middleware=[Middleware(RequestHostValidator)],
        )
    return app


class TestRequestHostValidatorDispatch:
    def test_public_host_passes_through(self) -> None:
        app = _build_app()
        with patch("apps.api.middleware.request_host_validator.get_settings") as mock_settings:
            mock_settings.return_value.security.ssrf_allowed_internal_hosts = []
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.get("/test", headers={"host": "example.com"})
            assert resp.status_code == 200

    def test_private_host_blocked(self) -> None:
        app = _build_app(allowed_hosts=[])
        with (
            patch("apps.api.middleware.request_host_validator.get_settings") as mock_settings,
            patch("apps.api.middleware.request_host_validator.emit_security_event"),
            patch("apps.api.middleware.request_host_validator.get_security_auditor"),
        ):
            mock_settings.return_value.security.ssrf_allowed_internal_hosts = []
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.get("/test", headers={"host": "169.254.169.254"})
            assert resp.status_code == 400
            assert "not allowed" in resp.json()["detail"]

    def test_private_host_allowed_passes(self) -> None:
        app = _build_app(allowed_hosts=["169.254.169.254"])
        with patch("apps.api.middleware.request_host_validator.get_settings") as mock_settings:
            mock_settings.return_value.security.ssrf_allowed_internal_hosts = ["169.254.169.254"]
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.get("/test", headers={"host": "169.254.169.254"})
            assert resp.status_code == 200

    def test_public_ip_not_blocked(self) -> None:
        app = _build_app(allowed_hosts=[])
        with patch("apps.api.middleware.request_host_validator.get_settings") as mock_settings:
            mock_settings.return_value.security.ssrf_allowed_internal_hosts = []
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.get("/test", headers={"host": "1.2.3.4"})
            assert resp.status_code == 200

    def test_127_x_blocked_when_not_allowed(self) -> None:
        app = _build_app(allowed_hosts=[])
        with (
            patch("apps.api.middleware.request_host_validator.get_settings") as mock_settings,
            patch("apps.api.middleware.request_host_validator.emit_security_event"),
            patch("apps.api.middleware.request_host_validator.get_security_auditor"),
        ):
            mock_settings.return_value.security.ssrf_allowed_internal_hosts = []
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.get("/test", headers={"host": "127.0.0.1"})
            assert resp.status_code == 400

    def test_10_x_blocked_when_not_allowed(self) -> None:
        app = _build_app(allowed_hosts=[])
        with (
            patch("apps.api.middleware.request_host_validator.get_settings") as mock_settings,
            patch("apps.api.middleware.request_host_validator.emit_security_event"),
            patch("apps.api.middleware.request_host_validator.get_security_auditor"),
        ):
            mock_settings.return_value.security.ssrf_allowed_internal_hosts = []
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.get("/test", headers={"host": "10.0.0.1"})
            assert resp.status_code == 400
