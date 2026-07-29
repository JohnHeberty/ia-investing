# Plano: Sistema de Logging Completo — Rastreamento Total

## Objetivo
Implementar um sistema de logging que rastreie **absolutamente tudo**: clicks do usuário no frontend, requisições HTTP, ações do backend, erros, e mudanças de estado — tudo correlacionado por `request_id` e salvos em arquivos com rotação.

## Restrições do Usuário
- **Sem Grafana, sem Prometheus** — logs ficam em arquivos locais
- **Sem serviços externos** — tudo self-hosted, sem Mixpanel/Amplitude/Sentry
- **Logs internos** — salvos em `logs/` com rotação

## O que existe hoje (gap analysis)

| Componente | Estado | O que falta |
|------------|--------|-------------|
| `AuditContextMiddleware` | Captura request_id, ip, user_agent | Não captura timing, status code, não injeta no logging context |
| `AuditLogEntry` (hash chain) | Escrito por 2 services (committee, execution) | 95% das rotas não escrevem audit entries |
| `AuditLog` (audit_models.py) | Tabela sem writers | **Código morto** — não usar |
| Python `logging` | 43+ módulos usam `logging.getLogger()` | Sem formatação JSON, sem correlação com request_id, sem config |
| structlog | Não instalado | Necessário para structured logging |
| OTel pipeline | Instrumentado mas exporta pra arquivo local | Sem backend queryável |
| Frontend tracking | Zero | Nenhum event capture, analytics, ou error reporting |
| Request/response logging | Não existe | Nenhum middleware loga method/path/status/duration |
| Correlação FE↔BE | `X-Trace-Id` lido mas nunca enviado pelo frontend | Gap de trace |

---

## Arquitetura Proposta

```
┌─────────────────────────────────────────────────────────┐
│  FRONTEND (Next.js)                                    │
│  ┌───────────────────┐  ┌──────────────────────────┐   │
│  │ telemetry.ts      │  │ api-client.ts             │   │
│  │ • track(event)    │  │ • Envia X-Request-Id      │   │
│  │ • flush() batch   │  │ • Envia X-Forwarded-For   │   │
│  │ • Captura clicks  │  │                          │   │
│  │ • Captura errors  │  │                          │   │
│  └───────┬───────────┘  └──────────┬───────────────┘   │
│          │ POST /api/v1/events     │ API calls          │
│          ▼                         ▼                    │
└──────────┼─────────────────────────┼────────────────────┘
           │                         │
┌──────────┼─────────────────────────┼────────────────────┐
│  BACKEND (FastAPI)                 │                    │
│          ▼                         ▼                    │
│  ┌───────────────┐  ┌──────────────────────────────┐   │
│  │ Events Router  │  │ LoggingMiddleware             │   │
│  │ POST /events   │  │ • Timing (start→end)          │   │
│  │ Recebe batch   │  │ • Status code                 │   │
│  │ Salva em JSON  │  │ • Structured JSON output      │   │
│  └───────┬────────┘  │ • Correlation ID              │   │
│          │           └──────────┬───────────────────┘   │
│          ▼                      ▼                       │
│  ┌───────────────┐  ┌──────────────────────────────┐   │
│  │ events.json    │  │ logs/                         │   │
│  │ (frontend log) │  │ ├── api-YYYY-MM-DD.log        │   │
│  └───────────────┘  │ ├── audit-YYYY-MM-DD.log       │   │
│                     │ ├── errors-YYYY-MM-DD.log       │   │
│                     │ └── security-YYYY-MM-DD.log     │   │
│                     └──────────────────────────────┘   │
│                                                         │
│  ┌──────────────────────────────────────────────┐      │
│  │ AuditContextMiddleware (expandido)             │      │
│  │ • Injeta request_id no structlog context       │      │
│  │ • Adiciona timing + status ao response         │      │
│  └──────────────────────────────────────────────┘      │
└─────────────────────────────────────────────────────────┘
```

---

## Fases de Implementação

### Fase 1: Backend — structlog + Request Logging Middleware
**Dependências:** `structlog` (pip install)
**Esforço:** ~2h
**Risco:** Baixo

#### Tarefa 1.1: Instalar e configurar structlog
- Adicionar `structlog` ao `pyproject.toml`
- Criar `src/ia_investing/logging_config.py`:
  - Configuração com `structlog.configure()` (JSON output em produção, ConsoleRenderer em dev)
  - Processores: `filter_by_level`, `add_logger_name`, `add_log_level`, `TimeStamper(fmt="iso")`, `CallsiteParameterAdder`, `JSONRenderer`
  - `structlog.contextvars.merge_contextvars` para request context
  - `logging.basicConfig(format="%(message)s", stream=sys.stdout, level=...)`
  - Integrar com `settings.application.log_level`
