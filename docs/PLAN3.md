# PLAN3 — Master Plano de Correção — Auditoria Completa do Sistema

**Data:** 2026-08-14
**Escopo:** Todas as 26 páginas do frontend + todos os endpoints do backend
**Agentes:** 4 reviewers especializados por seção do menu

---

## Resumo Executivo

| Severidade | Qtd | Descrição |
|------------|-----|-----------|
| 🔴 CRITICAL | 12 | Bugs que causam crashes, perda de dados, ou bypass de segurança |
| 🟠 HIGH | 25 | Bugs que causam comportamento errado ou UX confusa |
| 🟡 MEDIUM | 30 | Code quality, performance, acessibilidade |
| **Total** | **67** | |

---

## 🔴 CRITICAL (12 issues — fix obrigatório)

### 1. Rebalance: Response model field mismatch → 5 endpoints crash
- **Arquivo:** `src/apps/api/routes/rebalance.py:50-59, 72-77`
- **Problema:** `RebalanceProposalCreatedResponse` e `RebalanceProposalActionResponse` declaram campo `state`, mas o DB model, service e frontend usam `status`. `ValidationError` → 5 endpoints crasham.
- **Fix:** Renomear `state` → `status` nos 3 response models.

### 2. Committee: Silent data loss em batchFetchDetails
- **Arquivo:** `web/src/hooks/use-committee.ts:75-86`
- **Problema:** `Promise.allSettled` descarta silenciosamente sessões com falha. Usuário vê lista incompleta sem feedback.
- **Fix:** Log de falhas + banner warning quando algumas sessões falharam.

### 3. Risk: AsOfIndicator mostra horário atual em vez do dado
- **Arquivo:** `web/src/app/risk/page.tsx:99-106`
- **Problema:** `AsOfIndicator` recebe `new Date()` em vez do timestamp real dos dados. Dados stale parecem frescos.
- **Fix:** Usar `overview?.snapshots?.[0]?.as_of` como valor.

### 4. Portfolio: PositionCreate.quantity aceita negativos
- **Arquivo:** `src/apps/api/routes/portfolio.py:177-212`
- **Problema:** `quantity: float` permite valores negativos. Corrompe cálculos de P&L e weights.
- **Fix:** Adicionar `Field(gt=0)` em `quantity` e `avg_cost_per_share`.

### 5. Policy: Import path inconsistente para DOU
- **Arquivo:** `src/ia_investing/orchestration/activities/policy_source_collection.py:171`
- **Problema:** `from connectors.policy._official` em vez de `from ia_investing.connectors.policy._official`. `ImportError` em runtime quando authority=dou.
- **Fix:** Corrigir path do import.

### 6. Macro: Endpoint sem permission check
- **Arquivo:** `src/apps/api/routes/risk_overview.py:318-322`
- **Problema:** `get_macro_indicators` aceita `AuthContext` mas nunca verifica permissão. Qualquer usuário autenticado lê dados macro.
- **Fix:** Adicionar `require_policy_read(auth)`.

### 7. Paper: Reconciliation column sempre "Pendente"
- **Arquivo:** `web/src/hooks/use-paper.ts:47, 58-60`
- **Problema:** `use-paper.ts` lê `i.reconciliation` mas `TradeIntentV1` não tem esse campo. Coluna sempre mostra "Pendente".
- **Fix:** Buscar reconciliações separadamente ou adicionar ao response.

### 8. Backtests: API endpoint mismatch
- **Arquivo:** `web/src/hooks/use-backtests.ts:24`
- **Problema:** Hook chama `/api/v1/backtests` mas backend pode ter routers duplicados. Verificar registro em `app_factory.py`.
- **Fix:** Verificar e alinhar routes.

### 9. Backtests: strategy_name sempre "—"
- **Arquivo:** `src/apps/api/routes/institutional_portfolios.py:686-696`
- **Problema:** Frontend espera `strategy_name` mas response não inclui. JOIN com `BacktestConfig` é inútil.
- **Fix:** Incluir `strategy_name` no response ou remover JOIN.

### 10. Backtests: Missing authorization
- **Arquivo:** `src/apps/api/routes/institutional_portfolios.py:679-696`
- **Problema:** `list_backtests` e POST usam `get_auth_context` sem `require_permission`. Qualquer usuário pode ler/criar backtests.
- **Fix:** Adicionar `require_permission("backtests:read/manage")`.

### 11. Audit: verify_audit_chain carrega tudo em memória
- **Arquivo:** `src/apps/api/routes/audit.py:89-97`
- **Problema:** `list(result.scalars().all())` carrega TODAS as entradas de audit em memória. OOM para tenants grandes.
- **Fix:** Adicionar paginação ou streaming.

