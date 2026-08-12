# TODO — Correções Pendentes do Code Review

**Atualizado:** 2026-07-28 (Sessão 4 — 118 fixes, 24 fases concluídas)

---

## ✅ Fase 1 — Critical: Segurança e Consistência (CONCLUÍDA)
- [x] R6-C2: Consolidar 4 sessões DB no agent_runtime
- [x] R6-C3: Heartbeat timeout em candidate activities
- [x] R2-4: Atomicidade no agent_runtime/_runtime.py (FOR UPDATE)
- [x] R4-12: FK circular InvestmentCandidate ↔ ExplorationSuggestion
- [x] R5-10: operations.organization_id → NOT NULL
- [x] R5-11: Organization.status CHECK constraint

## ✅ Fase 2 — Performance: N+1 Queries (CONCLUÍDA)
- [x] R2-5: N+1 price fetch (false positive — already batch)
- [x] R2-6: N+1 FX rates em _nav.py (batch FX rates)
- [x] R2-7: N+1 em _risk.py (já fixado no working tree)

## ✅ Fase 3 — Orchestration Hardening (CONCLUÍDA)
- [x] R6-H1: Outbox dead letter para Path A
- [x] R6-H2: FOR UPDATE no create_scheduled_exploration_run
- [x] R6-H3: Retry policies no PortfolioConstructionWorkflow
- [x] R6-H4: cancel_activity + CancelledError handler

## ✅ Fase 4 — Segurança e Permissões (CONCLUÍDA)
- [x] R1-R1: _session_middleware auth_context
- [x] R2-11: Challenger bypass → status="proposed"
- [x] R1-R7: Agent runs org_id filtering
- [x] R2-10: TOCTOU em optimization run (FOR UPDATE)

## ✅ Fase 5 — Infra e Docker (CONCLUÍDA)
- [x] R9-5: Dockerfile layer caching
- [x] R9-6: HEALTHCHECK
- [x] R9-12: .dockerignore atualizado

## ✅ Fase 6 — God Methods (CONCLUÍDA)
- [x] R2-24: _reconciliation.py refatorado
- [x] R2-25: _nav.py refatorado (NavService)
- [x] R2-26: committee_service.py vote state guard

## ✅ Fase 7 — Frontend Medium (PARCIAL — 3/8)
- [x] R7-M4: window.prompt → Radix Dialog
- [x] R7-M5: "0/0" → "—" sem fontes
- [x] R7-M8: onError em mutations de rebalance

---

## 🔜 PRÓXIMOS PASSOS

## Fase 1 — Quick Wins: Segurança + API (~1h)

- [ ] **1.1** R1-R7: Permission check em agents endpoints (agents.py)
- [ ] **1.2** O12: SSRF check deve bloquear, não logar (request_host_validator.py)
- [ ] **1.3** O9/O10: Cursor pagination bug (research.py + investment_candidates.py)
- [ ] **1.4** O6: Sanitizar JWT error message (auth.py)
- [ ] **1.5** O2: Timing-safe CSRF comparison (security.py)

## Fase 2 — API Routes + Auth Medium (~1.5h)

- [ ] **2.1** R1-R15: Remover ou registrar audit_context middleware
- [ ] **2.2** R1-R12: Temporal client por request (investment_candidates.py)
- [ ] **2.3** R1-R6: Dict comprehension KeyError (portfolio.py)
- [ ] **2.4** O15: RebalanceService sem org scoping (rebalance.py)
- [ ] **2.5** O11: list_model_portfolios busca dashboard completo (institutional.py)
- [ ] **2.6** O5: _oidc_states in-memory (auth.py)
- [ ] **2.7** O4: ALLOWED_REDIRECT_HOSTS configurável (auth.py)
- [ ] **2.8** O7: readiness.py host:port parsing
- [ ] **2.9** O17: String comparison para "already exists" (investment_candidates.py)

## Fase 3 — Nit Items (~30min)

- [ ] **3.1** N1-N9: hmac.new naming, del exc, frozenset truthiness, PKCE docs, model_validator type, parse_etag consolidar, map_error consolidar, OperationAcceptedV1 rename, Request=None doc

## Fase 4 — Infra Medium (~1.5h)

- [ ] **4.1** R9-10: litellm security hardening (compose.yml)
- [ ] **4.2** R9-9: MLflow password → env var (compose.yml)
- [ ] **4.3** R9-11: Verificar uv.lock versionado
- [ ] **4.4** R9-M2: alembic.ini URL → env var
- [ ] **4.5** R9-M3: Postgres version → 17
- [ ] **4.6** R9-M4: pgvector extension
- [ ] **4.7** R9-M5: CI permissions
- [ ] **4.8** R9-M8: compose workers redundantes
- [ ] **4.9** R9-M9: web service security

