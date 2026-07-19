# Inventário do Repositório — F0-PR01

**Baseline tag:** `baseline/f19bbc8`
**Commit:** `f19bbc868db3365d80ae8bfeb86143d6e5e218f0`
**Branch:** `main`
**Data da captura:** 2026-07-18T21:18:20-03:00
**Autor:** John Heberty de Freitas

---

## 1. Estatísticas Gerais

| Categoria | Quantidade |
|---|---|
| Arquivos Python em `src/` | 113 |
| Linhas totais em `src/` | ~5.737 |
| Arquivos de teste | 8 |
| Linhas de teste | 623 |
| Subpacotes `src/` | 17 |
| Rotas da API | 5 routers, ~14 endpoints |
| Workflows Temporal | 4 |
| Modelos ORM | ~50+ |
| Configs de agentes | 7 |
| Arquivos de prompt | 4 existentes (3 ausentes) |
| Serviços Docker | 6 |
| Dependências runtime | 27 |
| Dependências dev | 6 |
| Variáveis de ambiente | 18+ |
| Migrations Alembic | 0 (não utilizado) |
| Pipelines CI | 0 (nenhum configurado) |

---

## 2. Estrutura de Diretórios

```
ia-investing/
├── src/
│   ├── agents/              324 linhas   Framework de agentes (OpenAI Agents SDK)
│   ├── apps/
│   │   ├── api/             316 linhas   FastAPI REST API
│   │   ├── scheduler/        89 linhas   Agendador asyncio
│   │   └── worker/           41 linhas   Temporal worker
│   ├── backtesting/         342 linhas   Engine de backtest
│   ├── connectors/         1.053 linhas  5 fontes de dados
│   │   ├── b3/              278 linhas   COTAHIST B3
│   │   ├── cvm/             330 linhas   DFP/ITR/FCA CVM
│   │   ├── investor_relations/ 98 linhas  RI scraping
│   │   ├── macro/           239 linhas   BCB/SIDRA
│   │   └── news/            114 linhas   RSS
│   ├── data_quality/        378 linhas   Validação financeira
│   ├── database/            710 linhas   SQLAlchemy + config
│   │   └── models/          709 linhas   50+ modelos ORM
│   ├── domain/              198 linhas   RAG + vector store
│   ├── evaluation/          278 linhas   Avaliação de agentes
│   ├── metrics/             405 linhas   50+ métricas financeiras
│   ├── normalization/       291 linhas   Normalização CVM
│   ├── observability/        81 linhas   OpenTelemetry
│   ├── parsers/             122 linhas   PDF + HTML
│   ├── portfolio/           280 linhas   CVXPY otimização
│   ├── schemas/             100 linhas   Pydantic models
│   └── workflows/           322 linhas   4 workflows Temporal
├── tests/unit/              623 linhas   8 arquivos de teste
├── migrations/               62 linhas   Alembic (sem versions/)
├── prompts/                 145 linhas   4 prompts existentes
├── infra/                    47 linhas   OTel collector config
├── docs/                            Plano v1/v2, livros
├── docker-compose.yml              6 serviços
├── Dockerfile                      Multi-stage build
├── pyproject.toml                  Configurações
├── alembic.ini                     Alembic config
└── .env.example                    18 variáveis
```

---

## 3. Entrypoints

| Entrypoint | Caminho | Tipo | Comando |
|---|---|---|---|
| FastAPI API | `src/apps/api/main.py` | ASGI (`app`) | `uvicorn apps.api.main:app --reload --app-dir src` |
| Temporal Worker | `src/apps/worker/main.py` | async function | `asyncio.run(start_worker())` |
| Scheduler | `src/apps/scheduler/main.py` | async function | `asyncio.run(run_scheduler())` |

**Dockerfile CMD:** `uvicorn apps.api.main:app --host 0.0.0.0 --port 8000`

---

## 4. Classificação dos Módulos

| Módulo | Classificação | Justificativa |
|---|---|---|
| `src/agents/` | PRESERVAR | Framework core de agentes, bem estruturado |
| `src/apps/api/` | PRESERVAR | FastAPI minimal, 5 routers |
| `src/apps/scheduler/` | REFACTOR | Loop asyncio simples; usar Temporal ou APScheduler |
| `src/apps/worker/` | PRESERVAR | Temporal worker, padrão produtivo |
| `src/backtesting/` | PRESERVAR | Self-contained, sem acoplamento externo |
| `src/connectors/` | PRESERVAR | 5 fontes bem organizadas, HTTP base compartilhado |
| `src/data_quality/` | PRESERVAR | Validação financeira bem testada |
| `src/database/` | REFACTOR | Core bom, mas models/ extenso (709 linhas, 17 arquivos) |
| `src/database/models/` | REFACTOR | 50+ modelos, convenções mistas, migrations não utilizadas |
| `src/domain/` | REFACTOR | RAG stub (198 linhas), implementações pequenas |
| `src/evaluation/` | REFACTOR | Sem testes, sem integração com API |
| `src/metrics/` | PRESERVAR | 50+ métricas, engine limpa, testado |
| `src/normalization/` | PRESERVAR | Normalização CVM, production-grade |
| `src/observability/` | PRESERVAR | Padrão OpenTelemetry padrão |
| `src/parsers/` | PRESERVAR | PDF + HTML, pequeno e reutilizável |
| `src/portfolio/` | PRESERVAR | CVXPY + scorecard, testado |
| `src/schemas/` | PRESERVAR | Pydantic models, 8 schemas |
| `src/workflows/` | PRESERVAR | 4 workflows Temporal, core de orquestração |

