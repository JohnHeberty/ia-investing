"""Tests for auth routes: authorize, callback, login, logout, me, csrf-token.

Covers:
- authorize: URL generation, PKCE, state/nonce uniqueness, return_to sanitization
- callback: state validation, token exchange, nonce verification, error handling
- login: validation, credential exchange, error handling
- logout: cookie clearing, CSRF cleanup
- me: session decoding, user info, missing/invalid session
- csrf-token: generation, validation, session binding
"""

from __future__ import annotations

import base64
import hashlib
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.api.routes.auth import _oidc_states, router
from apps.api.security import (
    create_session_token,
    decode_session_token,
    validate_csrf_token,
)
from ia_investing.settings import get_settings


@pytest.fixture()
def app_instance():
    get_settings.cache_clear()
    application = FastAPI()
    application.include_router(router)
    yield application
    get_settings.cache_clear()


@pytest.fixture()
def client(app_instance):
    with TestClient(app_instance, raise_server_exceptions=True) as c:
        yield c


def _make_id_token(
    sub: str = "user-123",
    nonce: str | None = "test-nonce",
    name: str = "Test User",
    email: str = "test@example.com",
    roles: list[str] | None = None,
    permissions: str | None = None,
    organization_id: str | None = None,
) -> str:
    """Build a minimal self-signed JWT-like token for testing."""
    header = base64.urlsafe_b64encode(json.dumps({"alg": "RS256", "typ": "JWT"}).encode()).rstrip(b"=").decode()
    payload_data: dict[str, object] = {"sub": sub, "name": name, "email": email}
    if nonce is not None:
        payload_data["nonce"] = nonce
    if roles is not None:
        payload_data["roles"] = roles
    if permissions is not None:
        payload_data["permissions"] = permissions
    if organization_id is not None:
        payload_data["organization_id"] = organization_id
    payload = base64.urlsafe_b64encode(json.dumps(payload_data).encode()).rstrip(b"=").decode()
    return f"{header}.{payload}.fakesig"


def _setup_oidc_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SECURITY__OIDC_TOKEN_URL", "https://idp.example.com/token")
    monkeypatch.setenv("SECURITY__OIDC_CLIENT_ID", "test-client")
    monkeypatch.setenv("SECURITY__OIDC_CLIENT_SECRET", "test-secret")
    monkeypatch.setenv("SECURITY__OIDC_REDIRECT_URI", "http://localhost:3000/callback")
    monkeypatch.setenv("SECURITY__OIDC_ISSUER", "https://idp.example.com")
    monkeypatch.setenv("SECURITY__OIDC_SCOPE", "openid profile email")
    monkeypatch.setenv("SECURITY__OIDC_AUTHORIZATION_URL", "https://idp.example.com/authorize")
    monkeypatch.setenv("SECURITY__SESSION_SECRET_KEY", "test-session-key-1234567890123456")
    get_settings.cache_clear()


# ── TestAuthorize ──────────────────────────────────────────────────────


