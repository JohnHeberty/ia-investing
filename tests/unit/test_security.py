from __future__ import annotations

from unittest.mock import patch
from uuid import UUID, uuid4

import jwt
import pytest
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from apps.api.main import app
from apps.api.security import (
    AuthContext,
    create_session_token,
    decode_session_token,
    generate_csrf_token,
    get_auth_context,
    require_permission,
    validate_csrf_token,
)
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
    monkeypatch.setenv("SECURITY__DEV_JWT_SKIP_VERIFY", "true")
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


# ── Session token roundtrip ────────────────────────────────────────────


def test_session_token_roundtrip(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SECURITY__SESSION_SECRET_KEY", "test-session-key-123")
    get_settings.cache_clear()
    try:
        token = create_session_token(
            subject="user-round",
            organization_id=UUID("11111111-1111-1111-1111-111111111111"),
            roles=frozenset({"admin"}),
            team_ids=frozenset({UUID("22222222-2222-2222-2222-222222222222")}),
            permissions=frozenset({"portfolio:read", "portfolio:write"}),
            name="Round User",
            email="round@test.com",
        )
        claims = decode_session_token(token)
        assert claims is not None
        assert claims["sub"] == "user-round"
        assert "portfolio:read" in claims["permissions"]
        assert "portfolio:write" in claims["permissions"]
        assert "admin" in claims["roles"]
    finally:
        get_settings.cache_clear()


def test_decode_invalid_token_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SECURITY__SESSION_SECRET_KEY", "test-session-key-123")
    get_settings.cache_clear()
    try:
        assert decode_session_token("not-a-valid-token") is None
    finally:
        get_settings.cache_clear()


# ── CSRF token roundtrip ──────────────────────────────────────────────


def test_csrf_token_roundtrip(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SECURITY__SESSION_SECRET_KEY", "test-session-key-123")
    get_settings.cache_clear()
    try:
        token = generate_csrf_token("sid-abc-123")
        assert validate_csrf_token(token, "sid-abc-123") is True
    finally:
        get_settings.cache_clear()


def test_csrf_token_wrong_session_id_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SECURITY__SESSION_SECRET_KEY", "test-session-key-123")
    get_settings.cache_clear()
    try:
        token = generate_csrf_token("sid-abc-123")
        assert validate_csrf_token(token, "sid-wrong") is False
    finally:
        get_settings.cache_clear()


def test_csrf_token_tampered_digest_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SECURITY__SESSION_SECRET_KEY", "test-session-key-123")
    get_settings.cache_clear()
    try:
        tampered = "sid-abc-123:0000000000000000000000000000000000000000000000000000000000000000"
        assert validate_csrf_token(tampered, "sid-abc-123") is False
    finally:
        get_settings.cache_clear()


def test_csrf_token_malformed_returns_false() -> None:
    assert validate_csrf_token("no-colon-here", "anything") is False
    assert validate_csrf_token("", "anything") is False


# ── Parse helpers ──────────────────────────────────────────────────────


def test_parse_permissions_string_space_separated() -> None:
    from apps.api.security import _parse_permissions

    result = _parse_permissions({"permissions": "read write execute"})
    assert result == frozenset({"read", "write", "execute"})


def test_parse_permissions_string_comma_separated() -> None:
    from apps.api.security import _parse_permissions

    result = _parse_permissions({"permissions": "read,write,execute"})
    assert result == frozenset({"read", "write", "execute"})


def test_parse_permissions_list() -> None:
    from apps.api.security import _parse_permissions

    result = _parse_permissions({"permissions": ["read", "write"]})
    assert result == frozenset({"read", "write"})


def test_parse_permissions_scope_fallback() -> None:
    from apps.api.security import _parse_permissions

    result = _parse_permissions({"scope": "openid profile"})
    assert result == frozenset({"openid", "profile"})


def test_parse_permissions_empty() -> None:
    from apps.api.security import _parse_permissions

    assert _parse_permissions({}) == frozenset()
    assert _parse_permissions({"permissions": 123}) == frozenset()


def test_parse_roles_string() -> None:
    from apps.api.security import _parse_roles

    result = _parse_roles({"roles": "admin analyst"})
    assert result == frozenset({"admin", "analyst"})


def test_parse_roles_list() -> None:
    from apps.api.security import _parse_roles

    result = _parse_roles({"roles": ["admin", "analyst"]})
    assert result == frozenset({"admin", "analyst"})


def test_parse_roles_empty() -> None:
    from apps.api.security import _parse_roles

    assert _parse_roles({}) == frozenset()
    assert _parse_roles({"roles": []}) == frozenset()


# ── Dev header with organization ──────────────────────────────────────


@pytest.mark.asyncio
async def test_development_headers_with_org_and_teams(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APPLICATION__ENVIRONMENT", "development")
    get_settings.cache_clear()
    try:
        team_id = uuid4()
        org_id = uuid4()
        context = await get_auth_context(
            credentials=None,
            dev_subject="dev@test.com",
            dev_permissions="agent_runs:create",
            dev_organization=org_id,
            dev_teams=str(team_id),
        )
        assert context.subject == "dev@test.com"
        assert context.organization_id == org_id
        assert team_id in context.team_ids
    finally:
        get_settings.cache_clear()


@pytest.mark.asyncio
async def test_production_with_no_oidc_returns_503(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APPLICATION__ENVIRONMENT", "production")
    monkeypatch.setenv("SECURITY__OIDC_ENABLED", "false")
    monkeypatch.setenv("SECURITY__OIDC_ISSUER", "https://idp.prod.com")
    monkeypatch.setenv("SECURITY__OIDC_AUDIENCE", "prod-aud")
    monkeypatch.setenv("SECURITY__OIDC_JWKS_URL", "https://idp.prod.com/jwks")
    monkeypatch.setenv("STORAGE__ACCESS_KEY", "prod-key")
    monkeypatch.setenv("STORAGE__SECRET_KEY", "prod-secret")
    monkeypatch.setenv("DATABASE__URL", "postgresql+asyncpg://u:p@db.prod.com/prod")
    monkeypatch.setenv("AI__PROVIDER", "gateway")
    monkeypatch.setenv("AI__GATEWAY__BASE_URL", "http://litellm:4000/v1")
    monkeypatch.setenv("AI__GATEWAY__API_KEY", "sk-prod-gateway-key-12345")
    get_settings.cache_clear()
    try:
        with pytest.raises(HTTPException) as exc_info:
            await get_auth_context(
                credentials=HTTPAuthorizationCredentials(scheme="Bearer", credentials="some.token"),
            )
        assert exc_info.value.status_code == 503
    finally:
        get_settings.cache_clear()


@pytest.mark.asyncio
async def test_no_credentials_no_dev_header_returns_401() -> None:
    with pytest.raises(HTTPException) as exc_info:
        await get_auth_context(
            credentials=None,
            dev_subject=None,
        )
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_token_without_subject_returns_401(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APPLICATION__ENVIRONMENT", "development")
    monkeypatch.setenv("SECURITY__OIDC_ENABLED", "false")
    monkeypatch.setenv("SECURITY__DEV_JWT_SKIP_VERIFY", "true")
    get_settings.cache_clear()
    try:
        with pytest.raises(HTTPException) as exc_info:
            await get_auth_context(
                credentials=HTTPAuthorizationCredentials(
                    scheme="Bearer",
                    credentials="eyJhbGciOiJub25lIn0.eyJpc3MiOiJ0ZXN0In0.",
                ),
            )
        assert exc_info.value.status_code == 401
        assert "no subject" in exc_info.value.detail
    finally:
        get_settings.cache_clear()


@pytest.mark.asyncio
async def test_token_with_invalid_org_returns_401(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APPLICATION__ENVIRONMENT", "development")
    monkeypatch.setenv("SECURITY__OIDC_ENABLED", "true")
    monkeypatch.setenv("SECURITY__OIDC_ISSUER", "https://issuer.example.com")
    monkeypatch.setenv("SECURITY__OIDC_AUDIENCE", "test")
    monkeypatch.setenv("SECURITY__OIDC_JWKS_URL", "https://issuer.example.com/jwks")
    get_settings.cache_clear()
    try:
        with (
            patch(
                "apps.api.security._decode_oidc_token",
                return_value={"sub": "user", "organization_id": "not-a-uuid"},
            ),
            pytest.raises(HTTPException) as exc_info,
        ):
            await get_auth_context(
                credentials=HTTPAuthorizationCredentials(scheme="Bearer", credentials="token"),
            )
        assert exc_info.value.status_code == 401
        assert "organization" in exc_info.value.detail
    finally:
        get_settings.cache_clear()
