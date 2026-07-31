# Session Log — IA Investing

## Como usar
- Leia este arquivo no início de cada sessão para contexto
- Ao finalizar, registre o que foi feito, o que funcionou/errou
- Mantenha janela de ~24h (remova entradas antigas)
- Pendências são checklist — marque conforme resolver

---

## 2026-07-24 (00h UTC)

### Foco: Code review geral + plugins opencode + QUALITY cleanup

**Feito:**
- Code review completa do projeto (5 agents paralelos): 34 críticos, 62+ major, 29+ minor
- Corrigido: OIDC auth (state/PKCE/JWT/httponly/timeout), idempotência tenant-scoped, float("inf")→None, N+1 batch, audit hash race, rate limiter isolado, CSRF timing fix, return_to whitelist
- Corrigido: computeDataState retornava "stale" p/ dados frescos (bug introduzido na correção anterior)
- Corrigido: audit_service.py verify_chain ainda usava timestamp.asc() (inconsistente)
- Corrigido: metadata→meta_data em audit_service.py, UUIDv4 ordering, flush antes de hash
- Corrigido: operations.py org_id param ignorado, CancelledError, crash window
- Corrigido: rate_limit.py int→ceil, prune stale keys, X-Forwarded-For validation
- Corrigido: candidate-api.ts 204 No Content handling
- Corrigido: oidc.ts timeout 30s, clear cookies on failure, atob UTF-8 corruption, variable shadow
- Corrigido: useUrlState reference equality bug, use-sse JSON.parse sem try/catch
- Corrigido: evidence-tags.tsx "use client"; proxy.ts dead file; login page open redirect
- Corrigido: computeDataState arity errada em 4 hooks (quality-incidents, committee, audit, backtests)
- web/src/lib/ criado (7 módulos: api-client, api-schema, api, data-state, oidc, sse, candidate-api)
- page.test.tsx corrigido (imports quebrados)
- package.json: "latest" pinned para versões concretas
- test_round_trip_contracts.py deletado (duplicata)
- .dockerignore: node_modules adicionado
- QUALITY/ removido (commit 0a0be0b)
- 3 plugins opencode instalados: opencode-mem (✅), tokenscope (✅), opencode-notify (❌ removido)
- MEMORY.md + AGENTS.md atualizados

**OK:**
- ruff 0 errors, mypy 0 errors (conforme FIX/File.md — verificado antes do ambiente perder uv)
- Tokenscope funcional (22.7M tokens, 18 subagentes)
- opencode-mem funcional (memory add/search/profile/list/forget)
- OIDC auth testado sintaticamente (todos os arquivos compilam)

**Erros:**
- opencode-notify: instalou no cache mas não carregou (removido do config)
- uv/bun/npm não disponíveis no ambiente shell para re-verificar pipeline

---

## 2026-07-24 (Sessão 3 — Permissões Frontend)

### Foco: Implementar sistema de permissões no frontend

**Feito:**
- **Backend:** `UserInfo.permissions` adicionado ao modelo e endpoint `/me` — session JWT já continha permissions, só estava oculto
- **Frontend:** `auth-provider.tsx` — tipo `UserInfo` ganhou campo `permissions: string[]`
- **Frontend:** `use-permissions.ts` — novo hook com `can()`, `canAny()`, `canAll()`, `isAdmin`, `role`
- **Frontend:** `can.tsx` — novos componentes `<Can permission="...">` e `<CanAny permissions={[...]}>` com suporte a fallback
- **Frontend:** `app-shell.tsx` — sidebar filtra itens por permissão; identidade do usuário no rodapé (nome + roles); botão Sair
- **Frontend:** `opportunities/page.tsx` — mock `usePermissions` removido, importa hook real; `canCreateCase = can("research_cases:create")`
- **Cleanup:** `proxy.ts` + `proxy.test.ts` deletados (substituídos por `middleware.ts`)