class TestAuthorize:
    def test_returns_authorize_url(self, client, monkeypatch):
        _setup_oidc_env(monkeypatch)
        try:
            resp = client.get("/api/v1/auth/authorize")
            assert resp.status_code == 200
            data = resp.json()
            assert data["authorization_url"] == "https://idp.example.com/authorize"
            assert data["client_id"] == "test-client"
            assert "state" in data
            assert "nonce" in data
            assert "code_challenge" in data
        finally:
            get_settings.cache_clear()

    def test_returns_503_when_not_configured(self, client, monkeypatch):
        monkeypatch.delenv("SECURITY__OIDC_AUTHORIZATION_URL", raising=False)
        monkeypatch.delenv("SECURITY__OIDC_CLIENT_ID", raising=False)
        get_settings.cache_clear()
        try:
            resp = client.get("/api/v1/auth/authorize")
            assert resp.status_code == 503
        finally:
            get_settings.cache_clear()

    def test_state_is_unique_per_request(self, client, monkeypatch):
        _setup_oidc_env(monkeypatch)
        try:
            states = set()
            for _ in range(10):
                resp = client.get("/api/v1/auth/authorize")
                states.add(resp.json()["state"])
            assert len(states) == 10, "Each request should generate a unique state"
        finally:
            get_settings.cache_clear()

    def test_nonce_is_unique_per_request(self, client, monkeypatch):
        _setup_oidc_env(monkeypatch)
        try:
            nonces = set()
            for _ in range(10):
                resp = client.get("/api/v1/auth/authorize")
                nonces.add(resp.json()["nonce"])
            assert len(nonces) == 10, "Each request should generate a unique nonce"
        finally:
            get_settings.cache_clear()

    def test_code_challenge_is_sha256_of_verifier(self, client, monkeypatch):
        _setup_oidc_env(monkeypatch)
        try:
            resp = client.get("/api/v1/auth/authorize")
            state = resp.json()["state"]
            stored = _oidc_states.get(state)
            assert stored is not None, "State should be stored for later callback"
            verifier = stored["verifier"]
            expected = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
            assert resp.json()["code_challenge"] == expected
        finally:
            _oidc_states.pop(state, None)
            get_settings.cache_clear()

    def test_return_to_sanitized_open_redirect(self, client, monkeypatch):
        _setup_oidc_env(monkeypatch)
        try:
            resp = client.get(
                "/api/v1/auth/authorize",
                params={"return_to": "https://evil.com/steal"},
            )
            assert resp.json()["return_to"] == "/"
        finally:
            get_settings.cache_clear()

    def test_return_to_allows_localhost(self, client, monkeypatch):
        _setup_oidc_env(monkeypatch)
        try:
            resp = client.get(
                "/api/v1/auth/authorize",
                params={"return_to": "http://localhost:3000/dashboard"},
            )
            assert resp.json()["return_to"] == "http://localhost:3000/dashboard"
        finally:
            get_settings.cache_clear()

    def test_return_to_allows_127_0_0_1(self, client, monkeypatch):
        _setup_oidc_env(monkeypatch)
        try:
            resp = client.get(
                "/api/v1/auth/authorize",
                params={"return_to": "http://127.0.0.1:8080/app"},
            )
            assert resp.json()["return_to"] == "http://127.0.0.1:8080/app"
        finally:
            get_settings.cache_clear()

    def test_return_to_rejects_non_http(self, client, monkeypatch):
        _setup_oidc_env(monkeypatch)
        try:
            resp = client.get(
                "/api/v1/auth/authorize",
                params={"return_to": "javascript:alert(1)"},
            )
            assert resp.json()["return_to"] == "/"
        finally:
            get_settings.cache_clear()

    def test_scope_includes_openid_profile_email(self, client, monkeypatch):
        _setup_oidc_env(monkeypatch)
        try:
            resp = client.get("/api/v1/auth/authorize")
            assert resp.json()["scope"] == "openid profile email"
        finally:
            get_settings.cache_clear()

    def test_state_stored_in_oidc_states(self, client, monkeypatch):
        _setup_oidc_env(monkeypatch)
        try:
            resp = client.get("/api/v1/auth/authorize")
            state = resp.json()["state"]
            assert state in _oidc_states
            assert "nonce" in _oidc_states[state]
            assert "verifier" in _oidc_states[state]
        finally:
            _oidc_states.pop(state, None)
            get_settings.cache_clear()


# ── TestCallback ───────────────────────────────────────────────────────


