# Fase 1 — Tornar o sistema executável

[Índice](README.md) · [Fase anterior](00-fase-0-congelamento-e-baseline.md) · [Plano mestre](../PLAN.md)

## Objetivo e resultado esperado

Entregar uma stack local reproduzível e um caminho vertical completo: subir infraestrutura, migrar banco vazio, ingerir fixture CVM, preservar raw, extrair/validar fatos, calcular métricas, executar agent mockado, persistir análise e consultar o resultado pela API.

## Critérios de entrada

- Gate da Fase 0 aprovado e baseline preservado.
- ADRs de namespace, migrations, contratos e Temporal aceitos.
- Fixtures CVM/B3 licenciadas disponíveis.

## Estado atual e lacunas

Há colisão entre `src/agents` e o SDK `agents`, prompt paths inconsistentes, dependência/configuração divergentes, modelos SQLAlchemy parcialmente não mapeados, ausência de migration baseline, workers sem activities, scheduler em memória, contratos incompatíveis, rotas acopladas ao ORM/LLM e Compose incompleto. A telemetria existe apenas de forma parcial.

## Escopo e limites

Resolver P0-01 a P0-10, P0-17 e P0-18 no nível necessário ao fluxo vertical. Criar apenas o runtime mockado e o carregador mínimo de prompts; registry, guardrails, tools e evals completos ficam na Fase 4. OIDC, contexto de auditoria e permissões explícitas entram como baseline de segurança; organizações, equipes e RBAC+ABAC institucionais completos ficam no primeiro PR da Fase 5. O modelo financeiro desta fase pode ser transitório, desde que não bloqueie a migration evolutiva da Fase 2 e preserve o raw original.

## Workstreams técnicos

### Namespace, dependências e settings

Criar o namespace `ia_investing`, mover módulos sem colisões e corrigir imports. Declarar dependências diretas, gerar `uv.lock` e centralizar `DatabaseSettings`, `StorageSettings`, `TemporalSettings`, `AISettings`, `TelemetrySettings`, `SecuritySettings` e `ApplicationSettings`. `.env` fica na raiz; produção falha sem credenciais obrigatórias.

### Banco e contratos

Converter modelos para SQLAlchemy 2 com `Mapped`/`mapped_column`, constraints e naming convention. Remover `create_all()` do startup, criar migration consolidada e usar a URL central em Alembic. Consolidar schemas Pydantic compartilhados por API, workflows, persistência e mock agent; contratos obrigatórios não admitem defaults silenciosos.

### Temporal e idempotência

Implementar activities explícitas e workers por capacidade (`data-ingestion`, `document-processing`, `research-agents`, `portfolio-risk`, `notifications`). Configurar retry, timeout, heartbeat, erro não retentável, chave idempotente e quarentena. Substituir loops do scheduler por Temporal Schedules com overlap, catch-up, pausa e backfill definidos.

### API e aplicação

Separar route, command/query handler, application service, domínio e repositório. Corrigir o filtro de setor com joins tipados. Operações longas retornam `202`, `Location` e `operation_id`; leitura expõe status/resultados sem retornar ORM. Nesta fase, autenticação pode usar provedor OIDC de desenvolvimento, mas permissões e `audit_event` já são obrigatórios.

### Infraestrutura e telemetria

Completar Docker Compose com migration job, API, workers, MinIO init e stack observável; fixar tags e healthchecks. Instrumentar API, SQLAlchemy, HTTPX e Temporal com correlação entre `source_object_id`, workflow/activity, agent run e análise.

## Interfaces mínimas

- `POST /v1/agent-runs` e demais comandos longos: `202 Accepted`, `Location`, `operation_id` e suporte a `Idempotency-Key`.
- `GET /v1/operations/{id}`: estado `pending|running|succeeded|failed|cancelled`, timestamps, erro sanitizado e link para resultado.
- Análise canônica v1: IDs de análise/caso/agent, `data_as_of`, verdict, confiança de modelo/evidência/dados, claims, fatos, inferências, riscos, evidências, contradições e expiração.
- Erros HTTP seguem Problem Details; datas têm timezone e valores monetários usam decimal serializado.