### 12. Audit: resource_id=None em audit logs de schedules
- **Arquivo:** `src/apps/api/routes/schedules.py:53-68`
- **Problema:** `_log_schedule_audit()` não passa `resource_id`. Entradas de audit são intracoráveis.
- **Fix:** Passar `resource_id` como UUID derivado do `schedule_id`.

---

## 🟠 HIGH (25 issues — fix antes de merge)

### Decision Section
| # | Arquivo | Issue |
|---|---------|-------|
| 13 | `use-committee.ts:155-168` | O(n²) breach mapping — 50k comparações com 100 snapshots |
| 14 | `portfolios/[id]:51-313` | Monolith 313 linhas, 12+ useState, 7 hooks |
| 15 | `risk_overview.py:114-267` | Queries unbounded sem LIMIT no snapshot |
| 16 | `portfolio.py:43-49` | list_portfolios sem paginação |
| 17 | `portfolio.py:43-49` | N+1 potential em _to_dict |
| 18 | `candidates/page.tsx:22-44` | Raw useState/useEffect em vez de React Query |
| 19 | `candidates/[id]:22-54` | Mesmo padrão anti-React Query |
| 20 | `exploration/page.tsx:22-51` | Mesmo padrão + stale closure |

### Policy+Macro+News
| # | Arquivo | Issue |
|---|---------|-------|
| 21 | `use-policy.ts:93-98` | Alerts query nunca busca alertas resolved |
| 22 | `use-policy.ts:145-147` | staleSources sempre 0 (computa de events, não sources) |
| 23 | `risk_overview.py:346-348` | Macro endpoint engole erros DB silenciosamente |
| 24 | `use-news.ts:142-143` | isLoading exclui sourcesQuery e statsQuery |
| 25 | `use-macro.ts:95-100` | sourceHealthQuery errors invisíveis |
| 26 | `policy/page.tsx:290` | Forecasts mostra UUIDs em vez de nomes |
| 27 | `policy_intelligence.py:128-135` | latest_stage_time join ambíguo → duplicates |

### Paper+Rebalance+Agents+Quality
| # | Arquivo | Issue |
|---|---------|-------|
| 28 | `paper_execution.py:368-385` | Permission check depois de fetch → info leak |
| 29 | `rebalance/page.tsx:68-83` | Sem error state para proposal detail |
| 30 | `data-quality/page.tsx:68` | openIncidents count mismatch |
| 31 | `use-quality-incidents.ts:65-69` | dataState nunca reporta "stale" |
| 32 | `agents/page.tsx:97` | Label "últimos 7 dias" sem filtro de data |
| 33 | `rebalance.py:37-47` | Double permission check |

### Backtests+Audit+Schedules
| # | Arquivo | Issue |
|---|---------|-------|
| 34 | `schedules.py:336-342` | Reconcile audit log sem try/except |
| 35 | `schedules.py:284-315` | Fake pagination — busca tudo em memória |
| 36 | `schedules.py:370-386` | Session commit after Temporal fail → estado inconsistente |
| 37 | `schedules.py:37` | asyncio.Lock() não funciona multi-worker |
| 38 | `schedules.py:521-549` | "Load more" nunca busca do servidor |

---

## 🟡 MEDIUM (30 issues — fix em follow-up)

| # | Arquivo | Issue |
|---|---------|-------|
| 39 | `risk/page.tsx:111` | Stale warning mismatch |
| 40 | `opportunities/page.tsx:237` | Hard limit 12 cases |
| 41 | `candidate-api.ts:162-175` | CSRF handling inconsistente |
| 42 | `portfolios/[id]:114` | Error state = not-found state |
| 43 | `committee.py:198-222` | Sem org filtering |
| 44 | `use-portfolios.ts:48-76` | PortfolioListItem Pydantic unused |
| 45 | `exploration/page.tsx:53-80` | Shared submitting state |
| 46 | `news/service.py:615-649` | 6 COUNT queries separados |
| 47 | `policy_source_collection.py:193-231` | N+1 em _ingest_records |
| 48 | `policy_intelligence.py:487-489` | list_sources sem paginação |
| 49 | `news.py:138-140` | catch-all exception handler |
| 50 | `policy/page.tsx:513-519` | Empty catch em delete confirmation |
| 51 | `policy_source_collection.py:269-273` | Explicit commit dentro de session_scope |
| 52 | `paper_execution.py:594-601` | Permissão inconsistente em list endpoints |
| 53 | `rebalance/page.tsx:99-115` | Select sem label acessível |
| 54 | `rebalance/page.tsx:64-66` | Loading state incompleto |
| 55 | `paper_execution.py:356-365` | list_trade_intents sem paginação |
| 56 | `paper_execution.py:594-613` | list_post_mortems/challenger sem paginação |
| 57 | `agents/page.tsx:165` | Table mostra 10 mas count mostra total |
| 58 | `use-backtests.ts:63-68` | Stale detection desabilitado |
| 59 | `use-backtests.ts:24` | Sem paginação (limit=100 hardcoded) |
| 60 | `backtests/page.tsx:169-197` | Cards estáticos com badges hardcoded |
| 61 | `use-audit.ts:23-41` | Queries paralelas sem error correlation |
| 62 | `use-schedules.ts:312` | Missing dep em useEffect |
| 63 | `schedules.py:178-253` | _parse_schedule_description 75 linhas |
| 64 | `institutional_portfolios.py:679-696` | JOIN query mas scalar results |
| 65 | `schedules.py:451-497` | TOCTOU no trigger endpoint |
| 66 | `schedules/page.tsx:564-578` | window.confirm inaccessible |
| 67 | `policy/page.tsx:220-238` | Sem validação client-side para resolve notes |

