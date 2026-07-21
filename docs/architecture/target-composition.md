# Composição técnica alvo

## Regra principal

O repositório deve possuir **um único namespace de produção**: `ia_investing`.
`apps` contém somente entrypoints finos. Nenhum entrypoint deve importar diretamente
os antigos pacotes raiz `database`, `workflows`, `agents`, `connectors`, `portfolio`
ou `domain`.

```text
apps/api -> ia_investing.application + ia_investing.platform
apps/worker -> ia_investing.orchestration
apps/cli -> ia_investing.application
web -> OpenAPI v1
```

## API

A aplicação deve ser criada por uma factory:

```text
create_app(settings)
  -> setup_logging
  -> setup_telemetry
  -> setup_exception_handlers
  -> setup_authentication
  -> setup_authorization
  -> register_v1_routers
  -> register_readiness/liveness
```

Requisitos:

- OIDC obrigatório fora de teste.
- `organization_id`, `actor_id` e `correlation_id` no contexto da requisição.
- Commands longos retornam `202 Accepted` e um `operation_id`.
- Idempotency-Key em commands.
- Audit event para toda mutação.
- Não executar agents, backtests, risco ou otimização dentro do request.

## Workers Temporal

Um processo por capacidade, com menor privilégio:

```text
data-ingestion
  workflows: SourceIngestion, FilingPublished, MarketClose
  activities: discover, download, persist_raw, parse, validate, promote

document-processing
  workflows: DocumentProcessing, EvidenceIndexing
  activities: extract_pages, parse_tables, chunk, embed, index

research-agents
  workflows: ResearchCase, ThesisReview, NewsEvent, PolicyEvent
  activities: retrieve_context, run_agent, validate_claims, persist_assessment

portfolio-risk
  workflows: PortfolioConstruction, RiskAssessment, Backtest, Rebalance
  activities: build_snapshot, calculate, optimize, stress, persist_proposal

notifications
  workflows: NotificationDispatch
  activities: email, webhook, in_app
```

Cada registry deve declarar explicitamente `workflows` e `activities`. O worker deve
falhar na inicialização se o registry estiver vazio.

## Temporal Schedules

Remover o loop em memória. Provisionar schedules idempotentemente:

- `cvm-discovery`: 20 minutos, overlap `SKIP`.
- `news-monitoring`: 15 minutos, overlap `SKIP`.
- `policy-monitoring`: 30 minutos, overlap `SKIP`.
- `macro-refresh`: diário, overlap `BUFFER_ONE`.
- `market-close`: calendário de negociação, overlap `CANCEL_OTHER` apenas com política explícita.
- `daily-reconciliation`: após fechamento.
- `weekly-opportunity-screen`: semanal.
- `weekly-committee-pack`: semanal.
- `daily-data-quality`: diário.

Registrar schedule ID, versão de especificação e última reconciliação.

## Dados sintéticos

Dados sintéticos só podem existir em:

```text
tests/fixtures
examples
seed de ambiente demo
```

Se um dataset sintético precisar estar no pacote para demonstração, ele deve ter:

```text
origin = synthetic
production_eligible = false
calibration_status = uncalibrated
```

A readiness de produção deve falhar se qualquer modelo decisório depender somente
de dados sintéticos.

## Migração de namespaces

1. Restaurar CI em modo informativo.
2. Reescrever API e worker para o namespace canônico.
3. Migrar testes/imports.
4. Rodar compile, mypy, unit, integration e E2E.
5. Excluir `src/agents` primeiro, eliminando a colisão crítica.
6. Excluir os demais pacotes legados.
7. Restringir package discovery a `ia_investing*` e `apps*`.
8. Tornar o architecture gate estrito.
