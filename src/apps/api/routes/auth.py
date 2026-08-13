from __future__ import annotations

import base64
import hashlib
import logging
import secrets
from uuid import UUID

import httpx
import jwt
from fastapi import APIRouter, HTTPException, Request, Response
from jwt import PyJWKClient
from pydantic import BaseModel, ConfigDict

from apps.api.security import (
    CSRF_COOKIE_NAME,
    SESSION_COOKIE_NAME,
    _session_from_request,
    create_session_token,
    decode_session_token,
    generate_csrf_token,
)
from ia_investing.application.security import get_security_auditor
from ia_investing.settings import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

HTTP_TIMEOUT = httpx.Timeout(30.0)


def _get_allowed_redirect_hosts() -> frozenset[str]:
    settings = get_settings()
    return frozenset(settings.security.allowed_redirect_hosts)


# SECURITY: In-memory OIDC state store — NOT shared across workers.
# With multiple uvicorn/gunicorn workers, state is lost between processes,
# causing "Invalid or expired OIDC state" errors for ~50% of callbacks.
# Mitigation: run with a single worker (e.g. uvicorn --workers 1) or replace
# with a shared store (Redis, database). See Issue #4.
_oidc_states: dict[str, dict[str, object]] = {}
_OIDC_STATE_TTL_SECONDS = 600  # 10 minutes
logger.warning("OIDC state store is in-memory — single-worker mode required for OIDC to work")


def _evict_expired_states() -> None:
    """Remove OIDC states older than _OIDC_STATE_TTL_SECONDS."""
    import time

    now = time.monotonic()
    expired = []
    for key, value in _oidc_states.items():
        created_at = value.get("created_at")
        if isinstance(created_at, (int, float)) and now - created_at > _OIDC_STATE_TTL_SECONDS:
            expired.append(key)
    for k in expired:
        del _oidc_states[k]


class LoginRequest(BaseModel):
    email: str
    password: str


class UserInfo(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    subject: str
    name: str | None = None
    email: str | None = None
    organization_id: str | None = None
    roles: list[str] = []
    team_ids: list[str] = []
    permissions: list[str] = []


class AuthorizeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    authorization_url: str
    client_id: str
    redirect_uri: str
    scope: str
    state: str
    nonce: str
    code_challenge: str
    return_to: str


class CallbackResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: str


class LoginDisabledResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    detail: str


class LogoutResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: str


class CsrfTokenResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    csrf_token: str


def _is_production() -> bool:
    return get_settings().application.environment == "production"


def _set_session_cookie(response: Response, token: str) -> None:
    secure = _is_production()
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=28_800,
        path="/",
        httponly=True,
        secure=secure,
        samesite="strict",
    )


def _delete_session_cookie(response: Response) -> None:
    secure = _is_production()
    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        path="/",
        httponly=True,
        secure=secure,
        samesite="strict",
    )
    response.delete_cookie(
        key=CSRF_COOKIE_NAME,
        path="/",
        secure=secure,
        samesite="strict",
    )


def _safe_return_to(url: str | None) -> str:
    if not url:
        return "/"
    if not url.startswith(("http:", "https:")):
        return "/"
    from urllib.parse import urlparse

    parsed = urlparse(url)
    if parsed.hostname not in _get_allowed_redirect_hosts():
        return "/"
    return url


async def _verify_jwt(id_token: str) -> dict[str, object]:
    settings = get_settings().security
    if not settings.oidc_jwks_url:
        raise HTTPException(status_code=503, detail="OIDC JWKS URL is not configured")
    try:
        jwks_client = PyJWKClient(settings.oidc_jwks_url)
        signing_key = jwks_client.get_signing_key_from_jwt(id_token)
        claims = jwt.decode(
            id_token,
            signing_key.key,
            algorithms=["RS256"],
            audience=settings.oidc_audience,
            issuer=settings.oidc_issuer,
            options={"verify_exp": True},
        )
    except jwt.ExpiredSignatureError as exc:
        get_security_auditor().on_auth_failure(token_present=True, detail="JWT has expired")
        raise HTTPException(status_code=401, detail="JWT has expired") from exc
    except jwt.InvalidAudienceError as exc:
        get_security_auditor().on_auth_failure(token_present=True, detail="JWT audience mismatch")
        raise HTTPException(status_code=401, detail="JWT audience mismatch") from exc
    except jwt.InvalidIssuerError as exc:
        get_security_auditor().on_auth_failure(token_present=True, detail="JWT issuer mismatch")
        raise HTTPException(status_code=401, detail="JWT issuer mismatch") from exc
    except jwt.DecodeError as exc:
        get_security_auditor().on_auth_failure(token_present=True, detail="JWT decode failed")
        raise HTTPException(status_code=401, detail="JWT decode failed") from exc
    except jwt.InvalidTokenError as exc:
        logger.warning("JWT verification failed: %s", exc)
        get_security_auditor().on_auth_failure(token_present=True, detail=str(exc))
        raise HTTPException(status_code=401, detail="JWT verification failed") from exc
    return dict(claims)


@router.get("/authorize", response_model=AuthorizeResponse)
async def authorize(
    return_to: str | None = None,
) -> AuthorizeResponse:
    settings = get_settings().security
    if not settings.oidc_authorization_url or not settings.oidc_client_id:
        raise HTTPException(status_code=503, detail="OIDC authorization is not configured")
    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(48)
    challenge = hashlib.sha256(verifier.encode()).digest()
    code_challenge = base64.urlsafe_b64encode(challenge).rstrip(b"=").decode()
    import time

    _evict_expired_states()
    _oidc_states[state] = {"nonce": nonce, "verifier": verifier, "created_at": time.monotonic()}
    return AuthorizeResponse(
        authorization_url=settings.oidc_authorization_url,
        client_id=settings.oidc_client_id,
        redirect_uri=settings.oidc_redirect_uri,
        scope=settings.oidc_scope,
        state=state,
        nonce=nonce,
        code_challenge=code_challenge,
        return_to=_safe_return_to(return_to),
    )


