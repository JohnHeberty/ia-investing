# PLAN.md — Sistema de Logging Completo

## Objetivo
Rastrear **absolutamente tudo**: clicks do frontend, requisições HTTP, ações do backend, erros — tudo correlacionado por `request_id`, salvo em arquivos com rotação.

**Sem Grafana/Prometheus. Sem serviços externos. Tudo em arquivos locais.**

---

## Fases

### Fase 1: Backend — structlog + Request Logging ✅
- [x] 1.1 Instalar structlog, criar `logging_config.py` (JSON output, contextvars)
- [x] 1.2 Criar `LoggingMiddleware` (method, path, status, duration, request_id)
- [x] 1.3 Expandir `AuditContextMiddleware` (bind structlog contextvars, timing)
- [x] 1.4 File rotation: `logs/app.log`, `logs/errors.log` (JSONL, 10MB, 30 backups)

### Fase 2: Backend — Audit Trail Completo ✅
- [x] 2.1 Migration: colunas extras em `audit_log_entries` (request_id, http_method, path, duration_ms, status_code)
- [x] 2.2 Criar `AuditMixin` para auto-audit em rotas de escrita
- [x] 2.3 Integrar audit em 12 rotas POST/PUT/PATCH/DELETE
- [x] 2.4 Implementar `SecurityAuditor` (era stub) → `logs/security.log`

### Fase 3: Frontend — Telemetry ✅
- [x] 3.1 Criar `telemetry.ts` (zero deps, custom, batch flush)
- [x] 3.2 Hooks React: `usePageView`, `useClickTracking`, `useFormTracking`
- [x] 3.3 `TelemetryProvider` (auto-capture errors, startAutoFlush)
- [x] 3.4 API route `POST /api/v1/events` → `logs/app.log` (rate limited)
- [x] 3.5 Enviar `X-Request-Id` no `api-client.ts`

### Fase 4: Integração ✅
- [x] 4.1 `AuditContextMiddleware` → `structlog.contextvars.bind_contextvars()`
- [x] 4.2 Correlação FE→BE via `X-Request-Id`
- [x] 4.3 Limpar código morto (audit_models.py mantido — tem imports)
- [x] 4.4 `.gitignore` + `.env.example`

### Fase 5: Testes ✅
- [x] 5.1 Testes unitários (35 testes novos — todos passando)
- [x] 5.2 Code review (5 eixos — 3 issues críticos corrigidos)
- [ ] 5.3 Testes de integração (requer DB real)
- [ ] 5.4 Verificação manual (requer app rodando)

---

## Ordem
```
Fase 1 + Fase 3 (paralelo) → Fase 2 → Fase 4 → Fase 5
```

## Arquivos

### Novos
| Arquivo | Fase |
|---------|------|
| `src/ia_investing/logging_config.py` | 1 |
| `src/apps/api/middleware/logging.py` | 1 |
| `src/ia_investing/application/_audit_mixin.py` | 2 |
| `src/apps/api/routes/events.py` | 3 |
| `migrations/versions/20260729_01_audit_enrichment.py` | 2 |
| `web/src/lib/telemetry.ts` | 3 |
| `web/src/hooks/use-telemetry.ts` | 3 |
| `web/src/components/telemetry-provider.tsx` | 3 |

### Modificados
| Arquivo | Fase |
|---------|------|
| `src/apps/api/app_factory.py` | 1,3 |
| `src/apps/api/middleware/audit_context.py` | 1,4 |
| `src/ia_investing/settings.py` | 1 |
| `pyproject.toml` | 1 |
| `.gitignore` | 4 |
| `.env.example` | 4 |
| `web/src/lib/api-client.ts` | 3 |
| `web/src/app/layout.tsx` | 3 |
| `src/apps/api/routes/calibration.py` | 2 |