- Arquivos: `src/ia_investing/logging_config.py` (novo), `src/ia_investing/settings.py` (adicionar `LogSettings`)

#### Tarefa 1.2: Request/Response Logging Middleware
- Criar `src/apps/api/middleware/logging.py` — `LoggingMiddleware(BaseHTTPMiddleware)`:
  - `time.perf_counter()` antes/depois de `call_next()`
  - Loga: `method`, `path`, `status_code`, `duration_ms`, `request_id`, `ip`, `user_agent`
  - Nível: `INFO` para 2xx/3xx, `WARNING` para 4xx, `ERROR` para 5xx
  - Exclui health/readiness paths (noise reduction)
  - Output: JSON via structlog
- Arquivo: `src/apps/api/middleware/logging.py` (novo)
- Integrar em `app_factory.py` (middleware stack)

#### Tarefa 1.3: Expandir AuditContextMiddleware
- Modificar `audit_context.py`:
  - Adicionar `structlog.contextvars.bind_contextvars(request_id=..., trace_id=..., ip=..., user_agent=...)`
  - Capturar `time.perf_counter()` no início
  - Após `call_next()`: adicionar `status_code` e `duration_ms` ao context
  - Limpar contextvars no finally block
- Isso faz TODO log emitido durante o request automaticamente ter `request_id`关联

#### Tarefa 1.4: File-based log rotation
- Configurar Python `logging.handlers.RotatingFileHandler` em `logging_config.py`:
  - `logs/api-YYYY-MM-DD.log` — requests/responses
  - `logs/errors-YYYY-MM-DD.log` — erros apenas (level >= ERROR)
  - `logs/security-YYYY-MM-DD.log` — security events (SSRF, rate limit, CSRF)
  - Rotação: 10MB por arquivo, 30 backups
  - Encoding: UTF-8
  - Format: JSON por linha (1 JSON object por line = JSONL)
- Criar diretório `logs/` e adicionar ao `.gitignore`

---

### Fase 2: Backend — Audit Trail Completo
**Dependências:** Fase 1
**Esforço:** ~3h
**Risco:** Médio (toque em muitos arquivos)

#### Tarefa 2.1: Expandir AuditLogEntry schema
- Migration: adicionar colunas `request_id` (UUID, nullable, index), `http_method` (String(7), nullable), `http_path` (String(500), nullable), `duration_ms` (Float, nullable), `status_code` (Integer, nullable)
- Atualizar modelo `audit.py`
- Arquivo: migration `20260729_01_audit_enrichment.py`

#### Tarefa 2.2: Criar AuditMixin para rotas
- Criar `src/ia_investing/application/_audit_mixin.py`:
  ```python
  class AuditMixin:
      async def _audit(self, session, action, resource_type, resource_id=None, changes=None):
          ctx = get_log_context()  # from structlog.contextvars
          await AuditService(session, tenant_id).log(
              actor_id=...,
              action=action,
              resource_type=resource_type,
              resource_id=resource_id,
              changes=changes,
              metadata={
                  "request_id": ctx.get("request_id"),
                  "http_method": ctx.get("http_method"),
                  "http_path": ctx.get("http_path"),
                  "duration_ms": ctx.get("duration_ms"),
                  "ip": ctx.get("ip"),
              }
          )
  ```
- Helper: `get_log_context()` retorna dict com todos os campos do structlog context

#### Tarefa 2.3: Auto-audit em rotas de escrita
- Criar decorator/decorator pattern para rotas POST/PUT/PATCH/DELETE
- Alternativa: middleware que intercepta responses 2xx em rotas mutáveis e dispara audit
- Escopo: todas as rotas em `_AUTH_ROUTERS` que são POST/PUT/PATCH/DELETE
- ~23 rotas atuais + novas precisam de audit

#### Tarefa 2.4: Security event logging
- Expandir `SecurityAuditor` (hoje stub vazio) para gravar em `logs/security-YYYY-MM-DD.log`:
  - `on_auth_failure()` → log com `structlog` level=WARNING
  - `on_permission_denied()` → log com `structlog` level=WARNING
- Integrar com `auth.py` (falha de JWT), `_csrf_middleware` (CSRF falhou), `request_host_validator` (SSRF bloqueado)

---

### Fase 3: Frontend — Telemetry de Usuário
**Dependências:** Nenhuma (pode paralelizar com Fase 1-2)
**Esforço:** ~2h
**Risco:** Baixo