@router.get("/callback")
async def callback(
    code: str | None = None,
    state: str | None = None,
    request: Request = None,  # type: ignore[assignment]
) -> Response:
    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing authorization code or state")
    _evict_expired_states()
    stored = _oidc_states.pop(state, None)
    if not stored:
        raise HTTPException(status_code=400, detail="Invalid or expired OIDC state")
    settings = get_settings().security
    if not settings.oidc_token_url or not settings.oidc_client_id:
        raise HTTPException(status_code=503, detail="OIDC is not configured")
    form = httpx.QueryParams(
        {
            "grant_type": "authorization_code",
            "code": code,
            "code_verifier": str(stored["verifier"]),
            "client_id": settings.oidc_client_id,
            "redirect_uri": settings.oidc_redirect_uri,
        }
    )
    if settings.oidc_client_secret:
        form = form.add("client_secret", settings.oidc_client_secret)
    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
        resp = await client.post(
            settings.oidc_token_url,
            data=form,
            headers={"Accept": "application/json"},
        )
    if resp.is_error:
        raise HTTPException(status_code=401, detail="OIDC token exchange failed")
    token_data: dict[str, object] = resp.json()
    access_token = token_data.get("access_token")
    id_token = token_data.get("id_token")
    if not access_token or not isinstance(access_token, str):
        raise HTTPException(status_code=401, detail="OIDC token response missing access_token")
    if id_token and isinstance(id_token, str):
        if not settings.oidc_jwks_url:
            raise HTTPException(status_code=503, detail="OIDC JWKS URL is required for token verification")
        claims = await _verify_jwt(id_token)
        if claims.get("nonce") != stored["nonce"]:
            raise HTTPException(status_code=401, detail="OIDC nonce validation failed")
        subject = str(claims.get("sub", ""))
        name = str(claims.get("name", "")) or None
        org_id = claims.get("organization_id")
        organization_id = UUID(str(org_id)) if org_id else None
        roles_raw = claims.get("roles", [])
        roles = frozenset(str(r) for r in roles_raw) if isinstance(roles_raw, list) else frozenset()
        team_ids_raw = claims.get("team_ids", [])
        team_ids = frozenset(UUID(str(t)) for t in team_ids_raw if t) if isinstance(team_ids_raw, list) else frozenset()
        permissions_raw = claims.get("permissions", "")
        permissions = frozenset(str(permissions_raw).split()) if permissions_raw else frozenset()
        session_token = create_session_token(
            subject=subject,
            organization_id=organization_id,
            roles=roles,
            team_ids=team_ids,
            permissions=permissions,
            name=name,
        )
        # SECURITY FIX: Return a real Response with both cookies AND JSON body.
        # Previously, cookies were set on a discarded Response() and a bare
        # CallbackResponse was returned — the client never received the cookies.
        response = Response(
            content='{"status":"authenticated"}',
            media_type="application/json",
        )
        _set_session_cookie(response, session_token)
        csrf = None
        sid = decode_session_token(session_token)
        if sid:
            csrf = generate_csrf_token(str(sid.get("sid", "")))
        if csrf:
            response.set_cookie(
                key=CSRF_COOKIE_NAME,
                value=csrf,
                max_age=28_800,
                path="/",
                httponly=False,
                secure=_is_production(),
                samesite="strict",
            )
        return response
    raise HTTPException(status_code=401, detail="OIDC callback failed")


@router.post("/login")
async def login() -> dict[str, str]:
    raise HTTPException(
        status_code=410,
        detail="Password grant is disabled. Use the OIDC authorization-code flow with PKCE.",
    )


@router.post("/logout", response_model=LogoutResponse)
async def logout(
    request: Request,
    response: Response,
) -> LogoutResponse:
    _delete_session_cookie(response)
    return LogoutResponse(status="ok")


@router.get("/me", response_model=UserInfo)
async def me(
    request: Request,
) -> UserInfo:
    session = _session_from_request(request)
    if session is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    subject = str(session.get("sub", ""))
    if not subject:
        raise HTTPException(status_code=401, detail="Invalid session")
    team_ids_raw = session.get("team_ids", [])
    team_ids = [str(t) for t in team_ids_raw] if isinstance(team_ids_raw, list) else []
    roles_raw = session.get("roles", [])
    roles = [str(r) for r in roles_raw] if isinstance(roles_raw, list) else []
    permissions_raw = session.get("permissions", [])
    permissions = [str(p) for p in permissions_raw] if isinstance(permissions_raw, list) else []
    return UserInfo(
        subject=subject,
        name=str(session["name"]) if session.get("name") else None,
        email=str(session["email"]) if session.get("email") else None,
        organization_id=str(session["organization_id"]) if session.get("organization_id") else None,
        roles=roles,
        team_ids=team_ids,
        permissions=permissions,
    )


@router.get("/csrf-token", response_model=CsrfTokenResponse)
async def csrf_token(
    request: Request,
    response: Response,
) -> CsrfTokenResponse:
    session = _session_from_request(request)
    if session is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    session_id = str(session.get("sid", ""))
    token = generate_csrf_token(session_id)
    settings = get_settings()
    response.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=token,
        max_age=28_800,
        path="/",
        httponly=False,
        secure=settings.application.environment == "production",
        samesite="strict",
    )
    return CsrfTokenResponse(csrf_token=token)
