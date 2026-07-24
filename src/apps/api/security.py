from __future__ import annotations

import asyncio
import hashlib
import hmac
import secrets
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt
from fastapi import Depends, Header, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient

from ia_investing.application.audit import emit_security_event
from ia_investing.application.security import ActorContext, enforce
from ia_investing.settings import Settings, get_settings

bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True, slots=True)
class AuthContext:
    subject: str
    permissions: frozenset[str]
    authentication_method: str
    organization_id: UUID | None = None
    roles: frozenset[str] = field(default_factory=frozenset)
    team_ids: frozenset[UUID] = frozenset()
    session_id: str | None = None

    def to_actor_context(self) -> ActorContext:
        return ActorContext(
            subject=self.subject,
            organization_id=self.organization_id,
            roles=self.roles,
            permissions=self.permissions,
            team_ids=self.team_ids,
            authentication_method=self.authentication_method,
        )


Principal = AuthContext


def _build_oidc_verifier(settings: Settings) -> PyJWKClient | None:
    url = settings.security.oidc_jwks_url
    return PyJWKClient(url) if url else None


async def _decode_oidc_token(
    token: str,
    verifier: PyJWKClient | None = None,
) -> dict[str, object]:
    settings = get_settings().security
    if not settings.oidc_issuer or not settings.oidc_audience or not settings.oidc_jwks_url:
        raise HTTPException(status_code=503, detail="OIDC is not configured")
    if verifier is None:
        verifier = _build_oidc_verifier(get_settings())
    assert verifier is not None
    signing_key = await asyncio.to_thread(verifier.get_signing_key_from_jwt, token)
    return jwt.decode(
        token,
        signing_key.key,
        algorithms=["RS256"],
        audience=settings.oidc_audience,
        issuer=settings.oidc_issuer,
    )


def _parse_permissions(claims: dict[str, object]) -> frozenset[str]:
    permissions_value = claims.get("permissions", claims.get("scope", ""))
    if isinstance(permissions_value, str):
        return frozenset(permissions_value.replace(",", " ").split())
    if isinstance(permissions_value, list):
        return frozenset(str(value) for value in permissions_value)
    return frozenset()


def _parse_roles(claims: dict[str, object]) -> frozenset[str]:
    roles_value = claims.get("roles", claims.get("groups", []))
    if isinstance(roles_value, str):
        return frozenset(roles_value.replace(",", " ").split())
    if isinstance(roles_value, list):
        return frozenset(str(value) for value in roles_value)
    return frozenset()


async def get_auth_context(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    dev_subject: str | None = Header(default=None, alias="X-Dev-Subject"),
    dev_permissions: str = Header(default="", alias="X-Dev-Permissions"),
    dev_organization: UUID | None = Header(default=None, alias="X-Dev-Organization"),
    dev_teams: str = Header(default="", alias="X-Dev-Teams"),
    request: Request = None,  # type: ignore[assignment]
) -> AuthContext:
    if request is not None:
        session_context: AuthContext | None = getattr(request.state, "auth_context", None)
        if session_context is not None:
            return session_context
    settings = get_settings()
    if credentials is not None:
        try:
            verifier: PyJWKClient | None = None
            if request is not None and hasattr(request.app.state, "oidc_verifier"):
                verifier = request.app.state.oidc_verifier
            if settings.security.oidc_enabled:
                claims = await _decode_oidc_token(credentials.credentials, verifier)
            elif settings.application.environment != "production":
                claims = jwt.decode(
                    credentials.credentials,
                    options={"verify_signature": False},
                )
            else:
                emit_security_event("auth_failure", outcome="deny", detail="OIDC is not configured in production")
                raise HTTPException(status_code=503, detail="OIDC is not configured")
        except HTTPException:
            raise
        except jwt.PyJWTError as exc:
            emit_security_event("auth_failure", detail=f"Invalid bearer token: {exc}")
            raise HTTPException(status_code=401, detail="Invalid bearer token") from exc
        subject = str(claims.get("sub", ""))
        if not subject:
            emit_security_event("auth_failure", detail="Bearer token has no subject")
            raise HTTPException(status_code=401, detail="Bearer token has no subject")
        permissions = _parse_permissions(claims)
        roles = _parse_roles(claims)
        organization_value = claims.get("organization_id")
        try:
            organization_id = UUID(str(organization_value)) if organization_value else None
            raw_team_ids = claims.get("team_ids")
            team_ids_value: list[object] = raw_team_ids if isinstance(raw_team_ids, list) else []
            team_ids = frozenset(UUID(str(value)) for value in team_ids_value)
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=401, detail="Bearer token has invalid organization claims") from exc
        return AuthContext(
            subject,
            permissions,
            "oidc",
            organization_id,
            roles,
            team_ids,
            str(claims.get("sid") or claims.get("jti") or "") or None,
        )

    if settings.application.environment != "production" and dev_subject:
        try:
            team_ids = frozenset(UUID(value) for value in dev_teams.replace(",", " ").split())
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="X-Dev-Teams contains an invalid UUID") from exc
        return AuthContext(
            dev_subject,
            frozenset(dev_permissions.replace(",", " ").split()),
            "development-header",
            dev_organization,
            frozenset(),
            team_ids,
            None,
        )
    emit_security_event("auth_failure", detail="Authentication required")
    raise HTTPException(status_code=401, detail="Authentication required")


