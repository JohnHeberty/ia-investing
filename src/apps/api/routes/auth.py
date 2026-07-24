from __future__ import annotations

import base64
import hashlib
import json
import secrets
from uuid import UUID

import httpx
from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel
from jose import jwk, jwt
from jose.constants import Algorithms
from jose.exceptions import JWKError, JWTError

from apps.api.security import (
    CSRF_COOKIE_NAME,
    SESSION_COOKIE_NAME,
    _session_from_request,
    create_session_token,
    decode_session_token,
    generate_csrf_token,
)
from ia_investing.settings import get_settings

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

ALLOWED_REDIRECT_HOSTS = frozenset({"localhost", "127.0.0.1"})
HTTP_TIMEOUT = httpx.Timeout(30.0)

# In-memory OIDC state store. In production, use Redis.
_oidc_states: dict[str, dict[str, str]] = {}


class LoginRequest(BaseModel):
    email: str
    password: str


class UserInfo(BaseModel):
    subject: str
    name: str | None = None
    email: str | None = None
    organization_id: str | None = None
    roles: list[str] = []
    team_ids: list[str] = []


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
    if parsed.hostname not in ALLOWED_REDIRECT_HOSTS:
        return "/"
    return url


async def _verify_jwt(id_token: str) -> dict[str, object]:
    settings = get_settings().security
    unverified_header = jwt.get_unverified_header(id_token)
    kid = unverified_header.get("kid")
    if not kid:
        raise HTTPException(status_code=401, detail="JWT missing kid header")
    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
        resp = await client.get(settings.oidc_jwks_url)
    if resp.is_error:
        raise HTTPException(status_code=503, detail="Failed to fetch JWKS")
    jwks: dict = resp.json()
    key_data = None
    for key in jwks.get("keys", []):
        if key.get("kid") == kid:
            key_data = key
            break
    if not key_data:
        raise HTTPException(status_code=401, detail="No matching JWK found")
    try:
        rsa_key = jwk.construct(key_data, algorithm=Algorithms.RS256)
    except JWKError:
        raise HTTPException(status_code=401, detail="Invalid JWK")
    try:
        claims = jwt.decode(
            id_token,
            rsa_key.to_pem().decode() if hasattr(rsa_key, "to_pem") else rsa_key,
            algorithms=[Algorithms.RS256],
            audience=settings.oidc_client_id,
            issuer=settings.oidc_issuer,
            options={"verify_at_hash": False, "verify_nonce": False},
        )
    except JWTError as exc:
        raise HTTPException(status_code=401, detail=f"JWT verification failed: {exc}")
    return claims


@router.get("/authorize")
async def authorize(
    return_to: str | None = None,
) -> dict[str, str]:
    settings = get_settings().security
    if not settings.oidc_authorization_url or not settings.oidc_client_id:
        raise HTTPException(status_code=503, detail="OIDC authorization is not configured")
    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(48)
    challenge = hashlib.sha256(verifier.encode()).digest()
    code_challenge = base64.urlsafe_b64encode(challenge).rstrip(b"=").decode()
    _oidc_states[state] = {"nonce": nonce, "verifier": verifier}
    return {
        "authorization_url": settings.oidc_authorization_url,
        "client_id": settings.oidc_client_id,
        "redirect_uri": settings.oidc_redirect_uri,
        "scope": settings.oidc_scope,
        "state": state,
        "nonce": nonce,
        "code_challenge": code_challenge,
        "return_to": _safe_return_to(return_to),
    }