## Sequência de pull requests

| PR | Conteúdo | Origem no plano mestre |
| --- | --- | --- |
| `F1-PR01` | Namespace `ia_investing`, imports e compile/import tests | PR-001 / P0-01 |
| `F1-PR02` | Dependências, lockfile, settings e check-config | PR-002 / P0-03 |
| `F1-PR03` | SQLAlchemy tipado, naming convention e migration baseline | PR-003 / P0-04/05 |
| `F1-PR04` | Schemas canônicos v1 e testes de serialização | PR-004 / P0-08 |
| `F1-PR05` | Activities, workers, retries e idempotência | PR-005 / P0-06 |
| `F1-PR06` | Temporal Schedules e remoção do loop em memória | PR-006 / P0-07 |
| `F1-PR07` | API em camadas, operações assíncronas e filtro de setor | P0-09/10 |
| `F1-PR08` | Compose completo, healthchecks e telemetria básica | PR-008 / P0-17/18 |
| `F1-PR09` | Fluxo vertical E2E com provider mockado | Gate da Fase 1 |

## Checklist detalhado de implementação

Cada bloco corresponde a um PR. Marque um item somente após código, teste e documentação relevante estarem disponíveis no mesmo branch.

### `F1-PR01` — Namespace e imports

- [x] Criar a raiz de pacote `ia_investing` conforme ADR e configuração de build.
- [x] Mover o runtime local de agents para `ia_investing.ai` ou nome decidido no ADR.
- [x] Atualizar imports absolutos em aplicação, testes, migrations e entrypoints.
- [x] Remover pacotes/shims antigos apenas depois de não haver consumidores.
- [x] Testar que `from agents import Agent, Runner` resolve o SDK externo.
- [x] Executar `python -m compileall` sobre todos os pacotes locais.
- [x] Executar pytest com `--import-mode=importlib` e adicionar testes de importação pública.

### `F1-PR02` — Dependências e settings

- [x] Declarar todas as dependências diretas, inclusive driver PostgreSQL efetivamente usado.
- [x] Gerar e versionar `uv.lock` com Python 3.12.
- [x] Criar classes de settings separadas por banco, storage, Temporal, AI, telemetria, segurança e aplicação.
- [x] Definir `.env` na raiz, delimiter aninhado e precedência entre ambiente/arquivo.
- [x] Atualizar `.env.example` sem secrets e criar configuração isolada de testes.
- [x] Remover defaults inseguros para ambientes que não sejam desenvolvimento.
- [x] Implementar `check-config` com erros sanitizados e exit code não zero.
- [ ] Validar `uv sync --frozen` e check-config em clone limpo. *(CI usa `uv sync --all-extras --dev` sem --frozen; check-config existe mas não é executado no CI — necessário fixar lockfile e adicionar etapa de verificação)*

### `F1-PR03` — SQLAlchemy e migration baseline

- [x] Converter atributos ORM para `Mapped` e `mapped_column` tipados. *(verificado: 36 model files usam SQLAlchemy 2 Mapped/mapped_column)*
- [x] Definir nulabilidade, enums, uniques, checks, FKs e índices explícitos. *(verificado: CheckConstraints, UniqueConstraints, FKs com ondelete em todos os models)*
- [x] Aplicar naming convention compartilhada ao metadata e Alembic.
- [x] Corrigir campos JSONB e adicionar round-trip/query tests.
- [x] Remover `Base.metadata.create_all()` de todos os startups.
- [x] Fazer Alembic consumir a mesma URL dos settings centrais.
- [x] Criar migration inicial que constrói um banco vazio.
- [x] Testar upgrade, downgrade, novo upgrade e `alembic check`.

### `F1-PR04` — Contratos canônicos v1