**Mapeamento sidebar:**
| Item | Permission |
|---|---|
| Carteiras | `portfolio:read` |
| Oportunidades | `research_cases:read` |
| Comitê | `committee:*` |
| Política | `policy:read` |
| Macro | `macro:read` |
| Paper | `portfolio:read` |
| Rebalance | `rebalance:*` |
| Agents | `agent_runs:read` |
| Qualidade | `quality_incidents:manage` |
| Auditoria | `audit:read` |
| Missão, Candidatos, Exploração, Risco, Backtests | público (null) |

**OK:** Ruff passou (backend). Pacote de permissões frontend autocontido.

---

## 2026-07-24 (Sessão 2 — Config .opencode)

### Foco: Alinhar .opencode/ com referência (plugins, skills, MCPs, comandos)

**Feito:**
- Removidas 12 skills custom antigas (acessibilidade, ui-visual, forms, fastapi, python-pro, etc)
- Instaladas 24 skills do addyosmani/agent-skills (via `git clone https://github.com/addyosmani/agent-skills.git`)
- plugins: removido version pin (`opencode-websearch-cited@1.2.0` → `opencode-websearch-cited`)
- plugins: adicionado `opencode-mem` e `@ramtinj95/opencode-tokenscope` explicitamente no projeto (já estavam no global, agora visíveis no project config)
- MCPs: removidos `serena` e `protheus` (mantido só `repomix` + `context7`)
- Comandos: adicionados `/build`, `/lint`, `/test`, `/typecheck`, `/tokenscope`
- `ui-designer.md` agent atualizado para referenciar skills do addyosmani

**OK:** Config validada — 5 plugins, 2 MCPs, 5 commands, 24 skills, sem erros de schema

---

## Pendências Abertas

### Resolvidos em 2026-07-24

**Commit `fc9d701` — 5 backend bugs:**
- [x] #1 source_registry.py — TOCTOU → upsert atômico com `pg_insert`
- [x] #2 portfolio_ranking_materializer.py — UPSERT RETURNING corrigido
- [x] #3 research.py — DoS max limit + UUID pagination
- [x] #4 research_mock.py — float(None) crash guard
- [x] #5 portfolio_models.py — organization_id FK + migration + routes

**Commit `5ade584` — 9 quick fixes:**
- [x] #6 use-risk-assessments → use-source-health-summary (rename)
- [x] #7 seed-eval-datasets CLI entrypoint (pyproject.toml + cli.py)
- [x] #10 OIDC/auth route tests — 38 novos testes backend
- [x] #11 Frontend vitest — 3 novos arquivos (useSourceHealthSummary, usePermissions, Can)
- [x] #12 MinIO vars em .env.example
- [x] #13 migrations/env.py sys.path dedup guard
- [x] #14 AGENTS.md cross-reference raiz→web

### Pendências de FIX/File.md (consolidadas aqui)

- [x] Permissões frontend — implementado (hook + Can + sidebar filtrado + logout)
- [x] Evals source discovery — datasets criados + seed CLI entrypoint
- [x] R7-M1: CSRF via BFF (commit `2e3a129`)
- [x] R7-M2: JWT signature verify — jose npm + PyJWT (commit `f715968`)
- [x] R7-M3: CNPJ mask (commit `55c624d`)
- [x] R7-M7: API patterns standardization — 13 route files (commit `d2e6743`)
- [x] R9-1: .env — not applicable (never committed)
- [x] Tarefa 7: StrategyMandate JSONB — 28→11 columns (commit `fc5b68c`)
- [x] R5-15..R5-22: DB duplications — all pre-resolved
- [x] R8: Testes — all 66 failures fixed, 1129 passed (commit `08728c6`)

### Feature/Infra (não bugs — precisam de escopo)

- [ ] Mission Control candidatos — frontend
- [ ] Observabilidade — dashboards Grafana/MLflow
- [ ] Conectores avançados — sitemap/RSS/institutional site resolvers

---

## 2026-07-26 (Sessão — Fix flush order em test_candidate_scenarios.py)

### Foco: Corrigir `IntegrityError: foreign key constraint violation` em `candidate_analysis_runs.candidate_id`

**Problema:** Testes de integração em `test_candidate_scenarios.py` falhavam com `IntegrityError` porque SQLAlchemy emitia `INSERT INTO candidate_analysis_runs` ANTES de `INSERT INTO investment_candidates`, violando FK constraint.