class TestCallback:
    def test_missing_params_returns_400(self, client):
        resp = client.get("/api/v1/auth/callback")
        assert resp.status_code == 400

    def test_missing_code_returns_400(self, client):
        resp = client.get("/api/v1/auth/callback", params={"state": "some-state"})
        assert resp.status_code == 400

    def test_missing_state_returns_400(self, client):
        resp = client.get("/api/v1/auth/callback", params={"code": "some-code"})
        assert resp.status_code == 400

    def test_invalid_state_returns_400(self, client, monkeypatch):
        _setup_oidc_env(monkeypatch)
        try:
            resp = client.get(
                "/api/v1/auth/callback",
                params={"code": "abc", "state": "nonexistent"},
            )
            assert resp.status_code == 400
            assert "Invalid or expired OIDC state" in resp.json()["detail"]
        finally:
            get_settings.cache_clear()

    def test_valid_callback_exchanges_token(self, client, monkeypatch):
        _setup_oidc_env(monkeypatch)
        state = "test-state-123"
        _oidc_states[state] = {"nonce": "test-nonce", "verifier": "test-verifier"}
        id_token = _make_id_token(nonce="test-nonce")

        mock_post_resp = MagicMock()
        mock_post_resp.is_error = False
        mock_post_resp.json.return_value = {
            "access_token": "at_abc",
            "id_token": id_token,
        }

        try:
            with patch("apps.api.routes.auth.httpx.AsyncClient") as mock_cls:
                mock_client = AsyncMock()
                mock_client.post = AsyncMock(return_value=mock_post_resp)
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                mock_cls.return_value = mock_client

                resp = client.get(
                    "/api/v1/auth/callback",
                    params={"code": "auth-code", "state": state},
                )
                assert resp.status_code == 200
                assert resp.json()["status"] == "authenticated"
        finally:
            _oidc_states.pop(state, None)
            get_settings.cache_clear()

    def test_callback_returns_401_on_token_exchange_error(self, client, monkeypatch):
        _setup_oidc_env(monkeypatch)
        state = "test-state-error"
        _oidc_states[state] = {"nonce": "test-nonce", "verifier": "test-verifier"}

        mock_post_resp = MagicMock()
        mock_post_resp.is_error = True
        mock_post_resp.status_code = 502

        try:
            with patch("apps.api.routes.auth.httpx.AsyncClient") as mock_cls:
                mock_client = AsyncMock()
                mock_client.post = AsyncMock(return_value=mock_post_resp)
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                mock_cls.return_value = mock_client

                resp = client.get(
                    "/api/v1/auth/callback",
                    params={"code": "bad-code", "state": state},
                )
                assert resp.status_code == 401
        finally:
            _oidc_states.pop(state, None)
            get_settings.cache_clear()

    def test_callback_returns_401_on_missing_access_token(self, client, monkeypatch):
        _setup_oidc_env(monkeypatch)
        state = "test-state-no-at"
        _oidc_states[state] = {"nonce": "test-nonce", "verifier": "test-verifier"}

        mock_post_resp = MagicMock()
        mock_post_resp.is_error = False
        mock_post_resp.json.return_value = {"id_token": _make_id_token()}

        try:
            with patch("apps.api.routes.auth.httpx.AsyncClient") as mock_cls:
                mock_client = AsyncMock()
                mock_client.post = AsyncMock(return_value=mock_post_resp)
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                mock_cls.return_value = mock_client

                resp = client.get(
                    "/api/v1/auth/callback",
                    params={"code": "code-no-at", "state": state},
                )
                assert resp.status_code == 401
        finally:
            _oidc_states.pop(state, None)
            get_settings.cache_clear()

    def test_callback_returns_401_on_nonce_mismatch(self, client, monkeypatch):
        _setup_oidc_env(monkeypatch)
        monkeypatch.setenv("SECURITY__OIDC_JWKS_URL", "https://idp.example.com/jwks")
        get_settings.cache_clear()
        state = "test-state-nonce-mismatch"
        _oidc_states[state] = {"nonce": "expected-nonce", "verifier": "test-verifier"}

        mock_post_resp = MagicMock()
        mock_post_resp.is_error = False
        mock_post_resp.json.return_value = {
            "access_token": "at_abc",
            "id_token": "some.jwt.token",
        }

        try:
            with (
                patch("apps.api.routes.auth.httpx.AsyncClient") as mock_cls,
                patch(
                    "apps.api.routes.auth._verify_jwt",
                    new_callable=AsyncMock,
                    return_value={"nonce": "wrong-nonce", "sub": "user-mismatch"},
                ),
            ):
                mock_client = AsyncMock()
                mock_client.post = AsyncMock(return_value=mock_post_resp)
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                mock_cls.return_value = mock_client

                resp = client.get(
                    "/api/v1/auth/callback",
                    params={"code": "auth-code", "state": state},
                )
                assert resp.status_code == 401
        finally:
            _oidc_states.pop(state, None)
            get_settings.cache_clear()

    def test_callback_returns_401_on_missing_id_token(self, client, monkeypatch):
        _setup_oidc_env(monkeypatch)
        state = "test-state-no-id"
        _oidc_states[state] = {"nonce": "test-nonce", "verifier": "test-verifier"}

        mock_post_resp = MagicMock()
        mock_post_resp.is_error = False
        mock_post_resp.json.return_value = {"access_token": "at_abc"}

        try:
            with patch("apps.api.routes.auth.httpx.AsyncClient") as mock_cls:
                mock_client = AsyncMock()
                mock_client.post = AsyncMock(return_value=mock_post_resp)
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                mock_cls.return_value = mock_client

                resp = client.get(
                    "/api/v1/auth/callback",
                    params={"code": "code-no-id", "state": state},
                )
                assert resp.status_code == 401
        finally:
            _oidc_states.pop(state, None)
            get_settings.cache_clear()

    def test_callback_returns_400_when_token_url_missing(self, client, monkeypatch):
        monkeypatch.setenv("SECURITY__OIDC_CLIENT_ID", "test-client")
        monkeypatch.delenv("SECURITY__OIDC_TOKEN_URL", raising=False)
        get_settings.cache_clear()
        try:
            resp = client.get(
                "/api/v1/auth/callback",
                params={"code": "abc", "state": "some-state"},
            )
            assert resp.status_code == 400
        finally:
            get_settings.cache_clear()

    def test_state_consumed_after_use(self, client, monkeypatch):
        _setup_oidc_env(monkeypatch)
        state = "test-state-consume"
        _oidc_states[state] = {"nonce": "test-nonce", "verifier": "test-verifier"}
        id_token = _make_id_token(nonce="test-nonce")

        mock_post_resp = MagicMock()
        mock_post_resp.is_error = False
        mock_post_resp.json.return_value = {
            "access_token": "at_abc",
            "id_token": id_token,
        }

        try:
            with patch("apps.api.routes.auth.httpx.AsyncClient") as mock_cls:
                mock_client = AsyncMock()
                mock_client.post = AsyncMock(return_value=mock_post_resp)
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                mock_cls.return_value = mock_client

                resp1 = client.get(
                    "/api/v1/auth/callback",
                    params={"code": "code1", "state": state},
                )
                assert resp1.status_code == 200

                resp2 = client.get(
                    "/api/v1/auth/callback",
                    params={"code": "code2", "state": state},
                )
                assert resp2.status_code == 400
        finally:
            _oidc_states.pop(state, None)
            get_settings.cache_clear()