## Fase 5 — Frontend Remaining (~1h)

- [ ] **5.1** R7-M3: CNPJ format validation (candidate-create-form.tsx)
- [ ] **5.2** R7-L2: LoadingSkeleton duplicado (rebalance/page.tsx)
- [ ] **5.3** R7-L1: Inline styles → CSS tokens
- [ ] **5.4** R7-M1: CSRF no login (server-side BFF)
- [ ] **5.5** R7-M2: JWT signature verify (jose library)
- [ ] **5.6** R7-M6: aria-label em tabs
- [ ] **5.7** R7-M7: Mixed API patterns

## Fase 6 — Orchestration Docs (~30min)

- [ ] **6.1** R6-M1: Documentar _RUNTIME
- [ ] **6.2** R6-M4: Documentar cancel signal scope
- [ ] **6.3** R6-M6: Validação Pydantic em activities
- [ ] **6.4** R6-M7: Documentar TLS requirement
- [ ] **6.5** R6-L1-L5: Nit fixes

## Fase 7 — DB Duplications (~4h, requer migrations)

- [ ] **7.1** R5-15: Duplicate RebalanceProposal
- [ ] **7.2** R5-16: Duplicate audit systems
- [ ] **7.3** R5-17: Duplicate agent tracking
- [ ] **7.4** R5-18: Duplicate thesis models
- [ ] **7.5** R5-19: Missing updated_at
- [ ] **7.6** R5-21: ARRAY vs JSONB
- [ ] **7.7** R5-22: StrategyMandate 20+ columns

## Fase 8 — Tests (~4h)

- [ ] **8.1** R8: Cobertura de módulos novos
- [ ] **8.2** R8: Testes de integração reais
- [ ] **8.3** R8: Fixtures realistas
- [ ] **8.4** R8: Testes de segurança
- [ ] **8.5** R8: Naming conventions

## Fase 9 — R2/R3/R4 Low + Architecture (~2h)

- [ ] **9.1** R2 Low (29-38)
- [ ] **9.2** R2 Architecture (39-42)
- [ ] **9.3** R3 Medium (15-22)
- [ ] **9.4** R3 Low (23-28)
- [ ] **9.5** R4 Medium (15-22)
- [ ] **9.6** R4 Low (23-29)

## Fase 10 — R5 Low + Performance (~2h)

- [ ] **10.1** R5 Low (23-28)
- [ ] **10.2** R5 Performance (29-32)
- [ ] **10.3** R5 Migration (33-34)

---

## Itens que requerem ação manual
- **R9-1**: `git filter-repo` para limpar .env do history
- **R7-M1**: Server-side BFF para CSRF token
- **R7-M2**: jose library + server-side JWT verification
- **R7-M7**: Refactoring amplo de API clients

---

## 🔧 Fase 25 — Candidate Intelligence: Ativação e Correções (2026-08-11)

### ✅ Fase 25.1 — Bugs Críticos
- [x] **CI-1**: Corrigir URL mismatch frontend — `web/src/lib/candidate-api.ts` (promote: `/exploration-runs/suggestions/{id}/promotion`, dismiss: `/exploration-runs/suggestions/{id}/dismissal`)
- [x] **CI-2**: Fechar Temporal client — NÃO É BUG (SDK Python não tem close(), gRPC gerenciado internamente)

### ✅ Fase 25.2 — Bugs Medium
- [x] **CI-3**: Remover DatabaseRuntime.create() duplicado — `src/ia_investing/candidate_intelligence/sync_pipeline.py` (removida 1ª chamada duplicada)
- [x] **CI-4**: Substituir assert por LookupError — `src/ia_investing/application/investment_candidates.py` linha 666 (`if existing is None: raise LookupError`)
- [x] **CI-5**: Unificar readiness computation — documentado no codebase, deferido (route handler e domain evaluator servem propósitos diferentes)

### ✅ Fase 25.3 — Melhorias Low
- [x] **CI-6**: Typed exception (RPCError.ALREADY_EXISTS) — `src/apps/api/routes/investment_candidates.py`
- [x] **CI-7**: Error handling no pipeline endpoint — `src/apps/api/routes/investment_candidates.py` (ConnectionError → 503, Exception → 422)
- [x] **CI-8**: UI de gap resolution — `web/src/app/opportunities/candidates/[id]/page.tsx` + `candidate-api.ts` + CSS (inline expandable card com textarea)
