# Plano de Correção — Itens Restantes (Atualização pós-Sessão 4)

**Criado:** 2026-07-28 | **Última atualização:** 2026-07-28 (Sessão 4 — 118 fixes aplicados)

---

## Resumo Executivo

| Categoria | Pendentes | Feitos | Total | Risco |
|-----------|-----------|--------|-------|-------|
| R1 Required + Optional + Nit | ~31 | ~15 | 46 | Médio |
| R2 Low + Architecture | ~12 | ~26 | 38 | Baixo |
| R3 Medium + Low | ~14 | ~14 | 28 | Baixo |
| R4 Medium + Low | ~15 | ~14 | 29 | Baixo |
| R5 Medium + Low + Perf | ~18 | ~10 | 28 | Alto (migrations) |
| R6 Medium + Low | ~9 | ~10 | 19 | Baixo (docs) |
| R7 Medium + Low | ~11 | ~16 | 27 | Baixo |
| R8 Tests | 25 | 0 | 25 | Baixo |
| R9 Critical + High + Medium + Low | ~25 | ~10 | 35 | Médio |
| **TOTAL** | **~160** | **~115** | **275** | |

### Top 10 Prioridades (Ainda Abertas)

1. **R1-R7** `agents.py:15-36` — Sem permission check em list/get agent runs → qualquer usuário lê todos os agent runs
2. **O12** `request_host_validator.py:54-63` — SSRF check é post-hoc (log mas não bloqueia)
3. **R9-1** `.env` com credenciais no git history — requer `git filter-repo`
4. **O9/O10** Bug de cursor pagination — último item duplicado entre páginas
5. **O15** `rebalance.py` — `RebalanceService` sem org scoping
6. **O5** `auth.py:32` — `_oidc_states` in-memory, não compartilhado entre workers
7. **O6** `auth.py:129` — JWT failure leaka exception detail ao client
8. **R1-R15** `audit_context.py` — Definido mas nunca registrado (dead code)
9. **R1-R12** `investment_candidates.py:564` — Temporal client criado por request
10. **R9-10** `litellm` sem security hardening no compose

---

## Fase 1 — Quick Wins: Segurança + API (~1h)

Itens de alto impacto, baixo esforço.

### 1.1 R1-R7: Permission check em agents endpoints
**Arquivo:** `src/apps/api/routes/agents.py`
**Problema:** `list_agent_runs` e `get_agent_run` sem permission check — qualquer usuário autenticado lê todos os agent runs.
**Fix:**
```python
@router.get("/agent-runs")
async def list_agent_runs(
    auth: AuthContext = Depends(get_auth_context),
    _: None = Depends(require_permission("agent_runs:read")),
    ...
```
**Verificar:** Se `AgentRun` tem `organization_id` para filtering.

### 1.2 O12: SSRF check deve bloquear, não logar
**Arquivo:** `src/apps/api/middleware/request_host_validator.py:54-63`
**Problema:** Check发生在 `call_next()` 之后 — request já foi servido.
**Fix:** Mover check para ANTES de `call_next()`:
```python
async def __call__(self, request, call_next):
    if not self._is_safe_host(request.url.hostname):
        return JSONResponse(status_code=400, content={"detail": "Invalid host"})
    return await call_next(request)
```

### 1.3 O9/O10: Cursor pagination bug
**Arquivos:** `research.py:410-412`, `investment_candidates.py:377-379`
**Problema:** Cursor aponta para `rows[limit-1]` (último visível) em vez de `rows[limit]` (primeiro invisível). Resultado: último item de página N repete em página N+1.
**Fix:** Buscar `limit+1` e usar `rows[limit].id` como cursor:
```python
rows = list((await session.execute(stmt.limit(limit + 1))).scalars().all())
if len(rows) > limit:
    response.headers["X-Next-Cursor"] = str(rows[limit].id)
    rows = rows[:limit]
```

### 1.4 O6: Sanitizar JWT error message
**Arquivo:** `src/apps/api/routes/auth.py:129`
**Problema:** `f"JWT verification failed: {exc}"` leaka exception detail.
**Fix:**
```python
logger.warning("JWT verification failed: %s", exc)
raise HTTPException(status_code=401, detail="JWT verification failed")
```

### 1.5 O2: Timing-safe CSRF comparison
**Arquivo:** `src/apps/api/security.py` (função `validate_csrf_token`)
**Fix:** Trocar `==` por `hmac.compare_digest()`.

---

## Fase 2 — API Routes + Auth Medium (~1.5h)

### 2.1 R1-R15: Remover ou registrar audit_context middleware
**Arquivo:** `src/apps/api/middleware/audit_context.py`
**Problema:** Middleware definido mas nunca registrado em `app_factory.py`.
**Fix:** Avaliar se é necessário. Se não, deletar o arquivo. Se sim, registrar com `app.add_middleware(AuditContextMiddleware)`.

### 2.2 R1-R12: Temporal client por request
**Arquivo:** `src/apps/api/routes/investment_candidates.py:564`
**Fix:** Usar `Depends(get_temporal_client)` em vez de `Client.connect()` manual.

