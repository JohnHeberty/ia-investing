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
- [ ] Validar `uv sync --frozen` e check-config em clone limpo.

### `F1-PR03` — SQLAlchemy e migration baseline

- [ ] Converter atributos ORM para `Mapped` e `mapped_column` tipados.
- [ ] Definir nulabilidade, enums, uniques, checks, FKs e índices explícitos.
- [x] Aplicar naming convention compartilhada ao metadata e Alembic.
- [x] Corrigir campos JSONB e adicionar round-trip/query tests.
- [x] Remover `Base.metadata.create_all()` de todos os startups.
- [x] Fazer Alembic consumir a mesma URL dos settings centrais.
- [x] Criar migration inicial que constrói um banco vazio.
- [x] Testar upgrade, downgrade, novo upgrade e `alembic check`.

### `F1-PR04` — Contratos canônicos v1

- [ ] Inventariar dataclasses/schemas duplicados e escolher um Pydantic schema canônico por mensagem.
- [x] Definir IDs, enums, datas com timezone, decimal, confiança, evidências e expiração.
- [x] Versionar schemas incompatíveis e documentar compatibilidade aditiva.
- [ ] Atualizar workflow, activity, persistência e API para consumir o mesmo contrato.
- [ ] Remover `.get(..., default)` de campos obrigatórios.
- [x] Criar fixtures de serialização válidas e inválidas.
- [ ] Adicionar round-trip tests entre Pydantic, JSON, banco e OpenAPI.

### `F1-PR05` — Activities e workers

- [x] Criar módulo de activities por capacidade sem lógica não determinística no workflow.
- [x] Definir task queues e registrar workflows/activities exatos em cada worker.
- [x] Definir timeout, retry e erros não retentáveis por activity.
- [x] Adicionar heartbeat/cancelamento a downloads e parsers longos.
- [ ] Definir idempotency key e unique constraint para cada efeito externo/escrita.
- [ ] Implementar quarentena para falhas de negócio não recuperáveis.
- [ ] Emitir métricas e correlation IDs por activity.
- [ ] Testar repetição e crash sem duplicar documentos, métricas ou eventos.

### `F1-PR06` — Temporal Schedules

- [x] Remover loops/scheduler em memória e seus entrypoints obsoletos.
- [x] Declarar IDs estáveis e configurações para os schedules iniciais.
- [x] Definir overlap, catch-up window, pause-on-failure e jitter quando aplicável.
- [x] Implementar criação/atualização idempotente de schedules.
- [ ] Expor status, última/próxima execução e pausa autorizada.
- [ ] Testar reinício, pausa, backfill e falha crítica.
- [x] Documentar operação e recuperação via Temporal UI/CLI.

### `F1-PR07` — API e camada de aplicação

- [ ] Separar routes, handlers, application services, domínio e repositories.
- [ ] Remover chamadas diretas a ORM, LLM e otimização das routes.
- [x] Implementar operação assíncrona com `202`, `Location` e status persistido.
- [ ] Exigir `Idempotency-Key` em commands e retornar Problem Details em erros.
- [x] Implementar OIDC baseline, permission checks explícitos e audit context.
- [x] Corrigir filtro de setor com joins tipados, paginação e filtros combináveis.
- [ ] Criar contract/integration tests para status, erros, auth e concorrência.
- [ ] Validar plano de query do filtro de emissores com dados representativos.

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

- [x] Criar comando único para preparar stack e aplicar migrations.
- [ ] Ingerir fixture CVM pelo schedule/workflow real.
- [ ] Verificar hash e persistência imutável do raw no MinIO.
- [ ] Extrair, validar e persistir fatos sem converter erro em zero.
- [ ] Calcular métricas e preservar lineage mínima.
- [ ] Executar provider mockado com output canônico validado.
- [ ] Persistir análise e consultar resultado pela API.
- [ ] Correlacionar request, workflow, activities, source object e agent run nos traces.
- [ ] Repetir o cenário e provar idempotência ponta a ponta.
- [ ] Publicar runbook e evidência automatizada dos dez passos.

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
- [ ] Agendas sobrevivem a reinício e aceitam backfill.
- [x] Nenhuma rota chama LLM ou otimização diretamente.
- [ ] Fluxo CVM mockado ponta a ponta possui evidência automatizada.
- [ ] Logs/traces correlacionam HTTP, workflow, activity e agent run.
- [ ] Runbooks de setup, migration, replay e recuperação estão publicados.

## Riscos e passagem para a Fase 2

O risco principal é transformar o schema transitório em modelo definitivo. Marcar tabelas/payloads temporários e impedir novos consumidores fora da camada de aplicação. A Fase 2 recebe contratos versionados, Raw Zone funcional, migrations estáveis, source fixture e infraestrutura de testes integrados.
