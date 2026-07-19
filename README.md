# ia-investing

Plataforma de pesquisa financeira com IA para o mercado brasileiro.

## Arquitetura

```
apps/
├── api/          FastAPI REST API
├── scheduler/    Agendamento de tarefas
└── worker/       Workers assíncronos

packages/
├── agents/       Agentes OpenAI (filing_analyst, news_analyst, etc.)
├── b3/           Conector B3 (COTAHIST)
├── cvm/          Conector CVM (DFP, ITR, FCA, CAD)
├── database/     SQLAlchemy async + modelos ORM
├── domain/       Domínio de negócio
├── portfolio/    Otimização com CVXPY
└── workflows/    Temporal workflows
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
mypy packages/ apps/

# Testes
pytest
```