### 2.3 R1-R6: Dict comprehension KeyError
**Arquivo:** `src/apps/api/routes/portfolio.py:41-57`
**Fix:** Usar `.get()` ou `Pydantic model_validate` em vez de `d[k]`.

### 2.4 O15: RebalanceService sem org scoping
**Arquivo:** `src/apps/api/routes/rebalance.py:34-37`
**Fix:** Passar `organization_id` do auth context para o service.

### 2.5 O11: list_model_portfolios busca dashboard completo
**Arquivo:** `src/apps/api/routes/institutional.py:102-121`
**Fix:** Criar query leve dedicada em vez de build() completo do dashboard.

### 2.6 O5: _oidc_states in-memory
**Arquivo:** `src/apps/api/routes/auth.py:32`
**Fix:** Usar `@lru_cache` ou Redis para compartilhar entre workers. Documentar limitação.

### 2.7 O4: ALLOWED_REDIRECT_HOSTS configurável
**Arquivo:** `src/apps/api/routes/auth.py:28`
**Fix:** Adicionar `ALLOWED_REDIRECT_HOSTS` ao Settings (env var).

### 2.8 O7: readiness.py host:port parsing
**Arquivo:** `src/apps/api/routes/readiness.py:52`
**Fix:** Usar `urllib.parse.urlparse` ou settings separados `host`/`port`.

### 2.9 O17: String comparison para "already exists"
**Arquivo:** `src/apps/api/routes/investment_candidates.py:588-590`
**Fix:** Catch `TemporalWorkflowAlreadyRunningError` ou exception específica.

---

## Fase 3 — Nit Items (~30min)

### 3.1 N1-N9: Quick fixes
| Item | Fix |
|------|-----|
| N1 | `hmac.new` → `hmac.HMAC` (naming correto) |
| N2 | `del exc` pattern → remover (já não é necessário em Python 3.x) |
| N3 | `frozenset UUID` truthiness → `len() > 0` |
| N4 | PKCE SHA-256 encoding → documentar que é correto |
| N5 | `model_validator` return type → adicionar `-> Self` |
| N6 | `parse_etag` duplicado → extrair para `src/apps/api/_etag.py` |
| N7 | `map_error` duplicado → consolidar |
| N8 | `OperationAcceptedV1` shadow → renomear |
| N9 | `Request = None` workaround → documentar |

---

## Fase 4 — Infra Medium (~1.5h)

### 4.1 R9-10: litellm security hardening
**Arquivo:** `docker/compose.yml:349-374`
**Fix:** Adicionar `read_only: true`, `tmpfs: [/tmp]`, `security_opt: [no-new-privileges:true]`.

### 4.2 R9-9: MLflow password em plaintext
**Arquivo:** `docker/compose.yml:338`
**Fix:** Usar variável de ambiente `${MLFLOW_DB_PASSWORD}` em vez de inline.

### 4.3 R9-11: Verificar uv.lock versionado
**Fix:** `git ls-files uv.lock` — se não existe, commitar.

### 4.4 R9-M2: alembic.ini URL vazia
**Fix:** `sqlalchemy.url = %(DATABASE_URL)s`

### 4.5 R9-M3: Postgres version mismatch
**Fix:** Padronizar em PostgreSQL 17 em todos os arquivos.

### 4.6 R9-M4: pgvector extension
**Fix:** Adicionar `CREATE EXTENSION IF NOT EXISTS vector` no init script.

### 4.7 R9-M5: CI permissions
**Fix:** Adicionar `permissions: contents: read` nos workflows.

### 4.8 R9-M8: compose workers redundantes
**Fix:** Consolidar `worker-data-ingestion` e `worker-research-agents`.

### 4.9 R9-M9: web service security
**Fix:** Adicionar `security_opt: [no-new-privileges:true]` ao service web.

---

## Fase 5 — Frontend Remaining (~1h)

### 5.1 R7-M3: CNPJ format validation
**Arquivo:** `web/src/components/candidates/candidate-create-form.tsx`
**Fix:** Adicionar máscara `XX.XXX.XXX/XXXX-XX` no input e validação Luhn/mod-11.

### 5.2 R7-L2: LoadingSkeleton duplicado
**Arquivo:** `web/src/app/rebalance/page.tsx:106`
**Fix:** Remover definição local e importar de `@/components/data-state-components`.

### 5.3 R7-L1: Inline styles → CSS tokens
**Problema:** Vários componentes usam `style={{}}` em vez de classes CSS.
**Fix:** Mover para classes CSS ou usar design tokens de forma consistente.

### 5.4 R7-M1: CSRF no login (server-side)
**Fix:** Requer implementação no BFF para setar CSRF cookie antes do redirect OIDC.

### 5.5 R7-M2: JWT signature verify
**Fix:** Requer `jose` library + verificação server-side no BFF callback.

### 5.6 R7-M6: aria-label em tabs
**Fix:** Adicionar `aria-label` nos tab triggers que não usam Radix.

### 5.7 R7-M7: Mixed API patterns
**Fix:** Consolar `candidate-api.ts` e `use-rebalance.ts` para usar `api-client.ts`.

---