# ── TestLogin ──────────────────────────────────────────────────────────


class TestLogin:
    def test_missing_body_returns_422(self, client):
        resp = client.post("/api/v1/auth/login")
        assert resp.status_code == 422

    def test_missing_email_returns_422(self, client):
        resp = client.post("/api/v1/auth/login", json={"password": "pass"})
        assert resp.status_code == 422

    def test_missing_password_returns_422(self, client):
        resp = client.post("/api/v1/auth/login", json={"email": "a@b.com"})
        assert resp.status_code == 422

    def test_empty_email_returns_422(self, client):
        resp = client.post(
            "/api/v1/auth/login",
            json={"email": "", "password": "pass"},
        )
        assert resp.status_code == 422

    def test_empty_password_returns_422(self, client):
        resp = client.post(
            "/api/v1/auth/login",
            json={"email": "a@b.com", "password": ""},
        )
        assert resp.status_code == 422

    def test_returns_503_when_oidc_not_configured(self, client, monkeypatch):
        monkeypatch.delenv("SECURITY__OIDC_TOKEN_URL", raising=False)
        monkeypatch.delenv("SECURITY__OIDC_CLIENT_ID", raising=False)
        get_settings.cache_clear()
        try:
            resp = client.post(
                "/api/v1/auth/login",
                json={"email": "a@b.com", "password": "pass"},
            )
            assert resp.status_code == 503
            assert "not available" in resp.json()["detail"]
        finally:
            get_settings.cache_clear()

    def test_invalid_credentials_returns_401(self, client, monkeypatch):
        _setup_oidc_env(monkeypatch)
        mock_post_resp = MagicMock()
        mock_post_resp.is_error = True
        mock_post_resp.status_code = 401
        try:
            with patch("apps.api.routes.auth.httpx.AsyncClient") as mock_cls:
                mock_client = AsyncMock()
                mock_client.post = AsyncMock(return_value=mock_post_resp)
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                mock_cls.return_value = mock_client

                resp = client.post(
                    "/api/v1/auth/login",
                    json={"email": "bad@creds.com", "password": "wrong"},
                )
                assert resp.status_code == 401
        finally:
            get_settings.cache_clear()

    def test_valid_login_returns_200(self, client, monkeypatch):
        _setup_oidc_env(monkeypatch)
        id_token = _make_id_token(sub="login-user")

        mock_post_resp = MagicMock()
        mock_post_resp.is_error = False
        mock_post_resp.json.return_value = {
            "access_token": "at_login",
            "id_token": id_token,
        }

        try:
            with patch("apps.api.routes.auth.httpx.AsyncClient") as mock_cls:
                mock_client = AsyncMock()
                mock_client.post = AsyncMock(return_value=mock_post_resp)
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                mock_cls.return_value = mock_client

                resp = client.post(
                    "/api/v1/auth/login",
                    json={"email": "good@creds.com", "password": "correct"},
                )
                assert resp.status_code == 200
                data = resp.json()
                assert data["status"] == "ok"
                assert data["subject"] == "login-user"
        finally:
            get_settings.cache_clear()

    def test_login_sets_session_cookie(self, client, monkeypatch):
        _setup_oidc_env(monkeypatch)
        id_token = _make_id_token(sub="cookie-user")

        mock_post_resp = MagicMock()
        mock_post_resp.is_error = False
        mock_post_resp.json.return_value = {
            "access_token": "at_cookie",
            "id_token": id_token,
        }

        try:
            with patch("apps.api.routes.auth.httpx.AsyncClient") as mock_cls:
                mock_client = AsyncMock()
                mock_client.post = AsyncMock(return_value=mock_post_resp)
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                mock_cls.return_value = mock_client

                resp = client.post(
                    "/api/v1/auth/login",
                    json={"email": "cookie@test.com", "password": "pass"},
                )
                assert resp.status_code == 200
                cookies = {c.name: c.value for c in resp.cookies.jar}
                assert "ia_session" in cookies
                assert "ia_csrf_token" in cookies
        finally:
            get_settings.cache_clear()


