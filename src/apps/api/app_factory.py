from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import APIRouter, Depends, FastAPI

from apps.api.auth import get_current_user
from apps.api.errors import install_problem_handlers
from apps.api.routes.agent_runtime import router as agent_runtime_router
from apps.api.routes.agents import router as agents_router
from apps.api.routes.financials import router as financials_router
from apps.api.routes.health import router as health_router
from apps.api.routes.institutional import router as institutional_router
from apps.api.routes.institutional_portfolios import router as institutional_portfolios_router
from apps.api.routes.instruments import router as instruments_router
from apps.api.routes.issuers import router as issuers_router
from apps.api.routes.metrics import router as metrics_router
from apps.api.routes.operations import router as operations_router
from apps.api.routes.paper_execution import router as paper_execution_router
from apps.api.routes.policy import macro_router
from apps.api.routes.policy import router as policy_router
from apps.api.routes.portfolio import router as portfolio_router
from apps.api.routes.quality import router as quality_router
from apps.api.routes.readiness import router as readiness_router
from apps.api.routes.research import router as research_router
from apps.api.routes.schedules import router as schedules_router
from apps.api.routes.sources import router as sources_router
from ia_investing.settings import Settings, get_settings
from observability import setup_telemetry


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
]

_AUTH_ROUTERS = [
    issuers_router,
    financials_router,
    portfolio_router,
    agents_router,
    operations_router,
    sources_router,
    instruments_router,
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
]


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

    if settings.telemetry.enabled:
        setup_telemetry("ia-investing-api", settings.telemetry.otlp_endpoint, app=app)

    _auth_router = APIRouter(dependencies=[Depends(get_current_user)])
    for router in _AUTH_ROUTERS:
        _auth_router.include_router(router)
    app.include_router(_auth_router)

    for router in _PUBLIC_ROUTERS:
        app.include_router(router)

    return app