## Fase 6 — Orchestration Docs (~30min)

### 6.1 R6-M1: Documentar _RUNTIME
**Fix:** Adicionar docstring explicando que factory-per-call é intencional.

### 6.2 R6-M4: Documentar cancel signal scope
**Fix:** Adicionar comment nos workflows listando estados canceláveis.

### 6.3 R6-M6: Validação Pydantic em activities
**Fix:** Adicionar Pydantic models para inputs de activities críticas.

### 6.4 R6-M7: Documentar TLS requirement
**Fix:** Adicionar note no README/AGENTS.md.

### 6.5 R6-L1-L5: Nit fixes
**Fix:** Imports, dead code, state validation — quick cleanup.

---

## Fase 7 — DB Duplications (~4h, requer migrations)

> ⚠️ **Alto risco** — cada fix gera migration + data migration.

### 7.1 R5-15: Duplicate RebalanceProposal
**Arquivos:** `portfolio_domain.py` vs `portfolio_models.py`
**Fix:** Consolidar. Migration: `INSERT INTO ... SELECT FROM ...`.

### 7.2 R5-16: Duplicate audit systems
**Arquivos:** `audit.py` vs `agents.py` (AuditLog)
**Fix:** Manter `AuditLogEntry`, deprecar `AuditLog`.

### 7.3 R5-17: Duplicate agent tracking
**Arquivos:** `agents.py` vs `agent_runtime.py`
**Fix:** Consolidar `AgentRun` em `AgentRuntimeRun`.

### 7.4 R5-18: Duplicate thesis models
**Fix:** Consolidar.

### 7.5 R5-19: Missing `updated_at`
**Fix:** Adicionar coluna + migration.

### 7.6 R5-21: ARRAY vs JSONB
**Fix:** Padronizar em JSONB.

### 7.7 R5-22: StrategyMandate 20+ columns
**Fix:** Extrair para `StrategyMandateConfig`.

---

## Fase 8 — Tests (~4h)

### 8.1 Cobertura de módulos novos
1. `candidate_intelligence.py` — testes de activities
2. `institutional_portfolio/` — testes de NAV, risk, optimization
3. `_evaluation.py` — testes de challenger
4. `operation_dispatch.py` — testes de outbox + DLQ

### 8.2 Testes de integração reais
5. Reduzir mocks
6. Adicionar testes com DB real (testcontainers)

### 8.3 Fixtures realistas
7. Criar fixtures de produção
8. Edge cases (empty portfolios, missing prices)

### 8.4 Testes de segurança
9. Permission checks (R1-R7, R1-R8, R1-R9)
10. Rate limiting
11. Input validation

### 8.5 Naming conventions
12. Padronizar `test_<behavior>`

---

## Fase 9 — R2/R3/R4 Low + Architecture (~2h)

Itens de baixa prioridade, melhorias de código.

### 9.1 R2 Low (29-38)
State restoration, `random.Random` crypto-secure, string truncation, etc.

### 9.2 R2 Architecture (39-42)
`ResourceAttributes` duplicado, portfolio services paralelos, audit logging inconsistente.

### 9.3 R3 Medium (15-22)
OpenAI client leak, model pricing fallback, base64 scan, error messages, etc.

### 9.4 R3 Low (23-28)
PROMPTS_ROOT, JSON parse, inline import, token estimation, etc.

### 9.5 R4 Medium (15-22)
Margin calculations, parameter shadows, SHA256 truncation, etc.

### 9.6 R4 Low (23-29)
Dead guards, cache eviction, balance sheet validation, etc.

---

## Fase 10 — R5 Low + Performance (~2h)

### 10.1 R5 Low (23-28)
Constraint naming, JSON vs JSONB, Float vs Numeric, etc.

### 10.2 R5 Performance (29-32)
Partitioning, HNSW index, selectin lazy loading.

### 10.3 R5 Migration (33-34)
Naming consistency, diamond branch.

---

## Ordem de Execução Recomendada

```
Fase 1  (1h)    → Quick Wins: SSRF, pagination, JWT, CSRF (segurança)
Fase 2  (1.5h)  → API Routes Medium (permissions, org scoping)
Fase 3  (30min) → Nit Items (quick fixes)
Fase 4  (1.5h)  → Infra Medium (Docker, CI, compose)
Fase 5  (1h)    → Frontend Remaining (CNPJ, loading, styles)
Fase 6  (30min) → Orchestration Docs (documentation only)
Fase 7  (4h)    → DB Duplications (migrations — alto risco)
Fase 8  (4h)    → Tests (coverage)
Fase 9  (2h)    → R2/R3/R4 Low + Architecture
Fase 10 (2h)    → R5 Low + Performance
```

**Total estimado:** ~18h de trabalho
**Itens puláveis:** R9-1 (git filter-repo manual), R7-M1/M2 (server-side BFF), R7-M7 (refactoring amplo)

---

## Comandos de Verificação

```bash
# Ruff check
ruff check src/
ruff format --check src/

# Type check
mypy src

# Tests
pytest tests/ -q

# Frontend
cd web && npm run typecheck && npm run lint

# Docker
docker compose config
```