# ── TestLogout ─────────────────────────────────────────────────────────


class TestLogout:
    def test_clears_cookies(self, client, monkeypatch):
        monkeypatch.setenv("APPLICATION__ENVIRONMENT", "development")
        get_settings.cache_clear()
        try:
            resp = client.post("/api/v1/auth/logout")
            assert resp.status_code == 200
            assert resp.json()["status"] == "ok"
        finally:
            get_settings.cache_clear()

    def test_logout_deletes_session_cookie(self, client, monkeypatch):
        monkeypatch.setenv("APPLICATION__ENVIRONMENT", "development")
        monkeypatch.setenv("SECURITY__SESSION_SECRET_KEY", "test-key")
        get_settings.cache_clear()
        try:
            token = create_session_token(subject="user-logout")
            client.cookies.set("ia_session", token)
            resp = client.post("/api/v1/auth/logout")
            assert resp.status_code == 200
            assert resp.cookies.get("ia_session") is None
        finally:
            get_settings.cache_clear()

    def test_logout_deletes_csrf_cookie(self, client, monkeypatch):
        monkeypatch.setenv("APPLICATION__ENVIRONMENT", "development")
        monkeypatch.setenv("SECURITY__SESSION_SECRET_KEY", "test-key")
        get_settings.cache_clear()
        try:
            client.cookies.set("ia_csrf_token", "some-csrf-token")
            resp = client.post("/api/v1/auth/logout")
            assert resp.status_code == 200
            assert resp.cookies.get("ia_csrf_token") is None
        finally:
            get_settings.cache_clear()

    def test_logout_without_session_succeeds(self, client):
        resp = client.post("/api/v1/auth/logout")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


# ── TestMe ─────────────────────────────────────────────────────────────


