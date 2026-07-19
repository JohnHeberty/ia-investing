from __future__ import annotations

import asyncio
from dataclasses import dataclass
from uuid import UUID

import jwt
from fastapi import Depends, Header, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient

from ia_investing.settings import get_settings

bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True, slots=True)
class AuthContext:
    subject: str
    permissions: frozenset[str]
    authentication_method: str
    organization_id: UUID | None = None
    team_ids: frozenset[UUID] = frozenset()
    session_id: str | None = None


async def _decode_oidc_token(token: str) -> dict[str, object]:
    settings = get_settings().security
    if not settings.oidc_issuer or not settings.oidc_audience or not settings.oidc_jwks_url:
        raise HTTPException(status_code=503, detail="OIDC is not configured")
    jwks_client = PyJWKClient(settings.oidc_jwks_url)
    signing_key = await asyncio.to_thread(jwks_client.get_signing_key_from_jwt, token)
    return jwt.decode(
        token,
        signing_key.key,
        algorithms=["RS256"],
        audience=settings.oidc_audience,
        issuer=settings.oidc_issuer,
    )


async def get_auth_context(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    dev_subject: str | None = Header(default=None, alias="X-Dev-Subject"),
    dev_permissions: str = Header(default="", alias="X-Dev-Permissions"),
    dev_organization: UUID | None = Header(default=None, alias="X-Dev-Organization"),
    dev_teams: str = Header(default="", alias="X-Dev-Teams"),
) -> AuthContext:
    settings = get_settings()
    if credentials is not None:
        try:
            claims = await _decode_oidc_token(credentials.credentials)
        except jwt.PyJWTError as exc:
            raise HTTPException(status_code=401, detail="Invalid bearer token") from exc
        subject = str(claims.get("sub", ""))
        permissions_value = claims.get("permissions", claims.get("scope", ""))
        if isinstance(permissions_value, str):
            permissions = frozenset(permissions_value.replace(",", " ").split())
        elif isinstance(permissions_value, list):
            permissions = frozenset(str(value) for value in permissions_value)
        else:
            permissions = frozenset()
        if not subject:
            raise HTTPException(status_code=401, detail="Bearer token has no subject")
        organization_value = claims.get("organization_id")
        try:
            organization_id = UUID(str(organization_value)) if organization_value else None
            team_ids = frozenset(UUID(str(value)) for value in claims.get("team_ids", []))
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=401, detail="Bearer token has invalid organization claims") from exc
        return AuthContext(
            subject,
            permissions,
            "oidc",
            organization_id,
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
            team_ids,
            None,
        )
    raise HTTPException(status_code=401, detail="Authentication required")


def require_permission(permission: str):
    async def dependency(context: AuthContext = Depends(get_auth_context)) -> AuthContext:
        if permission not in context.permissions:
            raise HTTPException(status_code=403, detail="Permission denied")
        return context

    return dependency
