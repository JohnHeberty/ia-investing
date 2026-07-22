from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, FastAPI, Request, Response

from apps.api.auth import get_current_user
from apps.api.errors import install_problem_handlers
from apps.api.middleware.rate_limit import RateLimitMiddleware
from apps.api.middleware.request_host_validator import RequestHostValidator
from apps.api.middleware.security_headers import SecurityHeadersMiddleware
from apps.api.routes.agent_runtime import router as agent_runtime_router
from apps.api.routes.agents import router as agents_router
from apps.api.routes.audit import router as audit_router
from apps.api.routes.auth import router as auth_router
from apps.api.routes.committee import router as committee_router
from apps.api.routes.executions import router as executions_router
from apps.api.routes.financials import router as financials_router
from apps.api.routes.health import router as health_router
from apps.api.routes.institutional import router as institutional_router
from apps.api.routes.institutional_portfolios import router as institutional_portfolios_router
from apps.api.routes.instruments import router as instruments_router
from apps.api.routes.investment_candidates import exploration_router
from apps.api.routes.investment_candidates import router as investment_candidates_router
from apps.api.routes.issuers import router as issuers_router
from apps.api.routes.metrics import router as metrics_router
from apps.api.routes.operations import router as operations_router
from apps.api.routes.paper_execution import router as paper_execution_router
from apps.api.routes.policy import macro_router
from apps.api.routes.policy import router as policy_router
from apps.api.routes.portfolio import router as portfolio_router
from apps.api.routes.quality import router as quality_router
from apps.api.routes.readiness import router as readiness_router
from apps.api.routes.rebalance import router as rebalance_router
from apps.api.routes.research import router as research_router
from apps.api.routes.schedules import router as schedules_router
from apps.api.routes.sources import router as sources_router
from apps.api.security import (
    AuthContext,
    _session_from_request,
    generate_csrf_token,
    validate_csrf_token,
)
from ia_investing.settings import Settings, get_settings
from observability import setup_telemetry

_MUTATING = frozenset({"POST", "PUT", "PATCH", "DELETE"})

_NO_CSRF_PATHS = frozenset(
    {
        "/api/v1/health",
        "/api/v1/readiness",
    }
)


def _build_lifespan(settings: Settings):
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
        from apps.api.security import _build_oidc_verifier
        from ia_investing.ai.artifacts import ArtifactLoader

        prompts_root = Path(__file__).resolve().parents[3] / "prompts"
        app.state.agent_registry = ArtifactLoader(prompts_root).load_registry()
        app.state.oidc_verifier = _build_oidc_verifier(settings)
        yield
        from ia_investing.database.core import close_db

        await close_db()

    return lifespan


_PUBLIC_ROUTERS = [
    health_router,
    readiness_router,
    auth_router,
]

_AUTH_ROUTERS = [
    issuers_router,
    financials_router,
    portfolio_router,
    agents_router,
    operations_router,
    sources_router,
    instruments_router,
    investment_candidates_router,
    exploration_router,
    quality_router,
    metrics_router,
    research_router,
    agent_runtime_router,
    institutional_router,
    institutional_portfolios_router,
    policy_router,
    macro_router,
    paper_execution_router,
    schedules_router,
    audit_router,
    committee_router,
    executions_router,
    rebalance_router,
]


async def _session_middleware(request: Request, call_next):
    if not request.url.path.startswith("/api/v1/auth/"):
        session = _session_from_request(request)
        if session is not None:
            org_id = session.get("organization_id")
            try:
                organization_id = UUID(str(org_id)) if org_id else None
            except (TypeError, ValueError):
                organization_id = None
            team_ids_raw = session.get("team_ids", [])
            if isinstance(team_ids_raw, list):
                team_ids = frozenset(UUID(str(t)) for t in team_ids_raw if t)
            else:
                team_ids = frozenset()
        roles_raw = session.get("roles", [])
        roles = frozenset(str(r) for r in roles_raw) if isinstance(roles_raw, list) else frozenset()
        permissions_raw = session.get("permissions", [])
        permissions = frozenset(str(p) for p in permissions_raw) if isinstance(permissions_raw, list) else frozenset()
        request.state.auth_context = AuthContext(
            subject=str(session.get("sub", "")),
            permissions=permissions,
            authentication_method="session",
            organization_id=organization_id,
            roles=roles,
            team_ids=team_ids,
            session_id=str(session.get("sid", "")),
        )
    return await call_next(request)


async def _csrf_middleware(request: Request, call_next):
    if (
        request.method in _MUTATING
        and not request.url.path.startswith("/api/v1/auth/")
        and request.url.path not in _NO_CSRF_PATHS
    ):
        auth_context: AuthContext | None = getattr(request.state, "auth_context", None)
        if auth_context is not None and auth_context.session_id:
            provided = request.headers.get("x-csrf-token", "")
            if not provided or not validate_csrf_token(provided, auth_context.session_id):
                from fastapi.responses import JSONResponse

                return JSONResponse(
                    status_code=403,
                    content={"detail": "CSRF token validation failed"},
                )
    response: Response = await call_next(request)
    auth_context: AuthContext | None = getattr(request.state, "auth_context", None)
    if auth_context is not None and auth_context.session_id:
        csrf_token = generate_csrf_token(auth_context.session_id)
        response.set_cookie(
            key="ia_csrf_token",
            value=csrf_token,
            max_age=28_800,
            path="/",
            httponly=False,
            secure=get_settings().application.environment == "production",
            samesite="strict",
        )
    return response


def create_app(settings: Settings | None = None) -> FastAPI:
    if settings is None:
        settings = get_settings()

    lifespan = _build_lifespan(settings)

    app = FastAPI(
        title="Stock Intelligence",
        version="0.1.0",
        description="Plataforma de pesquisa financeira com IA para o mercado brasileiro",
        lifespan=lifespan,
    )
    install_problem_handlers(app)

    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RequestHostValidator)
    app.add_middleware(RateLimitMiddleware)

    app.middleware("http")(_session_middleware)
    app.middleware("http")(_csrf_middleware)

    if settings.telemetry.enabled:
        setup_telemetry("ia-investing-api", settings.telemetry.otlp_endpoint, app=app)

    _auth_router = APIRouter(dependencies=[Depends(get_current_user)])
    for router in _AUTH_ROUTERS:
        _auth_router.include_router(router)
    app.include_router(_auth_router)

    for router in _PUBLIC_ROUTERS:
        app.include_router(router)

    return app
