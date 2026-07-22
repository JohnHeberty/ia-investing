"""Single database runtime for API and workers.

Migrations are never executed by the application process. Startup only verifies
that the schema exists and is at the expected consolidated head.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

EXPECTED_ALEMBIC_HEAD = "b4c000000002"
REQUIRED_TABLES = (
    "model_portfolios",
    "institutional_portfolio_versions",
    "portfolio_ranking_snapshots",
    "operation_dispatch_outbox",
    "agent_runtime_runs",
    "data_sources",
    "research_cases",
)


def normalize_async_database_url(url: str) -> str:
    """Use the driver that is actually declared by the project (psycopg)."""
    if url.startswith("postgresql+asyncpg://"):
        return url.replace("postgresql+asyncpg://", "postgresql+psycopg://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


@dataclass(slots=True)
class DatabaseRuntime:
    engine: AsyncEngine
    sessions: async_sessionmaker[AsyncSession]

    @classmethod
    def create(cls, database_url: str, *, echo: bool = False) -> DatabaseRuntime:
        engine = create_async_engine(
            normalize_async_database_url(database_url),
            echo=echo,
            pool_pre_ping=True,
            pool_recycle=1_800,
        )
        return cls(engine=engine, sessions=async_sessionmaker(engine, expire_on_commit=False))

    async def assert_schema_ready(self) -> None:
        async with self.engine.connect() as connection:
            heads = set((await connection.execute(text("SELECT version_num FROM alembic_version"))).scalars().all())
            if heads != {EXPECTED_ALEMBIC_HEAD}:
                raise RuntimeError(
                    "database schema is not at the consolidated head; "
                    f"expected {EXPECTED_ALEMBIC_HEAD!r}, found {sorted(heads)!r}. "
                    "Run `alembic upgrade head` in the migration job."
                )
            for table_name in REQUIRED_TABLES:
                exists = await connection.scalar(
                    text("SELECT to_regclass(:table_name) IS NOT NULL"),
                    {"table_name": f"public.{table_name}"},
                )
                if not exists:
                    raise RuntimeError(f"required table {table_name!r} is missing")

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        async with self.sessions() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise

    async def dispose(self) -> None:
        await self.engine.dispose()
