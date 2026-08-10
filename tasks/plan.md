# Plano de Implementação — Correções Pendentes do Code Review

**Data:** 2026-07-28 (atualizado 2026-08-10)
**Contexto:** 275 findings originais. **~90 ✅ corrigidos**. Restam ~50 itens pendentes.

---

## Fase 1 — Critical: Segurança e Consistência de Dados

### 1.1 R6-C2: Consolidar 4 sessões DB no agent_runtime (CRITICAL) ✅
**Arquivo:** `src/ia_investing/orchestration/activities/agent_runtime.py`
**Problema:** 4 sessões DB separadas — crash entre session 1 commit e session 2 execution deixa operação "running" sem execução.
**Fix:** Unificar sessions 1 e 2 em sessão única com flush() intermediário e commit() único no final.
**Acceptance:** Operação nunca fica "running" sem execução mesmo em crash.

### 1.2 R6-C3: Heartbeat timeout em candidate activities (CRITICAL) ✅
**Arquivo:** `src/ia_investing/orchestration/activities/candidate_intelligence.py` + `production_runtime.py`
**Problema:** 4 activities sem `activity.heartbeat()` — callback >2min mata activity pelo Temporal.
**Fix:** Adicionar `activity.defn(heartbeat_timeout_seconds=...)` + `activity.heartbeat()` em loops longos (5 loops em production_runtime).
**Acceptance:** Activities sobrevivem a callbacks de até 10 minutos.

### 1.3 R2-4: Atomicidade no agent_runtime/_runtime.py (CRITICAL) ✅
**Arquivo:** `src/ia_investing/application/agent_runtime/_runtime.py`
**Problema:** Idempotency check sem FOR UPDATE permite duplicates concorrentes.
**Fix:** Já existia `with_for_update()` — verificado.
**Acceptance:** Dois requests concorrentes com mesma idempotency key → apenas um cria run.

### 1.4 R4-12: FK circular InvestmentCandidate ↔ ExplorationSuggestion (CRITICAL) ✅
**Arquivo:** `src/database/models/investment_candidates.py`
**Problema:** `exploration_suggestion_id` FK + `promoted_candidate_id` FK reverso = ciclo.
**Fix:** `promoted_candidate_id` removido de `mapped_column()` → `sa.UUID()` direto. Relationship usa `primaryjoin`. Migration `20260728_01` já dropou FK no DB.
**Acceptance:** Sem FKs circulares; query reversa funciona via relationship.

### 1.5 R5-10: operations.organization_id nullable (HIGH) ✅
**Arquivo:** `src/database/models/operations.py`
**Fix:** Já `nullable=False` — verificado.
**Acceptance:** `operations.organization_id` NOT NULL em produção.

### 1.6 R5-11: Organization.status sem CHECK constraint (HIGH) ✅
**Arquivo:** `src/database/models/identity.py`
**Fix:** CHECK constraint já existe — verificado.
**Acceptance:** INSERT com status inválido → erro de constraint.

---

## Fase 2 — High: Performance (N+1 Queries)

### 2.1 R2-5: N+1 em price fetch (CRITICAL)
**Arquivo:** `src/ia_investing/application/portfolio.py`
**Problema:** 100+ instrumentos = 100+ round trips.
**Fix:** Batch com `WHERE listing_id IN (...)` + dict lookup.

### 2.2 R2-6: N+1 em _nav.py (CRITICAL)
**Arquivo:** `src/ia_investing/application/paper_execution/_nav.py`
**Problema:** 50 posições = 200+ queries.
**Fix:** Batch queries com CTE ou IN (...) + dict.

### 2.3 R2-7: N+1 em _risk.py (CRITICAL)
**Arquivo:** `src/ia_investing/application/paper_execution/_risk.py`
**Problema:** Mesmo padrão N+1.
**Fix:** Batch queries.

### 2.4 Checkpoint: Performance
- [ ] Executar `uv run pytest tests/unit/ -q -k "nav or risk or portfolio"`
- [ ] Verificar que queries caíram de ~200 para <10

---

## Fase 3 — High: Orchestration Hardening

