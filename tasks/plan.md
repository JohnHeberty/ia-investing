# Plano de Implementação — Correções Pendentes do Code Review

**Data:** 2026-07-28
**Contexto:** 275 findings originais. 68 ✅ corrigidos. Restam ~140 itens não-fixos.

---

## Fase 1 — Critical: Segurança e Consistência de Dados

### 1.1 R6-C2: Consolidar 4 sessões DB no agent_runtime (CRITICAL)
**Arquivo:** `src/ia_investing/orchestration/activities/agent_runtime.py`
**Problema:** 4 sessões DB separadas — crash entre session 1 commit e session 2 execution deixa operação "running" sem execução.
**Fix:** Unificar sessions 1 e 2 em sessão única com flush() intermediário e commit() único no final.
**Acceptance:** Operação nunca fica "running" sem execução mesmo em crash.

### 1.2 R6-C3: Heartbeat timeout em candidate activities (CRITICAL)
**Arquivo:** `src/ia_investing/orchestration/activities/candidate_intelligence.py`
**Problema:** 4 activities sem `activity.heartbeat()` — callback >2min mata activity pelo Temporal.
**Fix:** Adicionar `activity.defn(heartbeat_timeout_seconds=...)` + `activity.heartbeat()` em loops longos.
**Acceptance:** Activities sobrevivem a callbacks de até 10 minutos.

### 1.3 R2-4: Atomicidade no agent_runtime/_runtime.py (CRITICAL)
**Arquivo:** `src/ia_investing/application/agent_runtime/_runtime.py`
**Problema:** Idempotency check sem FOR UPDATE permite duplicates concorrentes.
**Fix:** Adicionar `with_for_update()` no SELECT de idempotency check.
**Acceptance:** Dois requests concorrentes com mesma idempotency key → apenas um cria run.

### 1.4 R4-12: FK circular InvestmentCandidate ↔ ExplorationSuggestion (CRITICAL)
**Arquivo:** `src/database/models/investment_candidates.py`
**Problema:** `exploration_suggestion_id` FK + `promoted_candidate_id` FK reverso = ciclo.
**Fix:** Remover `promoted_candidate_id` (direção reversa é lookup derivado). Adicionar relationship() em ambos os lados. Criar migration.
**Acceptance:** Sem FKs circulares; query reversa funciona via relationship.

### 1.5 R5-10: operations.organization_id nullable (HIGH)
**Arquivo:** `src/database/models/operations.py` + migration
**Problema:** Tabela tenant-scoped com coluna nullable.
**Fix:** Migration para NOT NULL (com default temporário se necessário).
**Acceptance:** `operations.organization_id` NOT NULL em produção.

### 1.6 R5-11: Organization.status sem CHECK constraint (HIGH)
**Arquivo:** `src/database/models/identity.py` + migration
**Problema:** `status` aceita qualquer string.
**Fix:** Adicionar `CheckConstraint("status IN ('active', 'suspended', 'deleted')")`.
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

### 3.1 R6-H1: Outbox dead letter para poison pills (HIGH)
**Arquivo:** `src/ia_investing/orchestration/activities/operation_dispatch.py`
**Problema:** Events inválidos retried infinitamente.
**Fix:** Max attempts threshold + dead letter queue.

### 3.2 R6-H2: FOR UPDATE no create_scheduled_exploration_run (HIGH)
**Arquivo:** `src/ia_investing/orchestration/activities/candidate_intelligence.py`
**Problema:** Idempotency check sem FOR UPDATE.
**Fix:** Adicionar `with_for_update()`.

### 3.3 R6-H3: Retry policies no PortfolioConstructionWorkflow (HIGH)
**Arquivo:** `src/workflows/_portfolio_construction.py`
**Problema:** Sem retry policies → infinite retries em CPU-bound optimization.
**Fix:** Adicionar retry_policy com max_attempts e backoff.

### 3.4 R6-H4: Finalização em cancelamento (HIGH)
**Arquivo:** `src/workflows/_candidate_analysis.py`
**Problema:** `_complete()` nunca chamado se workflow cancelado.
**Fix:** Adicionar handler de cancelamento que chama `_complete()`.

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

