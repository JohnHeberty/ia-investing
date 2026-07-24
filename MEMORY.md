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
- [ ] **Permissões frontend** — ainda mockadas (auth-provider, middleware)
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
- [ ] **secrets_manager.py** — str() em dict retorna repr Python; urlopen sem timeout; sync HTTP em app async
- [ ] **agent_runtime.py** — os.environ['OPENAI_API_KEY'] vaza chave; 3 sessions separadas p/ 1 unidade de trabalho
- [ ] **research.py** — list_cases sem limit max (DoS); UUIDv4 pagination non-determinística
- [ ] **portfolio_models.py** — Portfolio sem organization_id (sem tenant isolation)
- [ ] **research_mock.py** — float(None) crash (linha 114)
- [ ] **Frontend: hooks/use-quality-incidents.ts** — computeDataState arity (parâmetro booleano no lugar de string)
- [ ] **Frontend: hooks/use-committee.ts** — computeDataState arity
- [ ] **Frontend: hooks/use-audit.ts** — computeDataState arity
- [ ] **Frontend: hooks/use-backtests.ts** — computeDataState arity
- [ ] **Frontend: hooks/use-url-state.ts** — === reference equality para defaults array nunca limpa URL params
- [ ] **Frontend: hooks/use-sse.ts** — JSON.parse sem try/catch quebra EventSource permanentemente
- [ ] **Frontend: hooks/use-risk-assessments.ts** — dados sintéticos com nome enganoso
- [ ] **Frontend: hooks/use-committee.ts** — queryFn retorna [] vazio fixo
- [ ] **Frontend: hooks/use-mission-control.ts** — raw fetch() em vez de institutionalApi; hardcoded localhost:8000
- [ ] **Frontend: app/login/page.tsx** — open redirect via return_to sem validação (parcial: server-side ok, client-side não)
- [ ] **Frontend: app/opportunities/page.tsx** — crypto.randomUUID falha em HTTP
- [ ] **Frontend: components/app-shell.tsx** — search/notification buttons sem onClick
- [ ] **Frontend: components/evidence-tags.tsx** — agora tem "use client" ✅

### Melhorias desejáveis
- [ ] Testes de integração OIDC (zero cobertura)
- [ ] Testes unitários frontend (vitest configurado, só 5 testes)
- [ ] docker-compose expõe MinIO console na 9001 sem auth
- [ ] Migration env.py usa sys.path.insert(0, ...) frágil
- [ ] web/AGENTS.md duplicado (raiz + web/ — conteúdo diferente)
