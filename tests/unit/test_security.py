from __future__ import annotations

from unittest.mock import patch
from uuid import UUID, uuid4

import jwt
import pytest
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from apps.api.main import app
from apps.api.security import AuthContext, get_auth_context, require_permission
from ia_investing.application.security import (
    ActorContext,
    PolicyEngine,
    ResourceAttributes,
    enforce,
)
from ia_investing.settings import get_settings

_bearer_scheme = HTTPBearer(auto_error=False)


async def _mock_get_auth_context(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> AuthContext:
    if credentials is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    return AuthContext(
        subject="test-user",
        permissions=frozenset(),
        authentication_method="test",
        organization_id=UUID("00000000-0000-0000-0000-000000000000"),
    )


@pytest.fixture
def client():
    app.dependency_overrides[get_auth_context] = _mock_get_auth_context
    from fastapi.testclient import TestClient

    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides.clear()


def _auth_header(token: str = "test-token") -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# ── Existing tests (must remain passing) ───────────────────────────────


@pytest.mark.asyncio
async def test_development_identity_is_explicit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APPLICATION__ENVIRONMENT", "development")
    get_settings.cache_clear()
    try:
        context = await get_auth_context(
            credentials=None,
            dev_subject="developer@example.com",
            dev_permissions="agent_runs:create operations:read",
            dev_organization=None,
            dev_teams="",
        )
    finally:
        get_settings.cache_clear()

    assert context.subject == "developer@example.com"
    assert context.authentication_method == "development-header"


@pytest.mark.asyncio
async def test_permission_dependency_denies_missing_permission() -> None:
    dependency = require_permission("agent_runs:create")
    context = AuthContext("subject", frozenset(), "test")

    with pytest.raises(HTTPException) as exc_info:
        await dependency(context)

    assert exc_info.value.status_code == 403


def test_authenticated_user_without_permission_gets_403(client):
    response = client.get(
        "/api/v1/research/cases",
        headers=_auth_header(),
    )
    assert response.status_code == 403, "Empty permissions should deny access"


def test_unauthenticated_request_returns_401(client):
    response = client.get("/api/v1/research/cases")
    assert response.status_code in (401, 403)


# ── New OIDC tests ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_expired_token_returns_401(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SECURITY__OIDC_ENABLED", "true")
    monkeypatch.setenv("SECURITY__OIDC_ISSUER", "https://issuer.example.com")
    monkeypatch.setenv("SECURITY__OIDC_AUDIENCE", "test-audience")
    monkeypatch.setenv("SECURITY__OIDC_JWKS_URL", "https://issuer.example.com/jwks")
    get_settings.cache_clear()
    try:
        with (
            patch("apps.api.security._decode_oidc_token", side_effect=jwt.ExpiredSignatureError("expired")),
            pytest.raises(HTTPException) as exc_info,
        ):
            await get_auth_context(
                credentials=HTTPAuthorizationCredentials(
                    scheme="Bearer",
                    credentials="eyJhbGciOiJSUzI1NiJ9.eyJzdWIiOiJ0ZXN0In0.expired",
                ),
            )
        assert exc_info.value.status_code == 401
        assert "Invalid bearer token" in exc_info.value.detail
    finally:
        get_settings.cache_clear()


@pytest.mark.asyncio
async def test_invalid_signature_returns_401(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SECURITY__OIDC_ENABLED", "true")
    monkeypatch.setenv("SECURITY__OIDC_ISSUER", "https://issuer.example.com")
    monkeypatch.setenv("SECURITY__OIDC_AUDIENCE", "test-audience")
    monkeypatch.setenv("SECURITY__OIDC_JWKS_URL", "https://issuer.example.com/jwks")
    get_settings.cache_clear()
    try:
        with (
            patch("apps.api.security._decode_oidc_token", side_effect=jwt.InvalidSignatureError("bad signature")),
            pytest.raises(HTTPException) as exc_info,
        ):
            await get_auth_context(
                credentials=HTTPAuthorizationCredentials(
                    scheme="Bearer",
                    credentials="eyJhbGciOiJSUzI1NiJ9.eyJzdWIiOiJ0ZXN0In0.badsignature",
                ),
            )
        assert exc_info.value.status_code == 401
        assert "Invalid bearer token" in exc_info.value.detail
    finally:
        get_settings.cache_clear()


@pytest.mark.asyncio
async def test_missing_permission_returns_403() -> None:
    dependency = require_permission("portfolio:write")
    context = AuthContext(
        subject="analyst@example.com",
        permissions=frozenset({"research:read"}),
        authentication_method="oidc",
        organization_id=UUID("00000000-0000-0000-0000-000000000001"),
    )

    with pytest.raises(HTTPException) as exc_info:
        await dependency(context)

    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_valid_token_returns_actor_context(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SECURITY__OIDC_ENABLED", "true")
    monkeypatch.setenv("SECURITY__OIDC_ISSUER", "https://issuer.example.com")
    monkeypatch.setenv("SECURITY__OIDC_AUDIENCE", "test-audience")
    monkeypatch.setenv("SECURITY__OIDC_JWKS_URL", "https://issuer.example.com/jwks")
    get_settings.cache_clear()
    org_id = uuid4()
    try:
        with patch(
            "apps.api.security._decode_oidc_token",
            return_value={
                "sub": "user-abc-123",
                "permissions": "research:read portfolio:read",
                "organization_id": str(org_id),
                "iss": "https://issuer.example.com",
                "aud": "test-audience",
            },
        ):
            context = await get_auth_context(
                credentials=HTTPAuthorizationCredentials(
                    scheme="Bearer",
                    credentials="valid.jwt.token",
                ),
            )
        assert context.subject == "user-abc-123"
        assert context.authentication_method == "oidc"
        assert "research:read" in context.permissions
        assert "portfolio:read" in context.permissions
        assert context.organization_id == org_id

        actor = context.to_actor_context()
        assert isinstance(actor, ActorContext)
        assert actor.subject == "user-abc-123"
    finally:
        get_settings.cache_clear()


# ── ABAC / PolicyEngine tests ──────────────────────────────────────────


class TestPolicyEngine:
    def test_abac_policy_evaluates_correctly(self) -> None:
        engine = PolicyEngine()
        org_id = uuid4()
        actor = ActorContext(
            subject="analyst@example.com",
            organization_id=org_id,
            permissions=frozenset({"portfolio:read", "portfolio:write"}),
        )

        assert engine.enforce("portfolio", "read", actor)
        assert engine.enforce("portfolio", "write", actor)
        assert not engine.enforce("portfolio", "delete", actor)
        assert not engine.enforce("research", "read", actor)

    def test_abac_org_isolation(self) -> None:
        engine = PolicyEngine()
        actor = ActorContext(
            subject="analyst@example.com",
            organization_id=uuid4(),
            permissions=frozenset({"portfolio:read"}),
        )
        resource = ResourceAttributes(
            resource_type="portfolio",
            organization_id=uuid4(),
        )

        assert not engine.enforce("portfolio", "read", actor, resource)

    def test_abac_team_isolation(self) -> None:
        engine = PolicyEngine()
        team_id = uuid4()
        actor = ActorContext(
            subject="analyst@example.com",
            organization_id=uuid4(),
            team_ids=frozenset({team_id}),
            permissions=frozenset({"portfolio:write"}),
        )
        other_team_resource = ResourceAttributes(
            resource_type="portfolio",
            organization_id=actor.organization_id,
            owner_team_id=uuid4(),
        )
        own_team_resource = ResourceAttributes(
            resource_type="portfolio",
            organization_id=actor.organization_id,
            owner_team_id=team_id,
        )

        assert not engine.enforce("portfolio", "write", actor, other_team_resource)
        assert engine.enforce("portfolio", "write", actor, own_team_resource)

    def test_abac_admin_override(self) -> None:
        engine = PolicyEngine()
        actor = ActorContext(
            subject="admin@example.com",
            organization_id=None,
            roles=frozenset({"admin"}),
            permissions=frozenset(),
        )

        assert engine.enforce("any_resource", "any_action", actor)

    def test_abac_owner_access(self) -> None:
        engine = PolicyEngine()
        actor = ActorContext(
            subject="owner@example.com",
            organization_id=uuid4(),
            permissions=frozenset({"document:read"}),
        )
        own_resource = ResourceAttributes(
            resource_type="document",
            organization_id=actor.organization_id,
            owner_subject="owner@example.com",
        )
        other_resource = ResourceAttributes(
            resource_type="document",
            organization_id=actor.organization_id,
            owner_subject="someone-else@example.com",
        )

        assert engine.enforce("document", "read", actor, own_resource)
        assert not engine.enforce("document", "read", actor, other_resource)


# ── Development mode with OIDC disabled ────────────────────────────────


@pytest.mark.asyncio
async def test_development_mode_with_oidc_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APPLICATION__ENVIRONMENT", "development")
    monkeypatch.setenv("SECURITY__OIDC_ENABLED", "false")
    get_settings.cache_clear()
    try:
        context = await get_auth_context(
            credentials=HTTPAuthorizationCredentials(
                scheme="Bearer",
                credentials="eyJhbGciOiJub25lIn0.eyJzdWIiOiJhbnkuZGV2LnRva2VuLndvcmtzIn0.",
            ),
        )
        assert context.subject == "any.dev.token.works"
        assert context.authentication_method == "oidc"
    finally:
        get_settings.cache_clear()


@pytest.mark.asyncio
async def test_enforce_function_smoke() -> None:
    org_id = uuid4()
    actor = ActorContext(
        subject="test@example.com",
        organization_id=org_id,
        permissions=frozenset({"portfolio:read"}),
    )
    resource = ResourceAttributes(
        resource_type="portfolio",
        organization_id=org_id,
    )

    assert enforce("portfolio", "read", actor)
    assert not enforce("portfolio", "write", actor)
    assert enforce("portfolio", "read", actor, resource)
    assert not enforce("portfolio", "write", actor, resource)
