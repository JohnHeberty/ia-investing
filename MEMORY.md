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

### De FIX/File.md (features não implementadas)
- [ ] **Mission Control candidatos** — frontend
- [x] **Permissões frontend** — implementado (hook + Can + sidebar filtrado + logout)
- [ ] **Evals source discovery** — datasets não criados
- [ ] **Observabilidade** — dashboards não implementados
- [ ] **Conectores avançados** — sitemap/RSS/institutional site resolvers

### Issues de código conhecidos (não corrigidos)
- [ ] **operations.py** — TOCTOU idempotência (organization_id=NULL quebra UNIQUE), crash window (workflow inicia antes do commit)
- [ ] **audit_service.py** — concorrência hash chain (non-atomic read-then-write), flush side-effect na transaction do caller
- [ ] **source_registry.py** — TOCTOU register_source() e license creation (IntegrityError não tratado)
- [ ] **metrics.py** — divisão por zero com dependências vazias; SQL IN () retorna falso
- [ ] **portfolio.py** — optimize() sem with_for_update; close_price NULL causa TypeError; JOIN sem DISTINCT
- [ ] **portfolio_ranking_materializer.py** — UPSERT com WHERE suprime RETURNING; validação [0,1] mascara bugs
- [ ] **egress.py** — socket leak (sem context manager); blocking socket em async app; IPv4-only
- [x] **agent_runtime.py** — os.environ['OPENAI_API_KEY'] vaza chave; 4 sessions separadas p/ 1 unidade de trabalho ✅ (commit 9719188)
- [ ] **research.py** — list_cases sem limit max (DoS); UUIDv4 pagination non-determinística
- [ ] **portfolio_models.py** — Portfolio sem organization_id (sem tenant isolation)
- [ ] **research_mock.py** — float(None) crash (linha 114)
- [x] **Frontend: hooks/use-quality-incidents.ts** — computeDataState arity ✅ (commit 9719188)
- [x] **Frontend: hooks/use-committee.ts** — computeDataState arity + queryFn retorna [] vazio ✅ (commit 9719188)
- [x] **Frontend: hooks/use-audit.ts** — computeDataState arity ✅ (commit 9719188)
- [x] **Frontend: hooks/use-backtests.ts** — computeDataState arity ✅ (commit 9719188)
- [x] **Frontend: hooks/use-url-state.ts** — reference equality para defaults array ✅ (commit 9719188)
- [x] **Frontend: hooks/use-sse.ts** — JSON.parse sem try/catch ✅ (commit 9719188)
- [ ] **Frontend: hooks/use-risk-assessments.ts** — dados sintéticos com nome enganoso
- [x] **Frontend: hooks/use-mission-control.ts** — hardcoded localhost:8000 ✅ (commit 9719188)
- [x] **Frontend: app/login/page.tsx** — open redirect via return_to sem validação ✅ (commit 9719188)
- [x] **Frontend: app/opportunities/page.tsx** — crypto.randomUUID sem fallback ✅ (commit 9719188)
- [x] **Frontend: components/app-shell.tsx** — search/notification buttons sem type ✅ (commit 9719188)
- [x] **Backend: metrics.py** — DivisionByZero + SQL IN() vazio ✅ (commit 9719188)
- [x] **Backend: egress.py** — socket bloqueante + AF_INET hardcoded ✅ (commit 9719188)
- [x] **Backend: secrets_manager.py** — str(dict) + urlopen sem timeout ✅ (commit 9719188)
- [x] **Backend: operations.py** — crash window (workflow antes de commit) + TOCTOU ✅ (commit 9719188)
- [x] **Backend: audit_service.py** — hash chain fork race ✅ (commit 9719188)
- [x] **Backend: portfolio.py** — TOCTOU + NULL close_price + JOIN sem DISTINCT ✅ (commit 9719188)
- [x] **Permissions frontend** — use-permissions hook + Can components + sidebar ✅ (commit 9719188)
- [x] **Evals: company_source_discovery** — 6 cases + seed script + test suite ✅ (commit 9719188)
- [x] **proxy.ts** — deletado (substituído por middleware.ts) ✅ (commit 9719188)

### Melhorias desejáveis
- [ ] Testes de integração OIDC (zero cobertura)
- [ ] Testes unitários frontend (vitest configurado, só 5 testes)
- [ ] docker-compose expõe MinIO console na 9001 sem auth
- [ ] Migration env.py usa sys.path.insert(0, ...) frágil
- [ ] web/AGENTS.md duplicado (raiz + web/ — conteúdo diferente)