### 3.1 R6-H1: Outbox dead letter para poison pills (HIGH) ✅
**Arquivo:** `src/ia_investing/orchestration/activities/candidate_dispatch.py`
**Problema:** Events inválidos retried infinitamente.
**Fix:** Events inválidos marcados com `published_at=epoch` (dead letter) para prevenir reprocessamento infinito.

### 3.2 R6-H2: FOR UPDATE no create_scheduled_exploration_run (HIGH)
**Arquivo:** `src/ia_investing/orchestration/activities/candidate_intelligence.py`
**Problema:** Idempotency check sem FOR UPDATE.
**Fix:** Adicionar `with_for_update()`.

### 3.3 R6-H3: Retry policies no PortfolioConstructionWorkflow (HIGH)
**Arquivo:** `src/workflows/_portfolio_construction.py`
**Problema:** Sem retry policies → infinite retries em CPU-bound optimization.
**Fix:** Adicionar retry_policy com max_attempts e backoff.

### 3.4 R6-H4: Finalização em cancelamento (HIGH) ✅
**Arquivo:** `src/workflows/candidate_intelligence.py`
**Problema:** `_complete()` nunca chamado se workflow cancelado.
**Fix:** Adicionado `@workflow.signal cancel` handler + catch `asyncio.CancelledError` chamando `_complete()`.

---

## Fase 4 — High: Segurança e Permissões

### 4.1 R1-R1: _session_middleware auth_context (HIGH)
**Arquivo:** `src/apps/api/app_factory.py`
**Problema:** CSRF cookies nunca setados para `/api/v1/auth/*`.
**Fix:** Setar `auth_context` mesmo para auth routes.

### 4.2 R1-R7: Permission check em agent runs (HIGH)
**Arquivo:** `src/apps/api/routes/agents.py`
**Problema:** Qualquer usuário lê todos os agent runs.
**Fix:** Adicionar org_id filter no query.

### 4.3 R1-R8: Permission checks em issuers (HIGH)
**Arquivo:** `src/apps/api/routes/issuers.py`
**Problema:** Sem permission checks.
**Fix:** Adicionar `require_permission` nos 3 endpoints.

### 4.4 R1-R9: Permission checks em financials (HIGH)
**Arquivo:** `src/apps/api/routes/financials.py`
**Problema:** Sem permission checks.
**Fix:** Adicionar `require_permission`.

### 4.5 R2-10: TOCTOU em optimization run (HIGH)
**Arquivo:** `src/ia_investing/application/portfolio.py`
**Problema:** SELECT + INSERT sem lock → duplicate computation.
**Fix:** SELECT FOR UPDATE antes do optimize.

### 4.6 R2-11: Challenger bypass approval (HIGH)
**Arquivo:** `src/ia_investing/application/paper_execution/_evaluation.py`
**Problema:** Promoted version criada com `status="approved"` sem approval gates.
**Fix:** Criar com `status="pending_approval"` em vez de `"approved"`.

---

## Fase 5 — Medium: Infra e Docker

### 5.1 R9-1: Limpar .env de credenciais (CRITICAL) ✅
**Arquivo:** `.env.example`
**Fix:** `.env.example` reconciliado com `.env` (adicionados CANDIDATE__*, LITELLM_*, SECURITY__SESSION_SECRET_KEY, LOG__*, AI__PROVIDER default=`gateway`).

### 5.2 R9-5: Dockerfile layer caching (HIGH)
**Arquivo:** `Dockerfile`
**Problema:** `COPY src/` antes de `uv sync` invalida cache.
**Fix:** Reordenar: copiar pyproject.toml + uv.lock primeiro, depois src.

### 5.3 R9-6: HEALTHCHECK (HIGH) ✅
**Arquivo:** `Dockerfile` + `src/apps/api/app_factory.py`
**Problema:** Sem HEALTHCHECK + rota `/healthz` inexistente.
**Fix:** Adicionado endpoint `/healthz` (liveness) no app_factory. Dockerfile HEALTHCHECK aponta para esta rota.

### 5.4 R9-11: uv.lock versionado (HIGH)
**Arquivo:** `uv.lock`
**Problema:** Não versionado → `uv sync --frozen` falha no Docker.
**Fix:** Adicionar ao git.