**Causa raiz:**
- SQLAlchemy Unit of Work não emitia INSERT do pai (`InvestmentCandidateRecord`) mesmo estando em `session.new`
- Não havia `relationship()` explícita entre modelos — só FK column em `candidate_id`
- `session.flush([objects])` com ordenação manual era ignorado pelo UoW
- `engine.dispose()` no fixture causava `RuntimeError: Event loop is closed` entre testes
- Tickers hardcodados (`SCEN4`, `EXPL4`) causavam `ExclusionViolationError` em runs repetidos

**Correções aplicadas:**

1. **`src/database/models/investment_candidates.py`** — Adicionadas `relationship()` explícitas:
   - `InvestmentCandidateRecord.analysis_runs` → `CandidateAnalysisRunRecord`
   - `InvestmentCandidateRecord.candidate_sources` → `CandidateSourceRecord`
   - `InvestmentCandidateRecord.candidate_gaps` → `CandidateGapRecord`
   - `InvestmentCandidateRecord.candidate_events` → `CandidateEventRecord`
   - Todos com `back_populates` nos filhos

2. **`tests/integration/test_candidate_scenarios.py`** — Tickers únicos por run:
   - `_make_issuer_instrument_listing()` agora usa `ticker=f"SCEN{uuid4().hex[:4].upper()}"`
   - `_make_candidate()` aceita `ticker` via `**kw` em vez de valor hardcodado
   - Cenário A: flush/commit moved para escopo correto
   - Cenário B: mock HTTP response atualizado com CNPJ real + ticker do candidato
   - Cenário B: resolução manual de gaps para `investor_relations_missing` e `cvm_filings_missing`

3. **`tests/integration/conftest.py`** — Engine fixture:
   - Removido `_engine` global com caching (session-scoped)
   - Engine agora function-scoped: `@pytest_asyncio.fixture`
   - `pool_pre_ping=True` adicionado
   - Pool size reduzido para 2 (testes isolados)

4. **`pyproject.toml`** — pytest-asyncio config:
   - Adicionado `asyncio_default_fixture_loop_scope = "session"`

**Resultado (2026-07-26):**
- ✅ `test_scenario_a_full_flow` — PASS (era FAIL com IntegrityError)
- ✅ `test_scenario_b_ri_missing_resolved` — PASS (era FAIL com mock incorreto + event loop)
- ✅ `test_scenario_c_risk_check_passes` — PASS
- ✅ `test_scenario_f_run_fails` — PASS
- ❌ `test_scenario_d_explorer_persists_suggestions` — FAIL (universe_size=0, dados de equity ausentes — pre-existing, não flush-related)
- ✅ 1130 unit tests — PASS (380 warnings, pre-existing)

**Limitação conhecida:**
- Cenário D requer dados de equity no banco (equity_metrics table) que não são populados pelo fixture de teste
- Engine function-scoped é mais lenta (~17s para 5 testes vs ~5s com session-scoped), mas evita event loop conflicts

---

## Sessão 2026-07-27 — Execução do plano completo (5 fases) ✅

### O que foi feito
Implementei e verifiquei todas as 5 fases do plano de refatores pós-code-review:

**Fase 1 — N+1 Queries (R2-6/7)**
- `_nav.py::publish_nav()`: Substituído loop de ~200 queries por 5 batch queries com `IN (...)`. Batch-fetch de Instruments, Listing+MarketBar (DISTINCT ON), CorporateActions. Cache de FX rates.
- `_risk.py::assess_risk()`: Substituído loop de ~50 queries por 1 batch query com ROW_NUMBER() window function (partition by instrument_id). Processamento in-memory.

**Fase 2 — Outbox Dead Letter (R6-H1)**
- Modelo `OperationDispatchDeadLetter` adicionado em `operations.py`
- State constraint expandido para incluir `'dead_letter'`
- Dispatcher escreve DLQ records em: exaustão de retry, payload inválido, unsupported topic