@router.get("/callback")
async def callback(
    code: str | None = None,
    state: str | None = None,
    request: Request = None,
) -> dict[str, object]:
    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing authorization code or state")
    stored = _oidc_states.pop(state, None)
    if not stored:
        raise HTTPException(status_code=400, detail="Invalid or expired OIDC state")
    settings = get_settings().security
    if not settings.oidc_token_url or not settings.oidc_client_id:
        raise HTTPException(status_code=503, detail="OIDC is not configured")
    form = httpx.QueryParams({
        "grant_type": "authorization_code",
        "code": code,
        "code_verifier": stored["verifier"],
        "client_id": settings.oidc_client_id,
        "redirect_uri": settings.oidc_redirect_uri,
    })
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
        if settings.oidc_jwks_url:
            claims = await _verify_jwt(id_token)
            if claims.get("nonce") != stored["nonce"]:
                raise HTTPException(status_code=401, detail="OIDC nonce validation failed")
        else:
            import base64
            payload = id_token.split(".")[1]
            padded = payload + "=" * (4 - len(payload) % 4)
            try:
                claims = json.loads(base64.urlsafe_b64decode(padded))
            except (ValueError, json.JSONDecodeError):
                claims = {}
        subject = str(claims.get("sub", ""))
        name = str(claims.get("name", "")) or None
        org_id = claims.get("organization_id")
        organization_id = UUID(str(org_id)) if org_id else None
        roles_raw = claims.get("roles", [])
        roles = frozenset(str(r) for r in roles_raw) if isinstance(roles_raw, list) else frozenset()
        team_ids_raw = claims.get("team_ids", [])
        team_ids = (
            frozenset(UUID(str(t)) for t in team_ids_raw if t) if isinstance(team_ids_raw, list) else frozenset()
        )
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
        if request is not None:
            resp_obj = Response()
            _set_session_cookie(resp_obj, session_token)
            csrf = None
            sid = decode_session_token(session_token)
            if sid:
                csrf = generate_csrf_token(str(sid.get("sid", "")))
            if csrf:
                resp_obj.set_cookie(
                    key=CSRF_COOKIE_NAME,
                    value=csrf,
                    max_age=28_800,
                    path="/",
                    httponly=False,
                    secure=_is_production(),
                    samesite="strict",
                )
            return {"status": "authenticated"}
    raise HTTPException(status_code=401, detail="OIDC callback failed")


@router.post("/login")
async def login(
    body: LoginRequest | None = None,
    response: Response = None,
) -> dict[str, str]:
    if body is None or not body.email or not body.password:
        raise HTTPException(status_code=422, detail="Email and password are required")
    settings = get_settings().security
    if settings.oidc_token_url and settings.oidc_client_id:
        form = {
            "grant_type": "password",
            "username": body.email,
            "password": body.password,
            "client_id": settings.oidc_client_id,
            "scope": settings.oidc_scope,
        }
        if settings.oidc_client_secret:
            form["client_secret"] = settings.oidc_client_secret
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            resp = await client.post(
                settings.oidc_token_url,
                data=form,
                headers={"Accept": "application/json"},
            )
        if resp.is_error:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        token_data: dict[str, object] = resp.json()
        id_token_str = token_data.get("id_token")
        if id_token_str and isinstance(id_token_str, str):
            if settings.oidc_jwks_url:
                claims = await _verify_jwt(id_token_str)
            else:
                payload = id_token_str.split(".")[1]
                padded = payload + "=" * (4 - len(payload) % 4)
                try:
                    claims = json.loads(base64.urlsafe_b64decode(padded))
                except (ValueError, json.JSONDecodeError):
                    claims = {}
            subject = str(claims.get("sub", body.email))
            name = str(claims.get("name", "")) or None
            org_id = claims.get("organization_id")
            organization_id = UUID(str(org_id)) if org_id else None
            roles_raw = claims.get("roles", [])
            roles = frozenset(str(r) for r in roles_raw) if isinstance(roles_raw, list) else frozenset()
            team_ids_raw = claims.get("team_ids", [])
            team_ids = (
                frozenset(UUID(str(t)) for t in team_ids_raw if t) if isinstance(team_ids_raw, list) else frozenset()
            )
            permissions_raw = claims.get("permissions", "")
            permissions = frozenset(str(permissions_raw).split()) if permissions_raw else frozenset()
            session_token = create_session_token(
                subject=subject,
                organization_id=organization_id,
                roles=roles,
                team_ids=team_ids,
                permissions=permissions,
                name=name,
                email=body.email,
            )
            if response is not None:
                _set_session_cookie(response, session_token)
                sid = decode_session_token(session_token)
                if sid:
                    csrf = generate_csrf_token(str(sid.get("sid", "")))
                    response.set_cookie(
                        key=CSRF_COOKIE_NAME,
                        value=csrf,
                        max_age=28_800,
                        path="/",
                        httponly=False,
                        secure=_is_production(),
                        samesite="strict",
                    )
            return {"status": "ok", "subject": subject}
    raise HTTPException(status_code=503, detail="Direct login is not available")


@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
) -> dict[str, str]:
    _delete_session_cookie(response)
    return {"status": "ok"}


@router.get("/me")
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
    return UserInfo(
        subject=subject,
        name=str(session["name"]) if session.get("name") else None,
        email=str(session["email"]) if session.get("email") else None,
        organization_id=str(session["organization_id"]) if session.get("organization_id") else None,
        roles=roles,
        team_ids=team_ids,
    )


@router.get("/csrf-token")
async def csrf_token(
    request: Request,
    response: Response,
) -> dict[str, str]:
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
    return {"csrf_token": token}
