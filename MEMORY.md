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