class TestMe:
    def test_returns_401_without_session(self, client):
        resp = client.get("/api/v1/auth/me")
        assert resp.status_code == 401

    def test_returns_user_info_with_valid_session(self, client, monkeypatch):
        monkeypatch.setenv("SECURITY__SESSION_SECRET_KEY", "test-secret-key-for-sessions")
        get_settings.cache_clear()
        try:
            token = create_session_token(
                subject="user-abc",
                organization_id=None,
                roles=frozenset({"analyst"}),
                permissions=frozenset({"portfolio:read"}),
                name="Test User",
                email="test@example.com",
            )
            client.cookies.set("ia_session", token)
            resp = client.get("/api/v1/auth/me")
            assert resp.status_code == 200
            data = resp.json()
            assert data["subject"] == "user-abc"
            assert data["name"] == "Test User"
            assert data["email"] == "test@example.com"
            assert "analyst" in data["roles"]
            assert "portfolio:read" in data["permissions"]
        finally:
            get_settings.cache_clear()

    def test_returns_401_with_invalid_token(self, client, monkeypatch):
        monkeypatch.setenv("SECURITY__SESSION_SECRET_KEY", "test-secret-key")
        get_settings.cache_clear()
        try:
            client.cookies.set("ia_session", "invalid.token.here")
            resp = client.get("/api/v1/auth/me")
            assert resp.status_code == 401
        finally:
            get_settings.cache_clear()

    def test_returns_401_with_tampered_token(self, client, monkeypatch):
        monkeypatch.setenv("SECURITY__SESSION_SECRET_KEY", "test-secret-key")
        get_settings.cache_clear()
        try:
            token = create_session_token(
                subject="user-tamper",
                name="Tamper User",
            )
            tampered = token[:-5] + "XXXXX"
            client.cookies.set("ia_session", tampered)
            resp = client.get("/api/v1/auth/me")
            assert resp.status_code == 401
        finally:
            get_settings.cache_clear()

    def test_includes_organization_id(self, client, monkeypatch):
        from uuid import UUID

        monkeypatch.setenv("SECURITY__SESSION_SECRET_KEY", "test-secret-key")
        get_settings.cache_clear()
        try:
            org_id = UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
            token = create_session_token(
                subject="user-org",
                organization_id=org_id,
            )
            client.cookies.set("ia_session", token)
            resp = client.get("/api/v1/auth/me")
            assert resp.status_code == 200
            data = resp.json()
            assert data["organization_id"] == str(org_id)
        finally:
            get_settings.cache_clear()

    def test_includes_team_ids(self, client, monkeypatch):
        from uuid import UUID

        monkeypatch.setenv("SECURITY__SESSION_SECRET_KEY", "test-secret-key")
        get_settings.cache_clear()
        try:
            team_id = UUID("11111111-2222-3333-4444-555555555555")
            token = create_session_token(
                subject="user-teams",
                team_ids=frozenset({team_id}),
            )
            client.cookies.set("ia_session", token)
            resp = client.get("/api/v1/auth/me")
            assert resp.status_code == 200
            data = resp.json()
            assert str(team_id) in data["team_ids"]
        finally:
            get_settings.cache_clear()

    def test_empty_session_returns_401(self, client, monkeypatch):
        monkeypatch.setenv("SECURITY__SESSION_SECRET_KEY", "test-secret-key")
        get_settings.cache_clear()
        try:
            from datetime import UTC, datetime, timedelta

            import jwt as pyjwt

            payload = {
                "sub": "",
                "iat": datetime.now(UTC),
                "exp": datetime.now(UTC) + timedelta(hours=1),
            }
            token = pyjwt.encode(payload, "test-secret-key", algorithm="HS256")
            client.cookies.set("ia_session", token)
            resp = client.get("/api/v1/auth/me")
            assert resp.status_code == 401
        finally:
            get_settings.cache_clear()

    def test_returns_roles_list(self, client, monkeypatch):
        monkeypatch.setenv("SECURITY__SESSION_SECRET_KEY", "test-secret-key")
        get_settings.cache_clear()
        try:
            token = create_session_token(
                subject="user-roles",
                roles=frozenset({"admin", "analyst"}),
            )
            client.cookies.set("ia_session", token)
            resp = client.get("/api/v1/auth/me")
            assert resp.status_code == 200
            data = resp.json()
            assert "admin" in data["roles"]
            assert "analyst" in data["roles"]
        finally:
            get_settings.cache_clear()

    def test_returns_permissions_list(self, client, monkeypatch):
        monkeypatch.setenv("SECURITY__SESSION_SECRET_KEY", "test-secret-key")
        get_settings.cache_clear()
        try:
            token = create_session_token(
                subject="user-perms",
                permissions=frozenset({"portfolio:read", "research:write"}),
            )
            client.cookies.set("ia_session", token)
            resp = client.get("/api/v1/auth/me")
            assert resp.status_code == 200
            data = resp.json()
            assert "portfolio:read" in data["permissions"]
            assert "research:write" in data["permissions"]
        finally:
            get_settings.cache_clear()


# ── TestCsrfToken ──────────────────────────────────────────────────────


