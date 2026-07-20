"""Stock Intelligence — FastAPI application entry point."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from apps.api.errors import install_problem_handlers
from apps.api.routes.agent_runtime import router as agent_runtime_router
from apps.api.routes.agents import router as agents_router
from apps.api.routes.financials import router as financials_router
from apps.api.routes.health import router as health_router
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
from ia_investing.settings import get_settings
from observability import setup_telemetry


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    from database.core import close_db
    from ia_investing.ai.artifacts import ArtifactLoader

    prompts_root = Path(__file__).resolve().parents[3] / "prompts"
    app.state.agent_registry = ArtifactLoader(prompts_root).load_registry()
    yield
    await close_db()


app = FastAPI(
    title="Stock Intelligence",
    version="0.1.0",
    description="Plataforma de pesquisa financeira com IA para o mercado brasileiro",
    lifespan=lifespan,
)
install_problem_handlers(app)

_settings = get_settings()
if _settings.telemetry.enabled:
    setup_telemetry("ia-investing-api", _settings.telemetry.otlp_endpoint, app=app)

app.include_router(issuers_router)
app.include_router(financials_router)
app.include_router(portfolio_router)
app.include_router(agents_router)
app.include_router(health_router)
app.include_router(operations_router)
app.include_router(sources_router)
app.include_router(instruments_router)
app.include_router(quality_router)
app.include_router(metrics_router)
app.include_router(research_router)
app.include_router(agent_runtime_router)
app.include_router(institutional_portfolios_router)
app.include_router(policy_router)
app.include_router(macro_router)
app.include_router(paper_execution_router)
app.include_router(readiness_router)
app.include_router(schedules_router)
