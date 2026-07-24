# Repository Guidelines

## Project Structure & Module Organization

Application code lives under `src/`; deployable entry points are in `src/apps/`. Connectors fetch source data, while `domain/`, `portfolio/`, `backtesting/`, and `evaluation/` implement analysis. Database models live in `src/database/`, with Alembic migrations in `migrations/`. Prompts are versioned in `prompts/`. Tests belong in `tests/unit/`, infrastructure in `infra/`, and plans in `docs/`.

## Build, Test, and Development Commands

- `uv sync --all-extras` installs Python 3.12 runtime and development dependencies.
- `Copy-Item .env.example .env` creates local configuration on PowerShell; never commit the populated file.
- `docker compose --profile dev up -d` starts PostgreSQL, MinIO, Temporal, migrations, API, and workers.
- `docker compose --profile observability up -d` adds the persistent telemetry collector and MLflow.
- `alembic upgrade head` applies database migrations.
- `uvicorn apps.api.main:app --reload --app-dir src` runs the API locally.
- `pytest` runs all tests; use `pytest tests/unit/test_metrics_engine.py -q` for a focused run.
- `ruff check .` checks formatting-independent style and import order; `ruff format --check .` verifies formatting.
- `mypy src` performs strict static type checking.
- From `web/`, `npm ci && npm run build` validates the Next.js application and generated OpenAPI client.

## Coding Style & Naming Conventions

Use four-space indentation, Python 3.12 syntax, type annotations, and a 120-character line limit. Ruff enforces standard errors, imports, naming, upgrades, bug risks, and simplifications. Use `snake_case` for modules/functions, `PascalCase` for classes and Pydantic/ORM models, and `UPPER_SNAKE_CASE` for constants. Keep connector-specific logic within its provider package and expose intentional public APIs through `__init__.py`.

## Testing Guidelines

Tests use `pytest` with `pytest-asyncio` in automatic mode. Name files `test_<feature>.py` and test functions `test_<behavior>`. Add regression tests alongside every bug fix and cover success, validation, and boundary cases. Run `pytest --cov=src --cov-report=term-missing` when assessing coverage; the repository does not currently enforce a numeric threshold.

## Commit & Pull Request Guidelines

History follows Conventional Commit-style subjects such as `feat:`, `test:`, and `chore:`. Keep commits focused and use an imperative, concise summary. Pull requests should explain the motivation and behavior change, identify configuration or migration impacts, link relevant issues, and list verification commands. Include request/response examples for API changes and screenshots only for user-visible interfaces.

## Security & Configuration

Store credentials only in `.env` or a secret manager. Treat financial documents and downloaded datasets as potentially sensitive; avoid committing generated data, tokens, or production identifiers.

## Histórico de Sessão — Integração Candidate Intelligence (Jul/2026)

### O que foi feito
Integramos um overlay externo de ~9k linhas (47 arquivos) chamado **Candidate Intelligence** ao IA Investing. O overlay adiciona 7 tabelas no banco, 5 workflows Temporal, 13 arquivos de domínio, e um runtime factory de agentes.

### Correções aplicadas
- **P0-01**: `AgentRuntimeService.create_run()` passou a aceitar `organization_id: UUID` — armazenado no modelo com FK + índice
- **P0-02**: Factory em `src/ia_investing/integrations/candidate_runtime.py` com 15 callbacks; 3 conectados (persist, readiness, complete), 12 retornam checkpoint `blocked`
- **P0-04**: `SourceRegistryService.register_source()` faz upsert por `code`; reusa objetos de licença existentes
- **P0 residual**: `SSRFProtectionMiddleware` renomeado para `RequestHostValidator` (escopo só inbound); `app_factory.py` atualizado
- **Migration chain**: `f7a100000007` → `b4c000000001..005` → `20260722_01` aplicada com sucesso
- **`f7a100000008` deletada**: `b4c000000002` já adicionava `organization_id` em `agent_runtime_runs`; migration era redundante
- **`metadata` → `meta_data`**: colisão com palavra reservada do SQLAlchemy em `AuditLogEntry`
- **`.candidate-upgrade-backup/` limpo**: removido do staging, deletado do disco, adicionado ao `.gitignore`

### 18 erros de coleção corrigidos
- `WorkflowAlreadyStartedError` importado de `temporalio.exceptions` (não mais de `temporalio.client`)
- `Request | None = None` → `Request = None` em `security.py` e `auth.py` (FastAPI 0.139.2 não reconhece `Union[Request, None]` como tipo especial)
- `Response | None = None` → `Response = None` em `auth.py`
- Import circular em `candidate_dispatch.py` resolvido com import lazy dentro de `_dispatch_event`
- `SessionDep = Annotated[AsyncSession, Depends(get_async_session)]` adicionado em `dependencies.py`
- `Principal = AuthContext` adicionado em `security.py`
- `tests/__init__.py` criado (permitiu import de `tests.fixtures.golden_ai_vectors`)
- Re-exports em `worker/main.py` (`ACTIVITIES_BY_CAPABILITY` e `WORKFLOWS_BY_CAPABILITY` do registry)
- Import quebrado em `scheduler/main.py` consertado (re-export de `temporal_schedules.py`)

### 24 falhas de teste corrigidas (1025 passed, 0 failed)
- **21 falhas**: `_session_middleware` em `app_factory.py` — `session.get("roles", [])` estava fora do bloco `if session is not None:`, causando 500 em vez de 401/403. Corrigido indentando o bloco para dentro do guard e definindo `request.state.auth_context = None` para requisições anônimas
- **2 falhas**: testes de worker desatualizados porque o overlay substituiu `worker/main.py` por arquitetura baseada em registry. Atualizadas expectativas de tuples de workflows e contagem de activities
- **1 falha**: nome de constraint desatualizado em `test_operation_model.py` (`uq_operations_type_idempotency_key` → `uq_operations_org_type_idempotency_key`)

### Feature desabilitada por padrão
`CANDIDATE_INTELLIGENCE_ENABLED=false` — ativar via env vars + `CANDIDATE_RUNTIME_FACTORY=ia_investing.integrations.candidate_runtime:create_runtime`

### Limitação conhecida
Testes de integração asyncpg falham no Windows com `ConnectionResetError: [WinError 64]` — pré-existente.

## Session Memory

This project maintains a `MEMORY.md` file at the project root.
- Read it at session start to understand context and pending items.
- Update it at session end with what was done, what worked, and what failed.
- Keep only the last ~24h of session history (prune older entries).
