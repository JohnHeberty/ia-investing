# Repository Guidelines

## Project Structure & Module Organization

Application code lives under `src/`. Deployable entry points are in `src/apps/` (`api`, `scheduler`, and `worker`), while business capabilities are grouped by concern: `connectors/` fetches B3, CVM, macroeconomic, and news data; `normalization/`, `metrics/`, and `data_quality/` transform and validate it; `domain/`, `portfolio/`, `backtesting/`, and `evaluation/` implement core analysis. Database models and configuration live in `src/database/`, with Alembic support in `migrations/`. Agent prompts are versioned in `prompts/<agent>/system.md`. Unit tests belong in `tests/unit/`; infrastructure configuration is under `infra/`, and planning/reference material is under `docs/`.

## Build, Test, and Development Commands

- `uv sync --all-extras` installs Python 3.12 runtime and development dependencies.
- `Copy-Item .env.example .env` creates local configuration on PowerShell; never commit the populated file.
- `docker compose up -d` starts PostgreSQL/pgvector, MinIO, Temporal, MLflow, and OpenTelemetry.
- `alembic upgrade head` applies database migrations.
- `uvicorn apps.api.main:app --reload --app-dir src` runs the API locally.
- `pytest` runs all tests; use `pytest tests/unit/test_metrics_engine.py -q` for a focused run.
- `ruff check .` checks formatting-independent style and import order; `ruff format --check .` verifies formatting.
- `mypy src` performs strict static type checking.

## Coding Style & Naming Conventions

Use four-space indentation, Python 3.12 syntax, type annotations, and a 120-character line limit. Ruff enforces standard errors, imports, naming, upgrades, bug risks, and simplifications. Use `snake_case` for modules/functions, `PascalCase` for classes and Pydantic/ORM models, and `UPPER_SNAKE_CASE` for constants. Keep connector-specific logic within its provider package and expose intentional public APIs through `__init__.py`.

## Testing Guidelines

Tests use `pytest` with `pytest-asyncio` in automatic mode. Name files `test_<feature>.py` and test functions `test_<behavior>`. Add regression tests alongside every bug fix and cover success, validation, and boundary cases. Run `pytest --cov=src --cov-report=term-missing` when assessing coverage; the repository does not currently enforce a numeric threshold.

## Commit & Pull Request Guidelines

History follows Conventional Commit-style subjects such as `feat:`, `test:`, and `chore:`. Keep commits focused and use an imperative, concise summary. Pull requests should explain the motivation and behavior change, identify configuration or migration impacts, link relevant issues, and list verification commands. Include request/response examples for API changes and screenshots only for user-visible interfaces.

## Security & Configuration

Store credentials only in `.env` or a secret manager. Treat financial documents and downloaded datasets as potentially sensitive; avoid committing generated data, tokens, or production identifiers.