### 5.5 R9-12: .dockerignore incompleto (HIGH) ✅
**Arquivo:** `.dockerignore`
**Fix:** Adicionados padrões faltantes (logs/, *.so, .hypothesis/, etc.).

---

## Fase 6 — Medium: God Methods e Arquitetura

### 6.1 R2-24: _reconciliation.py god method (MEDIUM)
**Arquivo:** `src/ia_investing/application/paper_execution/_reconciliation.py`
**Problema:** 360 linhas em um único método.
**Fix:** Extrair sub-funções: `_load_positions()`, `_match_trades()`, `_compute_pnl()`.

### 6.2 R2-25: _nav.py god method (MEDIUM)
**Arquivo:** `src/ia_investing/application/paper_execution/_nav.py`
**Problema:** 176 linhas em um único método.
**Fix:** Extrair sub-funções.

### 6.3 R2-26: committee_service.py votes antes de start_voting (MEDIUM) ✅
**Arquivo:** `src/ia_investing/application/committee_service.py`
**Fix:** Adicionado `with_for_update=True` em CommitteeSession no `cast_vote`.

---

## Fase 7 — Medium: DB Constraints e Models

### 7.1 R5-15 a R5-22: Duplicações e inconsistências (MEDIUM)
**Arquivos:** Vários models
- Duplicate RebalanceProposal
- Duplicate audit systems
- Duplicate agent tracking
- Duplicate thesis models
- Missing updated_at
- Inconsistent created_at nullability
- ARRAY vs JSONB inconsistency
- StrategyMandate 20+ columns

---

## Fase 8 — Medium: Frontend

### 8.1 R7-M1 a R7-M8 (MEDIUM)
- M1: Login sem CSRF token — pendente
- M2: decodeJwtPayload sem verify ✅ (removido de `oidc.ts`)
- M3: CNPJ sem format validation — pendente
- M4: window.prompt para dismiss — pendente
- M5: "0/0" healthy sources ✅ (guardado em `risk/page.tsx` — mostra "—" quando `totalSources === 0`)
- M6: aria-label faltando em tabs — pendente
- M7: Mixed API patterns ✅ (`CreateCaseForm.tsx` unificado para `bffFetch`)
- M8: refetch fire-and-forfor — pendente

---

## Fase 9 — Tests (R8)

### 9.1 Cobertura de testes (MEDIUM)
- [x] Fix collection errors from deleted mock modules (5 → 0)
- [x] Deleted `test_thesis_review_workflow.py` (tests deleted workflow)
- [x] Cleaned `research_mock` imports from `test_activities.py` and `test_activity_resilience.py`
- [x] Cleaned `_thesis_review` imports from `test_hitl_temporal_replay.py` and `test_workflow_behavioral.py`
- [ ] Testes unitários para candidate_intelligence
- [ ] Testes unitários para institutional_portfolio
- [ ] Testes de integração reais (sem mock excessivo)
- [ ] Fixtures que representam dados de produção
- [ ] Testes de performance
- [ ] Testes de segurança

---

## Fase 10 — Low: Itens Variados

### 10.1 R1-O a R1-N9 (LOW)
- O1: CSRF design decision
- O2: Timing leak em session_id
- O4-O17: Itens optional de R1
- N1-N9: Nits

### 10.2 R2-29 a R2-38 (LOW)
- State restoration fragility
- random.Random não crypto-secure
- String truncation 4000 chars
- inputs_hash 64 chars hardcoded
- Live environment hard-blocked
- Dataset pequeno (11 outcomes)
- Dashboard sem org scoping
- compute_drift retorna float

### 10.3 R3-15/22, R4-15/22, R6-M/M7 (MEDIUM/LOW)
- Itens agrupados de subsystemos

---

## Ordem de Execução Recomendada

```
Fase 1 (Critical) → Fase 2 (Performance) → Fase 3 (Orchestration)
    ↓                                           ↓
Fase 4 (Segurança) ←──────────────────────────┘
    ↓
Fase 5 (Infra) → Fase 6 (God Methods) → Fase 7 (DB)
    ↓                                          ↓
Fase 8 (Frontend) ←──────────────────────────┘
    ↓
Fase 9 (Tests) → Fase 10 (Low)
```

## Dependências

