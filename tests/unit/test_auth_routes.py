"""Tests for auth routes: authorize, callback, login, logout, me."""

from __future__ import annotations

import base64
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.api.routes.auth import _oidc_states, router
from apps.api.security import create_session_token
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


class TestAuthorize:
    def test_returns_authorize_url(self, client, monkeypatch):
        monkeypatch.setenv("SECURITY__OIDC_AUTHORIZATION_URL", "https://idp.example.com/authorize")
        monkeypatch.setenv("SECURITY__OIDC_CLIENT_ID", "test-client")
        monkeypatch.setenv("SECURITY__OIDC_REDIRECT_URI", "http://localhost:3000/callback")
        monkeypatch.setenv("SECURITY__OIDC_SCOPE", "openid profile")
        get_settings.cache_clear()
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


class TestCallback:
    def test_missing_params_returns_400(self, client):
        resp = client.get("/api/v1/auth/callback")
        assert resp.status_code == 400

    def test_invalid_state_returns_400(self, client, monkeypatch):
        monkeypatch.setenv("SECURITY__OIDC_TOKEN_URL", "https://idp.example.com/token")
        monkeypatch.setenv("SECURITY__OIDC_CLIENT_ID", "test-client")
        get_settings.cache_clear()
        try:
            resp = client.get("/api/v1/auth/callback", params={"code": "abc", "state": "nonexistent"})
            assert resp.status_code == 400
            assert "Invalid or expired OIDC state" in resp.json()["detail"]
        finally:
            get_settings.cache_clear()

    def test_valid_callback_exchanges_token(self, client, monkeypatch):
        monkeypatch.setenv("SECURITY__OIDC_TOKEN_URL", "https://idp.example.com/token")
        monkeypatch.setenv("SECURITY__OIDC_CLIENT_ID", "test-client")
        monkeypatch.setenv("SECURITY__OIDC_REDIRECT_URI", "http://localhost:3000/callback")
        monkeypatch.setenv("SECURITY__OIDC_ISSUER", "https://idp.example.com")
        monkeypatch.setenv("SECURITY__SESSION_SECRET_KEY", "test-session-key-123")
        get_settings.cache_clear()

        state = "test-state-123"
        _oidc_states[state] = {"nonce": "test-nonce", "verifier": "test-verifier"}

        header = base64.urlsafe_b64encode(json.dumps({"alg": "RS256", "typ": "JWT"}).encode()).rstrip(b"=").decode()
        payload = (
            base64.urlsafe_b64encode(
                json.dumps(
                    {
                        "sub": "user-123",
                        "nonce": "test-nonce",
                        "name": "Test User",
                        "email": "test@example.com",
                    }
                ).encode()
            )
            .rstrip(b"=")
            .decode()
        )
        id_token = f"{header}.{payload}.fakesig"

        # Use MagicMock for .json() (sync) and is_error (property)
        mock_post_resp = MagicMock()
        mock_post_resp.is_error = False
        mock_post_resp.json.return_value = {"access_token": "at_abc", "id_token": id_token}

        try:
            with patch("apps.api.routes.auth.httpx.AsyncClient") as mock_cls:
                mock_client = AsyncMock()
                mock_client.post = AsyncMock(return_value=mock_post_resp)
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                mock_cls.return_value = mock_client

                resp = client.get("/api/v1/auth/callback", params={"code": "auth-code", "state": state})
                if resp.status_code != 200:
                    raise AssertionError(f"Expected 200, got {resp.status_code}: {resp.text}")
                assert resp.json()["status"] == "authenticated"
        finally:
            _oidc_states.pop(state, None)
            get_settings.cache_clear()


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