**Fase 3 — DB Migrations (R5-7/9/13/14)**
- FK: `agent_capabilities.active_version_id` → `agent_versions.id`
- FK: `thesis_versions.agent_run_id` → `agent_runtime_runs.id`
- Float→Numeric em Scorecard (5 cols), BacktestResult (7 cols), RiskSnapshot (3 cols)
- Migration: `20260727_01_fk_and_numeric_type_fixes.py`

**Fase 4 — Frontend Hooks (R7-5/6/7/8/10/13)**
- auth-provider: pathname removido de useEffect deps
- use-committee: batch com concurrency=5 + AbortController + Promise.allSettled
- source-drawer: focus trap + Escape key
- use-permissions: memoized com useCallback/useMemo
- app-shell: SSR-safe theme init (lazy useState)
- use-sse: seenIdsRef capped at 200

**Fase 5 — Docker/CI (R9-5/6/7/8/10/12)**
- Dockerfile: layer caching reorder + HEALTHCHECK
- web/Dockerfile: produção multi-stage
- init-databases.sh: ALTER DEFAULT PRIVILEGES
- .dockerignore: expandido
- quality.yml: pip → uv sync
- pyproject.toml: pip-audit + bandit added

### Resultado
- Todos os unit tests passam (exit 0)
- 23 arquivos modificados

### Pendente (resolvido nesta sessão)
Nada pendente — todos os itens corrigidos.

### Sessão 2026-07-27 (correções finais)
- **R5-8**: Criado modelo `SystemPrompt` + migration `20260727_02_system_prompts` + FK em `agent_definitions.system_prompt_id`
- **R2-28**: `policy.py:270` — `datetime.now(tz or None)` → `datetime.now(UTC)`
- **R2-27**: `_evaluation.py:create_post_mortem` — TOCTOU corrigido com `with_for_update=True`
- **R7-4**: `candidate-api.ts` — interface `Candidate` ganhou `rationale`, `instrument_id`, `final_decision_reason`, `approved_portfolio_eligible`
- **R7-9**: `StaleWarning` — `lastUpdated` opcional, remove `new Date().toISOString()` dos 10 callers
- **R7-11**: `portfolio-ranking-table.tsx` — Tailwind substituído por design tokens
- **R7-12**: `rebalance/page.tsx` — Tailwind substituído por CSS design tokens
- **R9-4**: `quality.yml` fundido em `ci.yml`; `quality.yml` removido
- 11 arquivos modificados no total

---

## Sessão 2026-07-28/29 — FIX.md completion ✅

### Foco: Resolver todos os itens pendentes do FIX.md

**Commits (10 total):**

| Commit | Descrição |
|--------|-----------|
| `d2e6743` | R7-M7: API patterns — 13 route files, map_error hierarchy, _context.py, contracts/v1/common.py |
| `f715968` | R7-M2: JWT verify — jose npm, PyJWT replaces python-jose |
| `fc5b68c` | Tarefa 7: StrategyMandate 18→1 JSONB (migration 20260728_07) |
| `358a28a` | FIX.md update |
| `7d0b072` | R8: Unblock 19 test files (heartbeat_timeout, DetectedBreak, stale imports) |
| `08728c6` | R8: Fix 66 test failures (FK back_populates, mock provider, stale path) |
| `e05c1bc` | FIX.md final update — all resolved |
| `c31a2f6` | Logging full-stack: structlog, LoggingMiddleware, AuditContextMiddleware, events endpoint, TelemetryProvider |
| `17e6786` | Fix: LoggingMiddleware switched to structlog, trace_id correlation, 6 tests updated |

**Fixes técnicos:**
- `_errors.py`: map_error hierarchy (404/403/409/422/500) — expanded from 3 exceptions to universal
- `_context.py`: shared context_from() — eliminated 3 duplicates
- 13 route files: response_model + consistent error handling + removed dead patterns
- `oidc.ts`: verifyJwt() with jose.jwtVerify() + remote JWKS
- `auth.py`: PyJWKClient replaces python-jose
- `investment_candidates.py`: FK + removed bidirectional back_populates (circular MANYTOONE)
- 8 `@activity.defn()`: removed invalid heartbeat_timeout_seconds