### 5.1 R9-1: Limpar .env de credenciais (CRITICAL)
**Arquivo:** `.env`
**Problema:** Senhas reais commitadas.
**Fix:** Usar `.env.example` com placeholders; `git filter-repo` para limpar histórico.

### 5.2 R9-5: Dockerfile layer caching (HIGH)
**Arquivo:** `Dockerfile`
**Problema:** `COPY src/` antes de `uv sync` invalida cache.
**Fix:** Reordenar: copiar pyproject.toml + uv.lock primeiro, depois src.

### 5.3 R9-6: HEALTHCHECK (HIGH)
**Arquivo:** `Dockerfile`
**Problema:** Sem HEALTHCHECK.
**Fix:** Adicionar `HEALTHCHECK CMD curl -f http://localhost:8000/health || exit 1`.

### 5.4 R9-11: uv.lock versionado (HIGH)
**Arquivo:** `uv.lock`
**Problema:** Não versionado → `uv sync --frozen` falha no Docker.
**Fix:** Adicionar ao git.

### 5.5 R9-12: .dockerignore incompleto (HIGH)
**Arquivo:** `.dockerignore`
**Problema:** FALTAM: FIX/, QUALITY/, *.pdf, caches.
**Fix:** Adicionar padrões faltantes.

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

### 6.3 R2-26: committee_service.py votes antes de start_voting (MEDIUM)
**Arquivo:** `src/ia_investing/application/committee_service.py`
**Problema:** Votos permitidos em `in_session` antes de `start_voting`.
**Fix:** Adicionar guard: `if not voting_started: raise ValueError`.

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
- Login sem CSRF token
- decodeJwtPayload sem verify
- CNPJ sem format validation
- window.prompt para dismiss
- "0/0" healthy sources
- aria-label faltando em tabs
- Mixed API patterns
- refetch fire-and-forget

---

## Fase 9 — Tests (R8)

### 9.1 Cobertura de testes (MEDIUM)
- Testes unitários para candidate_intelligence
- Testes unitários para institutional_portfolio
- Testes de integração reais (sem mock excessivo)
- Fixtures que representam dados de produção
- Testes de performance
- Testes de segurança

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

| Fase | Itens | Esforço | Risco |
|------|-------|---------|-------|
| 1 - Critical | 6 | 3-4h | Alto (migrations) |
| 2 - Performance | 3 | 2-3h | Médio |
| 3 - Orchestration | 4 | 2-3h | Médio |
| 4 - Segurança | 6 | 3-4h | Baixo |
| 5 - Infra | 5 | 1-2h | Baixo |
| 6 - God Methods | 3 | 3-4h | Médio |
| 7 - DB Models | 8 | 2-3h | Baixo |
| 8 - Frontend | 8 | 2-3h | Baixo |
| 9 - Tests | 25 | 4-6h | Baixo |
| 10 - Low | 40+ | 3-4h | Baixo |
| **Total** | **~140** | **~25-35h** | |

## Checkpoints

### Checkpoint 1: Após Fases 1-2 (Critical + Performance)
- [ ] Todas as migrations aplicam sem erro
- [ ] Queries N+1 eliminadas
- [ ] Agent runtime não deixa operações órfãs
- [ ] Testes unitários passam

### Checkpoint 2: Após Fases 3-4 (Orchestration + Segurança)
- [ ] Outbox não retried infinitamente
- [ ] Permissions checks em todos os endpoints
- [ ] TOCTOU corrigido
- [ ] Testes de integração passam

### Checkpoint 3: Após Fases 5-8 (Infra + Backend + Frontend)
- [ ] Docker build funciona
- [ ] CI passa
- [ ] Frontend compila sem erro
- [ ] Health checks funcionam

### Checkpoint 4: Após Fases 9-10 (Tests + Low)
- [ ] Coverage > 80%
- [ ] Todos os itens marcados com ✅
- [ ] Deploy em staging funciona