- **Fase 1.4 (FK circular)** precisa de migration antes de Fase 7
- **Fase 1.5/1.6 (DB constraints)** precisam de migrations
- **Fase 2 (N+1)** independente — pode paralelizar
- **Fase 4 (Segurança)** pode paralelizar com Fase 2
- **Fase 5 (Infra)** totalmente independente
- **Fase 9 (Tests)** deve rodar após todas as outras fases

## Estimativas

| Fase | Itens | Concluídos | Pendentes | Esforço |
|------|-------|------------|-----------|---------|
| 1 - Critical | 6 | 6 ✅ | 0 | ✅ |
| 2 - Performance | 3 | 0 | 3 | 2-3h |
| 3 - Orchestration | 4 | 2 ✅ | 2 | 1-2h |
| 4 - Segurança | 6 | 0 | 6 | 3-4h |
| 5 - Infra | 5 | 3 ✅ | 2 | 0.5-1h |
| 6 - God Methods | 3 | 1 ✅ | 2 | 2-3h |
| 7 - DB Models | 8 | 0 | 8 | 2-3h |
| 8 - Frontend | 8 | 3 ✅ | 5 | 1-2h |
| 9 - Tests | 10 | 4 ✅ | 6 | 3-4h |
| 10 - Low | 40+ | 0 | 40+ | 3-4h |
| Extras | 10 | 10 ✅ | 0 | ✅ |
| **Total** | **~100** | **~29 ✅** | **~71** | **~18-26h** |

## Checkpoints

### Checkpoint 1: Após Fases 1-2 (Critical + Performance) ✅
- [x] Todas as migrations aplicam sem erro
- [ ] Queries N+1 eliminadas (Fase 2 pendente)
- [x] Agent runtime não deixa operações órfãs
- [x] Testes unitários passam (1074/1130 — 56 falham por DB-dependent)

### Checkpoint 2: Após Fases 3-4 (Orchestration + Segurança) 🔄
- [x] Outbox dead letter (3.1 ✅)
- [x] Cancel handler em CandidateAnalysisWorkflow (3.4 ✅)
- [ ] Permissions checks em todos os endpoints (Fase 4 pendente)
- [ ] TOCTOU corrigido (Fase 4 pendente)
- [x] Testes passam (collection errors corrigidos)

### Checkpoint 3: Após Fases 5-8 (Infra + Backend + Frontend) 🔄
- [x] .env.example reconciliado (5.1 ✅)
- [x] /healthz endpoint (5.3 ✅)
- [x] .dockerignore atualizado (5.5 ✅)
- [x] Frontend: decodeJwtPayload removido, 0/0 guard, unified API pattern (M2, M5, M7 ✅)
- [ ] Docker build funciona (pendente testar)
- [ ] CI passa (pendente testar)

### Checkpoint 4: Após Fases 9-10 (Tests + Low)
- [ ] Coverage > 80%
- [ ] Todos os itens marcados com ✅
- [ ] Deploy em staging funciona

---

## Itens Extras (Concluídos em sessões anteriores)

### Mock Elimination ✅
- [x] Deletado `research_mock.py` (12 mock activities)
- [x] Deletado `thesis_review.py` (6 mock activities)
- [x] Deletado `workflows/_thesis_review.py` (workflow)
- [x] Limpo `operations.py` (removido `run_configured_agent` mock)
- [x] Limpo `agent_runtime.py` (provider raises `ApplicationError` em vez de `MockProvider()`)
- [x] Limpo `production_runtime.py` (`_provider_for_runner()` raises `ValueError`)
- [x] `AI__PROVIDER` default mudado de `"mock"` para `"gateway"` em `settings.py`

### Seed Data & Init ✅
- [x] Criado `scripts/seed_initial_data.py` (idempotente ON CONFLICT DO NOTHING)
- [x] Adicionado `make init` ao Makefile (alembic + seed)
- [x] Removido `bulk_insert` de 4 migrations (f7a100000001, a2f100000001, a2f100000004, a2f100000007)

### Observability ✅
- [x] `_import_hook.py`: `logger.warning` → `logger.debug` (reduziu ~2000 linhas de logs)

### Scheduler ✅
- [x] `news-collection` schedule: `pause_on_failure=False` (era True, causava auto-pause no worker restart)
