# ia-investing

Plataforma de pesquisa financeira com IA para o mercado brasileiro.

## Arquitetura

```
src/
├── apps/              FastAPI API, scheduler, workers (deployable entry points)
├── connectors/        B3, CVM, IR, macro, news, policy connectors
├── database/          SQLAlchemy async + ORM models + Alembic migrations
├── ia_investing/      Core application: domain, orchestration, AI, integrations
│   ├── ai/            Agent configuration, runner, provider
│   ├── application/   Application services (instruments, source registry)
│   ├── candidate_intelligence/  Candidate overlay: domain, bootstrap, contracts
│   ├── integrations/  Production runtime, CVM/B3 resolvers, factory
│   ├── orchestration/ Temporal activities, workflows, registry, queues
│   └── platform/      Database runtime, safe HTTP client
├── web/               Next.js frontend (independent package)
```

## Stack

- **Python 3.12+** com FastAPI
- **PostgreSQL 17** + pgvector
- **Temporal** para orquestração
- **OpenAI Agents SDK** com gateway compatível opcional
- **Polars/DuckDB** para processamento de dados
- **CVXPY** para otimização de portfólio
- **OpenTelemetry** para observabilidade
- **MLflow** para experiment tracking
- **S3/MinIO** para armazenamento de documentos brutos

## Setup

```bash
# Instalar dependências
uv sync --all-extras

# Copiar variáveis de ambiente
cp .env.example .env
# Editar .env com suas credenciais

# Subir a stack de desenvolvimento (migration, API e workers inclusos)
docker compose --profile dev up -d

# Alternativa: iniciar a API diretamente após aplicar as migrations
uv run alembic upgrade head
uv run uvicorn apps.api.main:app --reload --app-dir src
```

## Desenvolvimento

```bash
# Lint
ruff check .

# Type check
mypy src

# Testes
pytest tests/unit -q

# Testes de integração (requer PostgreSQL)
pytest tests/integration -q
```