---

## Plano de Implementação

### Fase 1: CRITICAL Fixes (12 issues) — 1-2 dias
**Prioridade:** Máxima. Bugs que causam crashes ou bypass de segurança.

| # | Issue | Arquivo | Esforço |
|---|-------|---------|---------|
| 1 | Rebalance field mismatch | rebalance.py | XS |
| 5 | DOU import path | policy_source_collection.py | XS |
| 6 | Macro permission check | risk_overview.py | XS |
| 12 | Audit resource_id | schedules.py | S |
| 2 | Committee silent loss | use-committee.ts | S |
| 3 | Risk as-of indicator | risk/page.tsx | XS |
| 4 | Portfolio quantity validation | portfolio.py | XS |
| 7 | Paper reconciliation | use-paper.ts | M |
| 8 | Backtests endpoint | use-backtests.ts | S |
| 9 | Backtests strategy_name | institutional_portfolios.py | S |
| 10 | Backtests authorization | institutional_portfolios.py | S |
| 11 | Audit chain OOM | audit.py | M |

### Fase 2: HIGH Fixes (25 issues) — 3-5 dias
**Prioridade:** Alta. Bugs que causam comportamento errado.

| Grupo | Issues | Esforço |
|-------|--------|---------|
| React Query migration (candidates, exploration) | #18, #19, #20 | L |
| Pagination (portfolios, risk, paper) | #15, #16, #55, #56 | M |
| Policy fixes (alerts, staleSources, forecasts) | #21, #22, #26, #27 | M |
| News/Macro fixes (isLoading, errors) | #23, #24, #25 | S |
| Rebalance fixes (error state, permissions) | #28, #29, #33 | S |
| Schedules fixes (reconcile, pagination, lock) | #34, #35, #36, #37, #38 | M |
| Other HIGH fixes | #13, #14, #17, #30, #31, #32 | M |

### Fase 3: MEDIUM Fixes (30 issues) — 5-10 dias
**Prioridade:** Média. Code quality, performance, acessibilidade.

| Grupo | Issues | Esforço |
|-------|--------|---------|
| Accessibility (labels, aria) | #53, #66 | S |
| Pagination (all remaining) | #48, #55, #56, #59 | M |
| Stale detection (all hooks) | #58, #61 | S |
| Code quality (long functions, DRY) | #46, #47, #63, #64 | M |
| UX improvements | #40, #42, #45, #50, #54, #57, #60, #62, #67 | M |
| Security (CSRF, permissions) | #41, #44, #49, #52 | S |
| Performance (N+1, caching) | #13, #47 | M |

---

## Estimativa de Esforço

| Fase | Issues | Dias Estimados |
|------|--------|----------------|
| Fase 1 (CRITICAL) | 12 | 1-2 |
| Fase 2 (HIGH) | 25 | 3-5 |
| Fase 3 (MEDIUM) | 30 | 5-10 |
| **Total** | **67** | **9-17** |

---

## Ordem de Prioridade Recomendada

1. **Fase 1 imediatamente** — CRITICAL bugs causam crashes e security bypass
2. **Fase 2 em paralelo** — HIGH bugs podem ser distribuídos entre devs
3. **Fase 3 iterativamente** — MEDIUM bugs melhoram qualidade gradualmente

---

## Verificação Pós-Correção

Para cada fase, rodar:
```bash
# Backend
uv run ruff check src/
uv run ruff format --check src/
uv run pytest tests/unit/ -q

# Frontend
cd web && npx tsc --noEmit
cd web && npx next build
```

---

## Notas

- Agentes de review: Decision (7 páginas), Policy+Macro+News (6 páginas), Paper+Rebalance+Agents+Quality (4 páginas), Backtests+Audit+Schedules (3 páginas)
- Total de páginas auditadas: 26
- Total de endpoints auditados: ~40
- Total de hooks auditados: ~20
- Total de modelos ORM auditados: ~15
