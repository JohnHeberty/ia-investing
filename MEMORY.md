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
- [ ] **Evals source discovery** — datasets criados, falta DB seeding
- [ ] **Observabilidade** — dashboards não implementados
- [ ] **Conectores avançados** — sitemap/RSS/institutional site resolvers

### Issues de código conhecidos
Ver `fix/PENDENCIAS.md` para lista completa e priorizada.

### Melhorias desejáveis
Ver `fix/PENDENCIAS.md` seção "Melhorias de infra/qualidade".