def require_permission(permission: str) -> Callable[[AuthContext], Awaitable[AuthContext]]:
    async def dependency(context: AuthContext = Depends(get_auth_context)) -> AuthContext:
        resource, action = permission.split(":", 1) if ":" in permission else (permission, "*")
        if not enforce(resource, action, context.to_actor_context()):
            emit_security_event(
                "permission_denied",
                actor=context.subject,
                resource=resource,
                action=action,
                detail=f"Missing permission: {permission}",
            )
            raise HTTPException(status_code=403, detail="Permission denied")
        return context

    return dependency


SESSION_COOKIE_NAME = "ia_session"
CSRF_COOKIE_NAME = "ia_csrf_token"
SESSION_DURATION = timedelta(hours=8)
COOKIE_SECURE_DEFAULT = False


def _session_key(settings: Settings) -> str:
    key = settings.security.session_secret_key
    if not key:
        raise RuntimeError("SECURITY__SESSION_SECRET_KEY is not configured")
    return key


def _csrf_key(settings: Settings) -> str:
    key = settings.security.csrf_secret_key
    if not key:
        key = _session_key(settings)
    return key


def create_session_token(
    subject: str,
    organization_id: UUID | None = None,
    roles: frozenset[str] = frozenset(),
    team_ids: frozenset[UUID] = frozenset(),
    permissions: frozenset[str] = frozenset(),
    name: str | None = None,
    email: str | None = None,
    extra: dict[str, object] | None = None,
) -> str:
    now = datetime.now(UTC)
    payload: dict[str, object] = {
        "sub": subject,
        "iat": now,
        "exp": now + SESSION_DURATION,
        "sid": secrets.token_hex(16),
    }
    if organization_id:
        payload["organization_id"] = str(organization_id)
    if roles:
        payload["roles"] = list(roles)
    if team_ids:
        payload["team_ids"] = [str(t) for t in team_ids]
    if permissions:
        payload["permissions"] = list(permissions)
    if name:
        payload["name"] = name
    if email:
        payload["email"] = email
    if extra:
        payload.update(extra)
    settings = get_settings()
    return jwt.encode(payload, _session_key(settings), algorithm="HS256")


def decode_session_token(token: str) -> dict[str, object] | None:
    settings = get_settings()
    try:
        return jwt.decode(
            token,
            _session_key(settings),
            algorithms=["HS256"],
            options={"require": ["sub", "exp", "iat"]},
        )
    except jwt.PyJWTError:
        return None


def _session_from_request(request: Request) -> dict[str, object] | None:
    raw = request.cookies.get(SESSION_COOKIE_NAME)
    if not raw:
        return None
    return decode_session_token(raw)


def generate_csrf_token(session_id: str) -> str:
    settings = get_settings()
    digest = hmac.new(
        _csrf_key(settings).encode(),
        session_id.encode(),
        hashlib.sha256,
    ).hexdigest()
    return f"{session_id}:{digest}"


def validate_csrf_token(token: str, expected_session_id: str) -> bool:
    settings = get_settings()
    parts = token.split(":", 1)
    if len(parts) != 2:
        return False
    session_id, digest = parts
    expected = hmac.new(
        _csrf_key(settings).encode(),
        session_id.encode(),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(digest, expected):
        return False
    if session_id != expected_session_id:
        return False
    return True