---

## 5. Comandos Registrados

### Instalação e setup
```bash
uv sync --all-extras
cp .env.example .env
docker compose up -d
alembic upgrade head  # (nenhuma migration existe ainda)
```

### Desenvolvimento
```bash
uvicorn apps.api.main:app --reload --app-dir src  # API local
```

### Qualidade
```bash
ruff check .                # linting
ruff format --check .       # verificação de formatação
mypy src                    # type checking
pytest                      # testes
pytest --cov=src --cov-report=term-missing  # cobertura
```

### Docker
```bash
docker compose up -d                    # todos os serviços
docker compose up -d postgres minio     # apenas infraestrutura
```

---

## 6. Variáveis de Ambiente

| Variável | Default | Obrigatória | Sensível | Descrição |
|---|---|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://...` | Sim | Não | Conexão PostgreSQL |
| `STORAGE_ENDPOINT` | `http://localhost:9000` | Sim | Não | MinIO/S3 |
| `STORAGE_ACCESS_KEY` | `minioadmin` | Sim | Não | S3 access key |
| `STORAGE_SECRET_KEY` | `minioadmin` | Sim | **Sim** | S3 secret key |
| `STORAGE_BUCKET` | `raw-documents` | Sim | Não | Bucket S3 |
| `OPENAI_API_KEY` | `sk-your-key-here` | Sim | **Sim** | Chave OpenAI |
| `OPENAI_BASE_URL` | `https://api.openai.com/v1` | Não | Não | Base URL OpenAI |
| `LITELLM_GATEWAY_URL` | `http://localhost:4000/v1` | Não | Não | Gateway LiteLLM |
| `TEMPORAL_ADDRESS` | `localhost:7233` | Sim | Não | Servidor Temporal |
| `TEMPORAL_NAMESPACE` | `default` | Sim | Não | Namespace Temporal |
| `TEMPORAL_TASK_QUEUE` | `stock-intelligence` | Sim | Não | Fila Temporal |
| `OTLP_ENDPOINT` | `http://localhost:4317` | Não | Não | Coletor OTel |
| `ENABLE_OTEL` | `true` | Não | Não | Habilitar OTel |
| `MLFLOW_TRACKING_URI` | `http://localhost:5000` | Não | Não | MLflow server |
| `APP_ENV` | `development` | Sim | Não | Ambiente |
| `LOG_LEVEL` | `DEBUG` | Não | Não | Nível de log |
| `DB_POOL_SIZE` | `10` | Não | Não | Pool size SQLAlchemy |
| `DB_MAX_OVERFLOW` | `20` | Não | Não | Max overflow pool |

---

## 7. Prompts

### Existentes (4)
| Agente | Arquivo | Linhas |
|---|---|---|
| Comitê de Investimento | `prompts/committee/system.md` | 33 |
| Agente Crítico | `prompts/critic/system.md` | 37 |
| Analista de Documentos | `prompts/filing_analyst/system.md` | 34 |
| Analista de Notícias | `prompts/news_analyst/system.md` | 31 |

### Ausentes (3) — referenciados em `agents/_config.py` mas não existem no disco
| Agente | Caminho esperado |
|---|---|
| Fundamentalist Analyst | `prompts/fundamentalist/system.md` |
| Risk Director | `prompts/risk_director/system.md` |
| Research Coordinator | `prompts/coordinator/system.md` |

---

## 8. Infraestrutura

### docker-compose.yml (6 serviços)
| Serviço | Imagem | Portas | Uso |
|---|---|---|---|
| postgres | pgvector/pgvector:pg17 | 5432 | PostgreSQL + pgvector |
| minio | minio/minio:latest | 9000, 9001 | Object storage S3 |
| temporal | temporalio/auto-setup:latest | 7233 | Orquestração |
| temporal-ui | temporalio/ui:latest | 8081 | UI Temporal |
| mlflow | ghcr.io/mlflow/mlflow:v2.17.0 | 5000 | Experiment tracking |
| otel-collector | otel/opentelemetry-collector-contrib | 4317, 4318 | Telemetria |

### Dockerfile
- Multi-stage build: `python:3.12-slim`
- Non-root user: `appuser`
- Porta: 8000

### CI/CD
**Nenhum configurado.** Sem `.github/`, `.gitlab-ci.yml`, `Jenkinsfile`.

---

## 9. Pontos de Atenção

1. **Migrations não utilizadas** — Alembic configurado mas schema via `create_all`
2. **3 prompts ausentes** — Agentes referenciam arquivos que não existem
3. **Sem CI** — Nenhum pipeline de integração contínua
4. **`docs/books/`** — PDF licenciado requer verificação de conformidade
5. **`database/models/` extenso** — 50+ modelos em 17 arquivos, convenções mistas
6. **`evaluation/` sem testes** — Módulo não integrado à API
7. **`domain/` stub** — Implementações mínimas (198 linhas total)