**Resultado final:**
- FIX.md: 0 items pending
- Tests: 1164 passed, 0 failed
- python-jose: removed (single JWT lib: PyJWT)

---

## Sessão: Logging Full-Stack (2026-07-29)

**Objetivo:** Rastrear tudo — clicks, requests, accesses, ações backend — salvos em arquivos, sem Grafana/Prometheus.

**Implementado:**
- **structlog** com JSON (prod) / ConsoleRenderer (dev), file rotation (logs/app.log, logs/errors.log, 10MB, 30 backups)
- **LoggingMiddleware**: request/response logging com structlog, method/path/status_code/duration_ms/request_id/trace_id
- **AuditContextMiddleware**: structlog contextvars binding, request_id (server), trace_id (client X-Request-Id)
- **AuditLogEntry**: 5 new columns (request_id, http_method, http_path, duration_ms, status_code) — migration 20260729_01
- **AuditMixin**: auto-audit in write routes (12 files integrated)
- **SecurityAuditor**: 5 structlog event methods (auth failures, CSRF, SSRF, rate limit, calibration)
- **Frontend telemetry**: telemetry.ts (zero deps), use-telemetry.ts hooks, TelemetryProvider (error capture + auto-flush)
- **POST /api/v1/events**: rate-limited (100/min), public endpoint for frontend events
- **X-Request-Id correlation**: FE sends header → BE uses as trace_id, same request_id shared across middleware chain

**Fixes nesta sessão:**
- LoggingMiddleware: `logging.getLogger()` → `structlog.get_logger()` (fields weren't appearing in logs)
- `trace_id` added to LoggingMiddleware bind (client X-Request-Id was lost)
- Tests: rewrote 6 tests from mock-based to structlog.testing.capture_logs()

**Commits finais:**
- `c31a2f6`: Logging full-stack (structlog, middleware, events, TelemetryProvider, 35 tests)
- `17e6786`: Fix LoggingMiddleware structlog + trace_id correlation

---

## 2026-07-31 (Sessão Atual)

### Foco: Escopo do sistema + limpeza de pendências

**Clarificação de escopo:**
- Este é um **sistema de recomendação de investimentos**, NÃO de operação/trading
- **Nunca** haverá integração com broker
- Broker item removido do PENDENTE.md

**Feito:**
- Atualizado `.env`: `AI__GATEWAY__MODEL=qwen` → `ornith` (modelo novo, API keys mantidas)
- Backend e frontend reiniciados e funcionando
- PENDENTE.md atualizado: item 1 (Broker) marcado como REMOVIDO com motivo

**Expansão de Scoring (9 dimensões):**
- `market_data.py`: novas funções `get_analyst_data()`, `get_esg_data()`, expandido `get_fundamentals()` com ~15 campos extras
- `portfolio_advisor.py`: reescrito com 9 scoring functions: fundamental, momentum, valuation, risk, analyst, leverage, growth, liquidity, earnings
- Pesos rebalanceados (soma = 1.0)
- API route retorna scores detalhados por dimensão

**Integração LLM (ornith):**
- `generate_llm_analysis()` conecta ao ornith via LiteLLM proxy
- Timeout 30s com fallback gracioso para rule-based
- Gera análise em linguagem natural por ativo + portfolio-level
- Frontend mostra "Análise IA" quando disponível, "indisponível" quando off-line

**Cache de Dados de Mercado (PENDENTE.md #4 ✅):**
- `_TTLCache` in-memory em `market_data.py`
- Fundamentals: TTL 1h, max 256 entries
- Analyst: TTL 4h, max 256 entries
- History: TTL 15min, max 128 entries
- Current prices: sem cache (sempre fresco)
- `GET /api/v1/health/cache` para monitoramento
- 50% hit rate em chamadas sequenciais

**Frontend:**
- `RecommendationsTab.tsx`: 9 barras de score (expandível), análise LLM por ativo
- Tipos TS atualizados: `scores`, `llm_analysis` em `PortfolioRecommendation`
- React key error corrigido (Fragment com key)