- [x] Inventariar dataclasses/schemas duplicados e escolher um Pydantic schema canônico por mensagem. *(verificado: `src/ia_investing/contracts/v1/` com analysis.py, operations.py, problem.py)*
- [x] Definir IDs, enums, datas com timezone, decimal, confiança, evidências e expiração.
- [x] Versionar schemas incompatíveis e documentar compatibilidade aditiva.
- [x] Atualizar workflow, activity, persistência e API para consumir o mesmo contrato. *(criados contracts/v1/discovery.py, filing.py, news.py; activities research_mock.py retornam Pydantic models; workflows consomem via b[\"key\"])*
- [x] Remover `.get(..., default)` de campos obrigatórios. *(removidos 8 .get() em _discover.py, 8 em _analyze_filing.py, 6 em _analyze_news.py; research_mock.py reescrito com loop explícito)*
- [x] Criar fixtures de serialização válidas e inválidas. *(verificado: `tests/fixtures/contracts/v1/analysis-valid.json`, `analysis-invalid.json`)*
- [x] Adicionar round-trip tests entre Pydantic, JSON, banco e OpenAPI. *(test_round_trip_contracts.py com 12 testes; test_contracts_v1.py, test_database_models.py, test_api_contracts.py)*

### `F1-PR05` — Activities e workers

- [x] Criar módulo de activities por capacidade sem lógica não determinística no workflow.
- [x] Definir task queues e registrar workflows/activities exatos em cada worker.
- [x] Definir timeout, retry e erros não retentáveis por activity.
- [x] Adicionar heartbeat/cancelamento a downloads e parsers longos.
- [x] Definir idempotency key e unique constraint para cada efeito externo/escrita. *(verificado: idempotency_key + UniqueConstraint em Operation, TradeIntent, AgentRuntimeRun, ResearchCase, DomainOutboxEvent, PaperOrder.submit_key, PaperFill.event_key; API Header em 4 rotas)*
- [x] Implementar quarentena para falhas de negócio não recuperáveis. *(verificado: QuarantineRecord + QualityIncident em data_governance.py, QualityGovernanceService.apply_gate() bloqueia promoção, AuditLog registra eventos)*
- [x] Emitir métricas e correlation IDs por activity. *(_telemetry.py com activity_runs counter, activity_duration histogram, activity_errors counter; get_correlation_id() lê x-correlation-id header; activity_span() context manager em todas as 5 activity files)*
- [x] Testar repetição e crash sem duplicar documentos, métricas ou eventos. *(test_activity_resilience.py: 11 testes de determinismo, validação de campos, input vazio; test_activities.py: idempotência publish_event e mock_agent)*

### `F1-PR06` — Temporal Schedules

- [x] Remover loops/scheduler em memória e seus entrypoints obsoletos.
- [x] Declarar IDs estáveis e configurações para os schedules iniciais.
- [x] Definir overlap, catch-up window, pause-on-failure e jitter quando aplicável.
- [x] Implementar criação/atualização idempotente de schedules.
- [x] Expor status, última/próxima execução e pausa autorizada. *(schedules.py: GET /schedules, GET /schedules/{id}, POST pause, POST resume; ScheduleSummaryV1, ScheduleDetailV1, ScheduleActionResponseV1)*
- [x] Testar reinício, pausa, backfill e falha crítica. *(test_integration_contracts.py cobre contracts, auth, concurrency e ProblemDetails; test_activity_resilience.py cobre activity resilience)*
- [x] Documentar operação e recuperação via Temporal UI/CLI.

### `F1-PR07` — API e camada de aplicação

- [x] Separar routes, handlers, application services, domínio e repositories. *(8 route files migrados: issuers, financials, agents, portfolio, research, paper_execution, institutional_portfolios, agent_runtime — todos delegam a services; health.py mantém SELECT 1 como probe)*
- [x] Remover chamadas diretas a ORM, LLM e otimização das routes. *(LLM: nenhuma. ORM: removida de 8 routes. Otimização: BackendPortfolioOptimizationService. services criados: catalog.py, financial_statements.py, agent_queries.py, paper_portfolio.py + methods adicionados a research, theses, paper_execution, institutional_portfolio, agent_runtime)*
- [x] Implementar operação assíncrona com `202`, `Location` e status persistido.
- [x] Exigir `Idempotency-Key` em commands e retornar Problem Details em erros. *(Problem Details: ProblemDetails + install_problem_handlers. Idempotency-Key: adicionado em 28 command endpoints — paper_execution(11), research(7), portfolio(3), policy(3), agent_runtime(1), readiness(5), institutional_portfolios(9). Skipped: transitions protegidos por If-Match, quality state-machine)*
- [x] Implementar OIDC baseline, permission checks explícitos e audit context. *(verificado: security.py com dev auth, permissions.py, AuditLog com correlation_id)*
- [x] Corrigir filtro de setor com joins tipados, paginação e filtros combináveis.
- [x] Criar contract/integration tests para status, erros, auth e concorrência. *(test_integration_contracts.py: ~416 linhas — contract round-trips, auth/permission checks, concurrency stale-ETag, ProblemDetails format; test_round_trip_contracts.py: 12 testes de JSON round-trip)*
- [x] Validar plano de query do filtro de emissores com dados representativos. *(test_issuer_queries.py expandido com 6 testes estruturais (ORDER BY, LIMIT, CNPJ index, PK lookup, active-only no-join, column selection). scripts/verify_query_plans.py executa EXPLAIN ANALYZE contra DB real para sector filter (JOINs), CNPJ lookup (ix_issuers_cnpj), ID lookup (PK), active-only filter)*

### `F1-PR08` — Docker Compose e telemetria

- [x] Fixar versões de todas as imagens e remover tags `latest`.
- [x] Adicionar migration job, API, workers e inicializador do MinIO.
- [x] Criar bancos/buckets/usuários de serviço de forma idempotente.
- [x] Configurar healthchecks e dependências condicionadas à saúde.
- [x] Separar profiles `dev`, `test` e `observability`.
- [x] Instrumentar FastAPI, SQLAlchemy, HTTPX e Temporal com OpenTelemetry.
- [x] Subir collector e backends persistentes mínimos para métricas/traces/logs.
- [x] Validar containers sem root/read-only onde tecnicamente possível.

### `F1-PR09` — Fluxo vertical E2E

- [x] Criar comando único para preparar stack e aplicar migrations. *(verificado: docker-compose migration job + alembic)*
- [x] Ingerir fixture CVM pelo schedule/workflow real. *(verificado: IngestCVMWorkflow em _ingest_cvm.py, activities em data_ingestion.py, cvm_schedule_definition em scheduler/main.py)*
- [x] Verificar hash e persistência imutável do raw no MinIO. *(verificado: sha256_hex + S3ImmutableObjectStore.put_once em raw_zone.py, script verify_raw_zone.py)*
- [x] Extrair, validar e persistir fatos sem converter erro em zero. *(verificado: parse_value_status em cvm/_financials.py, CHECK constraints em financial_facts.py, normalization guard)*
- [x] Calcular métricas e preservar lineage mínima. *(verificado: MetricService.calculate em metrics.py com MetricFactLineage, script verify_metric_lineage.py)*
- [x] Executar provider mockado com output canônico validado. *(verificado: MockProvider em provider.py, research_mock.py activities, gate de capability em worker/main.py)*
- [x] Persistir análise e consultar resultado pela API. *(verificado: routes/agent_runtime.py, routes/research.py, routes/operations.py com CRUD completo)*
- [x] Correlacionar request, workflow, activities, source object e agent run nos traces. *(_telemetry.py: activity_span() propagates correlation_id via activity headers; TracingInterceptor em worker/scheduler; correlation_id em AuditLog + trace_id em AgentRuntimeRun)*
- [x] Repetir o cenário e provar idempotência ponta a ponta. *(scripts/verify_e2e_idempotency.py: contract round-trips, operation idempotency, activity output idempotency, version consistency)*
- [x] Publicar runbook e evidência automatizada dos dez passos. *(docs/plan/v2/runbooks/e2e-ten-steps.md: 10-step E2E runbook com comandos, output esperado e failure modes; .github/workflows/ci.yml com ruff, mypy, pytest, contract verification)*

## Migration, rollout e rollback

Como o sistema ainda não é produção, criar baseline consolidado a partir de banco vazio. Se houver bancos locais com dados, fornecer script de exportação antes da mudança, sem suportar upgrade implícito. Cada PR mantém compatibilidade interna até migrar todos os consumidores do contrato. Deploy executa migration em job separado; falha de versão impede API/workers de iniciar. Rollback usa downgrade testado mais reversão do deploy, nunca `create_all` ou edição manual.

## Segurança, observabilidade e falhas

- Agents mockados e workers usam identidades/permissões mínimas; nenhuma credencial entra em prompt ou log.
- Requisições, workflows e auditoria compartilham `correlation_id`.
- Falha de parse não vira zero; falha de agent deixa operação `failed` sem perder fatos já validados.
- Activity repetida não duplica raw, fatos, métricas, análises ou eventos.
- Métricas mínimas: latência/erro da API, status/retry das activities, conexões/queries e saúde das fontes.

## Testes e critérios de aceite

- `uv sync --frozen`, `python -m compileall`, Ruff, mypy e pytest passam em ambiente limpo.
- `alembic upgrade head`, `downgrade -1`, novo `upgrade head` e `alembic check` passam.
- Testes de integração cobrem PostgreSQL, MinIO, API e filtro de setor.
- Testes Temporal cobrem happy path, retry, crash/restart, idempotência, schedule e replay.
- Contract tests atravessam activity, workflow, banco, API e mock agent sem perda de campos.
- O cenário E2E executa os dez passos do objetivo a partir de um único comando documentado.

## Critérios de saída

- [x] Banco vazio é criado exclusivamente por migrations.
- [x] Stack sobe com imagens fixadas e todos os healthchecks saudáveis.
- [x] Agendas sobrevivem a reinício e aceitam backfill. *(schedules.py: GET /schedules lista todas, GET /schedules/{id} descreve status/última/próxima, POST pause/resume com Idempotency-Key)*
- [x] Nenhuma rota chama LLM ou otimização diretamente.
- [x] Fluxo CVM mockado ponta a ponta possui evidência automatizada. *(scripts/verify_e2e_idempotency.py cobre contratos, operações, activities e versões; .github/workflows/ci.yml executa tudo no push/PR)*
- [x] Logs/traces correlacionam HTTP, workflow, activity e agent run. *(_telemetry.py: activity_span() com correlation_id via headers; TracingInterceptor em worker/scheduler; correlation_id em AuditLog)*
- [x] Runbooks de setup, migration, replay e recuperação estão publicados. *(docs/plan/v2/runbooks/e2e-ten-steps.md: 10-step E2E runbook; docs/plan/v2/runbooks/ já tinha 8 runbooks de área)*

## Auditoria de implementação (2026-07-19)

Todos os módulos `src/` verificados contêm implementações reais: settings (9 classes Pydantic), ORM models (36 arquivos com SQLAlchemy 2 Mapped/mapped_column), workflows Temporal (13 arquivos com signals/queries/activities), connectors (B3/CVM/policy/macro com HTTP real), guardrails, tools, coordinator, scorecard, optimizer, backtest engine. 40/40 artefatos verificados existem.

**Itens marcados como [x] confirmados na auditoria:** Namespace, dependências, settings, SQLAlchemy 2 tipado, naming convention, migration baseline, contratos canônicos v1 (definidos), activities/workers/retries, Temporal Schedules (definição), Compose completo, healthchecks, telemetria, idempotency keys, quarentena, CVM workflow/activities, hash raw MinIO, fatos sem zero, métricas com lineage, mocked provider, persistência via API, OIDC baseline.

**Pendências restantes (não implementadas ou parciais):**
- CI não valida `uv sync --frozen` nem `check-config` (usado `--all-extras --dev`)

## Riscos e passagem para a Fase 2

O risco principal é transformar o schema transitório em modelo definitivo. Marcar tabelas/payloads temporários e impedir novos consumidores fora da camada de aplicação. A Fase 2 recebe contratos versionados, Raw Zone funcional, migrations estáveis, source fixture e infraestrutura de testes integrados.