#### Tarefa 3.1: Criar módulo de telemetry
- Criar `web/src/lib/telemetry.ts`:
  ```typescript
  interface TelemetryEvent {
    event: string           // e.g. "page_view", "click", "form_submit", "error"
    target?: string         // e.g. "button.export", "link.portfolio"
    path: string            // current URL path
    timestamp: number       // Date.now()
    metadata?: Record<string, unknown>
  }

  class Telemetry {
    private queue: TelemetryEvent[] = []
    private flushInterval: NodeJS.Timeout | null = null

    track(event: string, target?: string, metadata?: Record<string, unknown>) {
      this.queue.push({ event, target, path: window.location.pathname, timestamp: Date.now(), metadata })
      if (this.queue.length >= 20) this.flush()
    }

    async flush() {
      if (this.queue.length === 0) return
      const batch = this.queue.splice(0)
      await fetch("/api/v1/events", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ events: batch }),
      }).catch(() => { this.queue.unshift(...batch) }) // retry on failure
    }

    startAutoFlush(intervalMs = 30_000) { ... }
    stop() { ... }
  }

  export const telemetry = new Telemetry()
  ```
- Sem dependências externas — 100% custom, zero analytics services

#### Tarefa 3.2: Auto-capture de eventos de UI
- Criar `web/src/hooks/use-telemetry.ts`:
  - `usePageView()` — loga page_view no useEffect (route change via `usePathname()`)
  - `useClickTracking(ref, target)` — loga clicks em elementos ref
  - `useFormTracking(formName)` — loga submit e erros de formulário
- Criar `web/src/components/providers/telemetry-provider.tsx`:
  - Provider React que inicializa `telemetry.startAutoFlush()`
  - Captura `window.onerror` e `unhandledrejection` como erros

#### Tarefa 3.3: API route para receber events
- Criar `src/apps/api/routes/events.py`:
  - `POST /api/v1/events` — recebe batch de eventos
  - Valida schema (event, path, timestamp)
  - Salva em `logs/events-YYYY-MM-DD.log` (JSONL)
  - Rate limit: 100 events/min per IP
  - Não requer autenticação (público, mas com rate limit)
- Adicionar router ao `app_factory.py`

#### Tarefa 3.4: Enviar X-Request-Id no frontend
- Modificar `web/src/lib/api-client.ts`:
  - Gerar UUID por sessão de navegação (stored in sessionStorage)
  - Enviar como `X-Request-Id` header em todas as requisições
  - Isso correlaciona logs do frontend com logs do backend

---

### Fase 4: Integração e Consolidação
**Dependências:** Fases 1-3
**Esforço:** ~1.5h
**Risco:** Baixo

#### Tarefa 4.1: Integrar AuditContextMiddleware com structlog
- `audit_context.py`: Usar `structlog.contextvars.bind_contextvars()` em vez de só `request.state`
- `request.state.audit_context` continua existendo (compatibilidade), mas structlog context é a primary

#### Tarefa 4.2: Correlação frontend→backend
- Frontend envia `X-Request-Id` (UUID gerado no client)
- Backend `AuditContextMiddleware` lê `X-Request-Id` header (fallback: gera UUID)
- Todas as linhas de log (structlog) e audit entries incluem `request_id`
- Resultado: `grep <request_id> logs/*.log` mostra toda a cadeia

#### Tarefa 4.3: Limpar código morto
- Deletar `audit_models.py` (`AuditLog` — sem writers)
- Remover `SecurityAuditor` stub vazio ou implementar
- Avaliar se OTel collector ainda é necessário (pode ser removido se logs em arquivo bastam)

#### Tarefa 4.4: Atualizar .gitignore e .env.example
- `.gitignore`: adicionar `logs/`
- `.env.example`: adicionar variáveis:
  ```
  APPLICATION__LOG_LEVEL=INFO
  LOG__DIR=./logs
  LOG__MAX_BYTES=10485760
  LOG__BACKUP_COUNT=30
  LOG__ENABLED=true
  ```

---

### Fase 5: Testes e Validação
**Dependências:** Fases 1-4
**Esforço:** ~1h
**Risco:** Baixo

#### Tarefa 5.1: Testes unitários
- `test_logging_config.py`: Verificar que structlog está configurado, JSON output funciona
- `test_logging_middleware.py`: Verificar que request/response é logado com campos corretos
- `test_audit_enrichment.py`: Verificar que audit entries incluem request_id, http_method, etc.
- `test_events_route.py`: Verificar que POST /events salva no arquivo correto
- `test_telemetry.py`: Verificar que telemetry.flush() envia batch

