"""Stock Intelligence — FastAPI application entry point."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from apps.api.routes.agents import router as agents_router
from apps.api.routes.financials import router as financials_router
from apps.api.routes.health import router as health_router
from apps.api.routes.issuers import router as issuers_router
from apps.api.routes.portfolio import router as portfolio_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    from database.core import close_db, init_db

    await init_db()
    yield
    await close_db()


app = FastAPI(
    title="Stock Intelligence",
    version="0.1.0",
    description="Plataforma de pesquisa financeira com IA para o mercado brasileiro",
    lifespan=lifespan,
)

app.include_router(issuers_router)
app.include_router(financials_router)
app.include_router(portfolio_router)
app.include_router(agents_router)
app.include_router(health_router)