class TestCsrfToken:
    def test_returns_401_without_session(self, client):
        resp = client.get("/api/v1/auth/csrf-token")
        assert resp.status_code == 401

    def test_returns_csrf_token_with_valid_session(self, client, monkeypatch):
        monkeypatch.setenv("SECURITY__SESSION_SECRET_KEY", "test-secret-key")
        get_settings.cache_clear()
        try:
            token = create_session_token(subject="user-csrf")
            client.cookies.set("ia_session", token)
            resp = client.get("/api/v1/auth/csrf-token")
            assert resp.status_code == 200
            data = resp.json()
            assert "csrf_token" in data
            assert len(data["csrf_token"]) > 10
        finally:
            get_settings.cache_clear()

    def test_csrf_token_validates_correctly(self, client, monkeypatch):
        monkeypatch.setenv("SECURITY__SESSION_SECRET_KEY", "test-secret-key")
        get_settings.cache_clear()
        try:
            token = create_session_token(subject="user-csrf-validate")
            client.cookies.set("ia_session", token)
            resp = client.get("/api/v1/auth/csrf-token")
            csrf_token = resp.json()["csrf_token"]
            session = decode_session_token(token)
            session_id = str(session.get("sid", ""))
            assert validate_csrf_token(csrf_token, session_id) is True
        finally:
            get_settings.cache_clear()

    def test_csrf_token_unique_per_session(self, client, monkeypatch):
        monkeypatch.setenv("SECURITY__SESSION_SECRET_KEY", "test-secret-key")
        get_settings.cache_clear()
        try:
            tokens = set()
            for _ in range(5):
                token = create_session_token(subject="user-csrf-unique")
                client.cookies.set("ia_session", token)
                resp = client.get("/api/v1/auth/csrf-token")
                tokens.add(resp.json()["csrf_token"])
            assert len(tokens) == 5
        finally:
            get_settings.cache_clear()

    def test_csrf_token_rejects_wrong_session(self, client, monkeypatch):
        monkeypatch.setenv("SECURITY__SESSION_SECRET_KEY", "test-secret-key")
        get_settings.cache_clear()
        try:
            token = create_session_token(subject="user-csrf-wrong")
            client.cookies.set("ia_session", token)
            resp = client.get("/api/v1/auth/csrf-token")
            csrf_token = resp.json()["csrf_token"]
            assert validate_csrf_token(csrf_token, "wrong-session-id") is False
        finally:
            get_settings.cache_clear()

    def test_csrf_token_sets_cookie(self, client, monkeypatch):
        monkeypatch.setenv("SECURITY__SESSION_SECRET_KEY", "test-secret-key")
        get_settings.cache_clear()
        try:
            token = create_session_token(subject="user-csrf-cookie")
            client.cookies.set("ia_session", token)
            resp = client.get("/api/v1/auth/csrf-token")
            assert resp.status_code == 200
            cookies = {c.name: c.value for c in resp.cookies.jar}
            assert "ia_csrf_token" in cookies
        finally:
            get_settings.cache_clear()


# ── TestSafeReturnTo ───────────────────────────────────────────────────


class TestSafeReturnTo:
    def test_none_defaults_to_slash(self, client, monkeypatch):
        _setup_oidc_env(monkeypatch)
        try:
            resp = client.get("/api/v1/auth/authorize")
            assert resp.json()["return_to"] == "/"
        finally:
            get_settings.cache_clear()

    def test_empty_string_defaults_to_slash(self, client, monkeypatch):
        _setup_oidc_env(monkeypatch)
        try:
            resp = client.get(
                "/api/v1/auth/authorize",
                params={"return_to": ""},
            )
            assert resp.json()["return_to"] == "/"
        finally:
            get_settings.cache_clear()

    def test_rejects_javascript_uri(self, client, monkeypatch):
        _setup_oidc_env(monkeypatch)
        try:
            resp = client.get(
                "/api/v1/auth/authorize",
                params={"return_to": "javascript:alert(1)"},
            )
            assert resp.json()["return_to"] == "/"
        finally:
            get_settings.cache_clear()

    def test_rejects_data_uri(self, client, monkeypatch):
        _setup_oidc_env(monkeypatch)
        try:
            resp = client.get(
                "/api/v1/auth/authorize",
                params={"return_to": "data:text/html,<script>alert(1)</script>"},
            )
            assert resp.json()["return_to"] == "/"
        finally:
            get_settings.cache_clear()

    def test_rejects_filed_uri(self, client, monkeypatch):
        _setup_oidc_env(monkeypatch)
        try:
            resp = client.get(
                "/api/v1/auth/authorize",
                params={"return_to": "file:///etc/passwd"},
            )
            assert resp.json()["return_to"] == "/"
        finally:
            get_settings.cache_clear()