#### Tarefa 5.2: Testes de integração
- Verificar correlação: fazer request → verificar que request_id aparece em logs/ e em audit_log_entries
- Verificar que health/readiness não gera logs de request
- Verificar rotação de arquivos (mock)

#### Tarefa 5.3: Verificação manual
- Subir app localmente, fazer requests, verificar `logs/api-*.log` tem JSONs válidos
- Verificar `logs/events-*.log` tem eventos do frontend
- Verificar `grep <uuid> logs/*.log` mostra request completa

---

## Arquivos a Criar/Modificar

### Novos (backend)
| Arquivo | Propósito |
|---------|-----------|
| `src/ia_investing/logging_config.py` | Configuração structlog + file handlers |
| `src/apps/api/middleware/logging.py` | Request/response logging middleware |
| `src/ia_investing/application/_audit_mixin.py` | Mixin para auto-audit em rotas |
| `src/apps/api/routes/events.py` | API para receber frontend events |
| `migrations/versions/20260729_01_audit_enrichment.py` | Colunas extras em audit_log_entries |
| `tasks/plan-logging.md` | Este documento |

### Novos (frontend)
| Arquivo | Propósito |
|---------|-----------|
| `web/src/lib/telemetry.ts` | Módulo de telemetry custom |
| `web/src/hooks/use-telemetry.ts` | Hooks React para tracking |
| `web/src/components/providers/telemetry-provider.tsx` | Provider para auto-capture |

### Modificados (backend)
| Arquivo | Mudança |
|---------|---------|
| `src/apps/api/app_factory.py` | Adicionar LoggingMiddleware, events router |
| `src/apps/api/middleware/audit_context.py` | Integrar structlog contextvars |
| `src/ia_investing/settings.py` | Adicionar LogSettings |
| `pyproject.toml` | Adicionar structlog |
| `.gitignore` | Adicionar logs/ |
| `.env.example` | Adicionar variáveis de log |

### Modificados (frontend)
| Arquivo | Mudança |
|---------|---------|
| `web/src/lib/api-client.ts` | Enviar X-Request-Id header |
| `web/src/app/layout.tsx` | Adicionar TelemetryProvider |
| `web/package.json` | Sem mudanças (zero dependências novas) |

---

## Ordem de Execução Sugerida

```
Fase 1 (backend logging) ─┐
                           ├→ Fase 4 (integração) → Fase 5 (testes)
Fase 3 (frontend) ────────┘
Fase 2 (audit trail) ──────┘
```

- Fases 1 e 3 podem ser paralelizadas
- Fase 2 depende de Fase 1 (structlog precisa estar configurado)
- Fase 4 integra tudo
- Fase 5 valida

---

## Estimativas

| Fase | Tempo | Arquivos |
|------|-------|----------|
| Fase 1 | ~2h | 4 novos + 3 modificados |
| Fase 2 | ~3h | 1 migration + ~23 rotas |
| Fase 3 | ~2h | 3 novos + 3 modificados |
| Fase 4 | ~1.5h | ~5 modificados |
| Fase 5 | ~1h | ~6 testes novos |
| **Total** | **~9.5h** | **~18 novos + ~15 modificados** |

---

## Decisões de Design

### Por que não OTel collector como primary?
O OTel collector já existe no docker-compose mas exporta pra JSON files sem querying. O usuário quer logs em arquivos. Manter o OTel como secondário (traces/metrics) mas o logging primary será structlog → RotatingFileHandler → JSONL.

### Por que structlog e não só logging?
- structlog permite **context injection** via `contextvars` — request_id, user_id etc. são automaticamente adicionados a cada log line
- Output JSON nativo — máquina-parseável
- Bind/unbind de context — limpo e thread-safe
- Performance: `cache_logger_on_first_use=True` minimiza overhead

### Por que JSONL (1 JSON por linha)?
- `grep`, `jq`, `awk` funcionam diretamente
- Rotação por tamanho funciona naturalmente
- Não precisa de parser especializado

### Por que custom telemetry e não PostHog/Mixpanel?
- Zero dependências externas (requisito do usuário)
- Dados ficam no servidor (privacidade)
- Formato idêntico ao backend (JSONL)
- Simples: ~80 linhas de código

### Segredos nos logs
- Nunca logar: passwords, tokens JWT, API keys, session secrets
- Logar: user_id (não password), route (não body completa), status code
- Middleware de logging NÃO loga request body (só em audit para mutations)
