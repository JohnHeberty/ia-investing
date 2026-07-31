# PENDENTE — Itens a Implementar

## Prioridade Alta

> **Escopo**: Este é um sistema de **recomendação de investimentos**, não de operação/trading. Não haverá integração com broker.

### 1. ~~Integração com Broker~~ — REMOVIDO
- **Motivo**: Sistema é de recomendação, não de operação. Não há necessidade de broker.

### 2. Temporal Worker Ativo
- **Status**: Pendente
- **Descrição**: O worker do Temporal não está processando tasks. Precisa de um `temporal worker` rodando com as workflows e activities registradas.
- **Comando**: `uv run python -m apps.worker.main` ou `docker compose up worker`

### 3. Sinais Quantitativos em Tempo Real
- **Status**: Pendente
- **Descrição**: Engine de sinais (momentum, mean reversion, breakout, volume) rodando diariamente para gerar sinais de entrada/saída.
- **Fontes**: yfinance (histórico), indicadores técnicos (ta-lib ou pandas_ta)

### 4. Cache de Dados de Mercado
- **Status**: ✅ Implementado
- **Descrição**: Cache in-memory TTL para evitar chamadas excessivas ao yfinance.
- **Implementação**: `_TTLCache` em `market_data.py` com 3 caches separados:
  - Fundamentals: TTL 1h, max 256 entries
  - Analyst data: TTL 4h, max 256 entries  
  - Historical prices: TTL 15min, max 128 entries
  - Current prices: sem cache (sempre fresco)
- **Monitoramento**: `GET /api/v1/health/cache` retorna stats (hits, misses, hit_rate)
- **Resultado**: 50% hit rate em chamadas sequenciais, elimina chamadas repetidas ao yfinance

---

## Code Review Profundo — 6 Subagents (30/Jul/2026)

> Review realizado com 6 subagents em paralelo cobrindo: Hooks/Data Layer, Pages Part 1-3, Components, Config/Security/Styles.
> **Total: 67 issues identificadas** — 8 CRITICAL (corrigidos), 5 REQUIRED (corrigidos), 54 restantes documentados abaixo.

---

## Arquitetura — Debt Estrutural

### 18. 4 HTTP Clients diferentes no frontend
- **Status**: Pendente
- **Severidade**: Alta (manutenção)
- **Arquivos afetados**:
  - `web/src/lib/api-client.ts` → `institutionalApi` (openapi-fetch, quebrado por bug de headers)
  - `web/src/lib/api-client.ts` → `bffFetch` (fetch direto via BFF)
  - `web/src/hooks/use-rebalance.ts` → `apiFetch` (fetch próprio com CSRF manual)
  - `web/src/hooks/use-portfolios.ts`, `use-audit-logs.ts` → raw `fetch()` com credentials
  - `web/src/lib/candidate-api.ts` → `api()` (fetch próprio com CSRF manual)
- **Problema**: Cada um implementa CSRF, error handling, headers e base URL de forma diferente. Manutenção é um pesadelo — corrigir um bug requer mudar 4-5 arquivos.
- **Proposta**: Consolidar em `bffFetch<T>(path, init)` como único client HTTP. Remover `institutionalApi`, `apiFetch` e `api()` do candidate-api. Todos passam pelo BFF proxy que já cuida de session + CSRF.

### 19. 12 hooks usam `Record<string, unknown>` + `String()` manual
- **Status**: Pendente
- **Severidade**: Média
- **Arquivos afetados**: Todos os hooks exceto `use-portfolios.ts`
- **Problema**: Cada hook faz `fetch()` → recebe `Record<string, unknown>` → converte cada campo com `String(item.field ?? "")`. Esse padrão se repete em 12+ hooks. Se a API mudar um nome de campo, o erro só aparece em runtime (string "undefined" silenciosa).
- **Proposta**: Gerar tipos a partir do OpenAPI schema (`npm run generate:api`) e usar validação zod no boundary.

### 20. `institutionalApi` exportado mas não utilizado
- **Status**: Pendente
- **Severidade**: Baixa
- **Arquivo**: `web/src/lib/api-client.ts:21-28`
- **Problema**: `institutionalApi` (openapi-fetch client) é exportado mas nenhum hook usa mais (todos migraram para `bffFetch`). Dead code que confunde — novos devs podem usá-lo sem saber que tem bug de headers.
- **Proposta**: Remover completamente. Se openapi-fetch for necessário no futuro, corrigir o bug do `csrfFetch` primeiro.

### 21. `use-portfolios.ts` (344 linhas) — arquivo oversized
- **Status**: Pendente
- **Severidade**: Média
- **Arquivo**: `web/src/hooks/use-portfolios.ts`
- **Problema**: 344 linhas com 8 hooks, 3 interfaces, mutações e queries misturadas. Difícil de navegar e manter.
- **Proposta**: Dividir em:
  - `use-portfolios-queries.ts` (list, detail, recommendations)
  - `use-portfolios-mutations.ts` (create, addPosition, updatePosition, deletePosition, deletePortfolio)
  - `types/portfolio.ts` (interfaces compartilhadas)

### 22. `use-rebalance.ts` (259 linhas) — arquivo oversized
- **Status**: Pendente
- **Severidade**: Média
- **Arquivo**: `web/src/hooks/use-rebalance.ts`
- **Problema**: 259 linhas com 8 hooks + tipos + `apiFetch` própria. Terceira implementação de HTTP client no codebase.
- **Proposta**: Dividir em queries, mutations e tipos. Remover `apiFetch` (usar `bffFetch`).

### 23. Queries duplicadas para `/sources/health`
- **Status**: Pendente
- **Severidade**: Média
- **Arquivos afetados**:
  - `use-source-health-summary.ts` → fetch `/api/v1/sources/health`
  - `use-quality-incidents.ts` → fetch `/api/v1/sources/health` (duplicata)
  - `use-macro.ts` → fetch `/api/v1/sources/health` (terceira vez)
- **Problema**: Três hooks buscam o mesmo endpoint independentemente. React Query deduplica se montados simultaneamente, mas se um desmonta e outro monta, faz request duplo.
- **Proposta**: Criar `useSharedSourceHealth()` como provider/context, ou usar `queryKey` idêntico em todos (já fazem, mas sem garantia de montagem simultânea).

### 24. `use-audit-logs.ts` e `use-audit.ts` duplicam interface `AuditLogEntry`
- **Status**: Pendente
- **Severidade**: Baixa
- **Arquivos**:
  - `hooks/use-audit-logs.ts:5-18` — `AuditLogEntry`
  - `hooks/use-audit.ts:9-18` — `AuditEvent`
- **Problema**: Dois tipos diferentes para a mesma entidade de audit log. `AuditLogEntry` tem campos do banco; `AuditEvent` é uma view transformada.
- **Proposta**: Unificar em um tipo base `AuditLogEntry` e gerar `AuditEvent` via função `mapToAuditEvent()`.

### 25. `portfolios/[id]/page.tsx` (803 linhas) — God Component
- **Status**: Pendente
- **Severidade**: Alta
- **Arquivo**: `web/src/app/portfolios/[id]/page.tsx`
- **Problema**: 803 linhas com: data fetching, metrics computation, position CRUD UI, edit form state, delete confirmation modal, risk metrics, allocation chart, performance chart, recommendations, audit logs, 7 tabs inline.
- **Proposta**: Extrair para sub-componentes:
  - `components/portfolio/PositionsTab.tsx` (~120 linhas)
  - `components/portfolio/PerformanceTab.tsx` (~80 linhas)
  - `components/portfolio/RiskTab.tsx` (~80 linhas)
  - `components/portfolio/AllocationTab.tsx` (~60 linhas)
  - `components/portfolio/LimitsTab.tsx` (~60 linhas)
  - `components/portfolio/RecommendationsTab.tsx` (~80 linhas)
  - `components/portfolio/AuditTab.tsx` (~60 linhas)
  - `components/portfolio/ConfirmDeleteModal.tsx` (~40 linhas)
  - `components/portfolio/EditPositionForm.tsx` (~80 linhas)
  - `components/portfolio/PortfolioMetrics.tsx` (~40 linhas)

### 26. `rebalance/page.tsx` (603 linhas) — decompor sub-componentes
- **Status**: Pendente
- **Severidade**: Média
- **Arquivo**: `web/src/app/rebalance/page.tsx`
- **Problema**: 6 sub-componentes inline: `DriftBadge`, `SideBadge`, `StatusBadge`, `ProposeForm`, `DriftTable`, `TradesTable`, `ProposalDetail`, `Timeline`.
- **Proposta**: Extrair para arquivos separados em `components/rebalance/`.

### 27. `opportunity/page.tsx` (660 linhas) — decompor
- **Status**: Pendente
- **Severidade**: Média
- **Arquivo**: `web/src/app/opportunities/page.tsx`
- **Problema**: Formulário de criação (140 linhas), funnel row (40 linhas), conteúdo principal (300 linhas) misturados.
- **Proposta**: Extrair form para `components/opportunities/CreateCaseForm.tsx`.

---

## Performance

### 28. ECharts dynamic import chamado em todo render
- **Status**: Pendente
- **Severidade**: Baixa
- **Arquivos**: `use-echart.ts` (hook compartilhado)
- **Problema**: `import("echarts")` é chamado no `useEffect` a cada mudança de deps. Dynamic import é cacheado pelo browser depois da primeira vez, mas o pattern poderia ser melhor — cachear o módulo em variável de módulo.
- **Proposta**: Usar `let echartsModule: typeof import("echarts") | null = null;` no nível de módulo e popular no primeiro use.

### 29. `use-committee.ts` — N+1 pattern (1 list + N detail fetches)
- **Status**: Pendente
- **Severidade**: Média
- **Arquivo**: `web/src/hooks/use-committee.ts:66-79`
- **Problema**: `batchFetchDetails()` busca a lista de sessões (1 request) e depois busca cada detalhe individualmente (N requests com concorrência de 5). Para 50 sessões = 10 batches sequenciais.
- **Proposta**: Criar endpoint backend `GET /api/v1/committee/sessions?include_details=true` que retorna tudo de uma vez.

### 30. `use-committee.ts:96` — query key instável
- **Status**: Pendente
- **Severidade**: Média
- **Arquivo**: `web/src/hooks/use-committee.ts:96`
- **Problema**: A key inclui `sessionsQuery.data?.map(...)` que cria um novo array a cada render. Isso invalida o cache do details query a cada render, causando refetch desnecessário.
- **Proposta**: Usar `JSON.stringify(ids)` ou um hash determinístico como parte da key.

### 31. `use-committee.ts:106` — fallback para raw list items
- **Status**: Pendente
- **Severidade**: Alta (data corruption)
- **Arquivo**: `web/src/hooks/use-committee.ts:106`
- **Problema**: `(detailsQuery.data ?? sessionsQuery.data ?? [])` — se details estão carregando, usa os items brutos da lista (que não têm `agenda`, `decision`, `rationale`). O mapping de `decisions` então lê campos undefined → dados garbage silenciosos.
- **Proposta**: Retornar `[]` enquanto details estão loading, não misturar com raw list.

### 32. `page.tsx` (Dashboard) — 4 `reduce()` sem `useMemo`
- **Status**: Pendente
- **Severidade**: Baixa
- **Arquivo**: `web/src/app/page.tsx:44-60`
- **Problema**: `totalPositions`, `totalValue`, `totalCost`, `totalPnl` computados inline no render sem memoização. Cada re-render faz 4 iteractions sobre portfolios × positions.
- **Proposta**: Extrair para `useDashboardMetrics(portfolios)` hook com `useMemo`.

### 33. `portfolios/[id]/page.tsx` — `computeRiskMetrics` não memoizado
- **Status**: Pendente
- **Severidade**: Baixa
- **Arquivo**: `web/src/app/portfolios/[id]/page.tsx:17-31`
- **Problema**: `computeRiskMetrics(positions, totalValue)` faz `Math.max(...weights)` e `[...weights].sort()` a cada render. O(n log n) desnecessário.
- **Proposta**: `const riskMetrics = useMemo(() => computeRiskMetrics(positions, totalValue), [positions, totalValue])`.

### 34. `Intl.NumberFormat` reinstanciado dentro de `.map()` em 3 arquivos
- **Status**: Pendente
- **Severidade**: Baixa
- **Arquivos**:
  - `portfolios/[id]/page.tsx` (~12 vezes no JSX)
  - `portfolios/page.tsx` (~2 vezes)
  - `portfolio-ranking-table.tsx` (~3 vezes)
- **Problema**: `new Intl.NumberFormat("pt-BR", { style: "currency", currency })` criado dentro de loops de render. Cada chamada aloca um novo formatter.
- **Proposta**: Criar `const fmt = useMemo(() => new Intl.NumberFormat(...), [currency])` no nível do componente.

### 35. `use-audit.ts` — 4 `.filter()` separados no mesmo array
- **Status**: Pendente
- **Severidade**: Baixa
- **Arquivo**: `web/src/hooks/use-audit.ts:53-56`
- **Problema**: 4 filter operations percorrem `auditEvents` separadamente (correlatedEvents, overrides, integrityFailures, totalEvents).
- **Proposta**: Single reduce pass.

### 36. `use-quality-incidents.ts` — loading states combinados incorretamente
- **Status**: Pendente
- **Severidade**: Baixa
- **Arquivo**: `web/src/hooks/use-quality-incidents.ts:73`
- **Problema**: `isLoading: query.isLoading || sourceHealthQuery.isLoading` — se só sourceHealth está loading, a página inteira mostra loading spinner para incidents que já chegaram.
- **Proposta**: Loading states separados para cada seção da página.

### 37. `app-shell.tsx` — NavGroup re-renderiza a cada navegação
- **Status**: Pendente
- **Severidade**: Baixa
- **Arquivo**: `web/src/components/app-shell.tsx:52-83`
- **Problema**: `NavGroup` chama `usePathname()` e `usePermissions()` diretamente. Toda navegação re-renderiza todos os links.
- **Proposta**: Wrappar em `React.memo` e levantar pathname/permissions para AppShell, passando como props.

### 38. `portfolio-ranking-table.tsx` — 10N inline style objects por render
- **Status**: Pendente
- **Severidade**: Baixa
- **Arquivo**: `web/src/components/portfolio-ranking-table.tsx:36-98`
- **Problema**: Cada célula da tabela tem `style={{ fontFamily: "var(--font-mono)" }}`. Com 10 colunas × N linhas = 10N objects criados a cada render.
- **Proposta**: Usar classes CSS `.mono`, `.text-right`, etc. (já existem no globals.css).

### 39. `dashboard/page.tsx` — "Ver Carteiras" e "+ Nova Carteira" linkam para mesma URL
- **Status**: Pendente
- **Severidade**: Baixa
- **Arquivo**: `web/src/app/page.tsx:73-78`
- **Problema**: Botões "Ver Carteiras" e "+ Nova Carteira" apontam ambos para `/portfolios`. O segundo deveria abrir um modal de criação ou ter rota própria.

---

## Segurança

### 40. Login: CSRF token não é HMAC-signed (auto-corrected)
- **Status**: Mitigado (o backend sobrescreve o cookie com HMAC válido na primeira response)
- **Severidade**: Baixa (self-healing)
- **Arquivo**: `web/src/app/api/auth/login/route.ts:131-139`
- **Problema**: Login gera `crypto.randomUUID()` como CSRF token. Backend espera HMAC-signed. O middleware do backend sobrescreve com HMAC válido em toda response não-mutating. Se a primeira request após login for mutating (POST), CSRF falha com 403.
- **Proposta**: Gerar HMAC no login route usando a mesma chave do backend, ou simplesmente não setar o cookie no login (deixar o backend setar na primeira response).

### 41. `next.config.ts` — sem Content-Security-Policy
- **Status**: Pendente
- **Severidade**: Alta (produção)
- **Arquivo**: `web/next.config.ts`
- **Problema**: Headers HSTS, X-Frame-Options e X-XSS-Protection foram adicionados, mas **CSP não foi adicionado**. App financeiro sem CSP é vulnerável a XSS.
- **Proposta**: Adicionar CSP header com:
  - `default-src 'self'`
  - `script-src 'self' 'unsafe-eval'` (Next.js Turbopack precisa de unsafe-eval)
  - `style-src 'self' 'unsafe-inline'` (React inline styles)
  - `img-src 'self' data:` (echarts, icons)
  - `connect-src 'self' http://localhost:8000` (backend)
  - `font-src 'self'`

### 42. `candidate-api.ts` — `getCandidate` bypassa shared `api()` helper
- **Status**: Pendente
- **Severidade**: Média
- **Arquivo**: `web/src/lib/candidate-api.ts:184-204`
- **Problema**: `getCandidate()` tem sua própria lógica de fetch (sem CSRF, sem error formatting), enquanto todas as outras funções usam `api()`. Inconsistência de manutenção.
- **Proposta**: Refatorar para usar `api()` com handler customizado para extrair ETag do response.

### 43. `oidc.ts` — `safeReturnTo` rejeita hostnames não-localhost
- **Status**: Pendente
- **Severidade**: Média
- **Arquivo**: `web/src/lib/oidc.ts:193-204`
- **Problema**: `safeReturnTo()` só aceita `localhost` ou `127.0.0.1`. Em staging/prod com domínio customizado, `return_to` sempre cai no fallback `/`.
- **Proposta**: Aceitar hostnames configuráveis via env var ou whitelist.

### 44. `candidate-api.ts:32` — `return undefined as unknown as Promise<T>` (type lie)
- **Status**: Pendente
- **Severidade**: Baixa
- **Arquivo**: `web/src/lib/candidate-api.ts:32`
- **Problema**: Para responses 204, retorna `undefined` castado como `Promise<T>`. Qualquer caller que desestrutura o resultado vai crashar.
- **Proposta**: Return `null as T` ou melhor, refatorar callers para aceitar `T | null`.

---

## Dados Phantom / Placeholders hardcoded

### 45. Risk page — breaches sempre vazios
- **Status**: Pendente
- **Severidade**: Média (UX misleading)
- **Arquivo**: `web/src/app/risk/page.tsx:69-71`
- **Problema**: `assessment.breaches` é sempre `[]` (stub em `use-source-health-summary.ts:50`). A seção inteira de breaches (hard/soft), o card de concentração, e os 4 KPIs mostram zeros ou "nenhum ativo" — dados phantom que parecem reais.
- **Proposta**: Conectar a `GET /api/v1/risk-assessments/{id}/breaches` ou remover as seções.

### 46. Risk page — cenários hardcoded
- **Status**: Pendente
- **Severidade**: Média
- **Arquivo**: `web/src/app/risk/page.tsx:73-78`
- **Problema**: `ScenarioWaterfall` recebe 4 cenários fixos ("Choque de juros", "Elevação cambial", etc.) sem connection com a API.
- **Proposta**: Buscar de `stress_results` endpoint ou remover.

### 47. Risk page — "97% da carteira é liquidável"
- **Status**: Pendente
- **Severidade**: Média (misleading)
- **Arquivo**: `web/src/app/risk/page.tsx:180`
- **Problema**: Texto estático hardcoded. `assessment.liquidity` é `{ healthy_sources: healthyCount }` — stub. O valor "97%" não tem backing real.
- **Proposta**: Calcular de dados reais ou usar placeholder honesto ("Dados de liquidez indisponíveis").

### 48. Backtests page — Sharpe Ratio sempre "—"
- **Status**: Pendente
- **Severidade**: Baixa
- **Arquivo**: `web/src/app/backtests/page.tsx:99-102`
- **Problema**: Métrica "Sharpe mediano" sempre mostra "—" porque não computa median.
- **Proposta**: Calcular median do array `runs.map(r => r.sharpeRatio)` ou remover.

### 49. Policy page — "Diffs novos" hardcode "3"
- **Status**: Pendente
- **Severidade**: Baixa
- **Arquivo**: `web/src/app/policy/page.tsx:106`
- **Problema**: `Math.min(materialEvents.length, 3)` mostra "3" como valor fixo para "Diffs novos".
- **Proposta**: Usar `materialEvents.length` real.

### 50. Paper page — Slippage sempre "—"
- **Status**: Pendente
- **Severidade**: Baixa
- **Arquivo**: `web/src/app/paper/page.tsx:111`
- **Problema**: Métrica "Slippage" sempre mostra "—" sem dados reais.
- **Proposta**: Calcular de fill data ou remover placeholder.

### 51. Audit page — `.slice(0, 15)` esconde eventos sem aviso
- **Status**: Pendente
- **Severidade**: Média (UX misleading)
- **Arquivo**: `web/src/app/audit/page.tsx:137`
- **Problema**: Header mostra "X eventos" mas a tabela só exibe 15. Usuário não sabe que o restante está escondido.
- **Proposta**: Adicionar "…e mais N eventos" no footer ou paginação.

---

## Dados / Hooks

### 52. `use-source-health-summary.ts` — timestamp fake impede stale detection
- **Status**: Pendente
- **Severidade**: Média
- **Arquivo**: `web/src/hooks/use-source-health-summary.ts:49,60`
- **Problema**: Hook sintetiza `as_of: new Date().toISOString()` como timestamp do assessment. `computeDataState` recebe este timestamp fake e sempre retorna "ready" — dados stale nunca são detectados.
- **Proposta**: Usar o `as_of` real da resposta da API ou `null`.

### 53. `use-macro.ts` — `selic`/`ipca`/`usdBrl` podem ser `undefined`
- **Status**: Pendente
- **Severidade**: Média
- **Arquivo**: `web/src/hooks/use-macro.ts:56-64`
- **Problema**: `.find()` retorna `undefined` se não encontrar. Se a página desestrutura `{ selic: { value } }`, crasha.
- **Proposta**: Tipar como `MacroSeries | undefined` e usar optional chaining no consumer.

### 54. `use-audit-logs.ts` — entry.metadata assume formato flat
- **Status**: Pendente
- **Severidade**: Baixa
- **Arquivo**: `web/src/hooks/use-audit.ts:54`
- **Problema**: `(entry.metadata as Record<string, unknown>)?.correlation_id` assume que metadata é um objeto flat com `correlation_id`. Se o backend retornar `{ trace: { correlation_id: "..." } }`, produz `""` silenciosamente.
- **Proposta**: Validar formato com zod ou buscar em nested paths.

### 55. `use-committee.ts` — `d.decidedBy` nunca preenchido
- **Status**: Pendente
- **Severidade**: Baixa
- **Arquivo**: `web/src/hooks/use-committee.ts:111-127`
- **Interface**: `CommitteeDecision.decidedBy: string`
- **Problema**: A propriedade existe na interface mas nunca é populada pelo mapping. Sempre `undefined`.
- **Proposta**: Popular de `session.agenda.requested_by` ou remover da interface.

### 56. `data-quality/page.tsx` — `FreshnessPill` import não usado
- **Status**: Pendente
- **Severidade**: Baixa (dead code)
- **Arquivo**: `web/src/app/data-quality/page.tsx:11`
- **Problema**: `FreshnessPill` importado mas nunca renderizado.
- **Proposta**: Remover import.

### 57. `data-quality/page.tsx` — `urlState` desestruturado mas não lido
- **Status**: Pendente
- **Severidade**: Baixa (dead code)
- **Arquivo**: `web/src/app/data-quality/page.tsx:16`
- **Problema**: `const [urlState] = useUrlState(filterPresets.dataQuality)` — `urlState` nunca é acessado.
- **Proposta**: Remover ou conectar os filtros de URL à UI.

### 58. `risk/page.tsx` — `urlState` desestruturado mas não lido
- **Status**: Pendente
- **Severidade**: Baixa (dead code)
- **Arquivo**: `web/src/app/risk/page.tsx:17`
- **Problema**: Mesmo caso que item 57.
- **Proposta**: Remover.

### 59. `opportunity/page.tsx` — `useUrlState` import não usado
- **Status**: Pendente
- **Severidade**: Baixa (dead code)
- **Arquivo**: `web/src/app/opportunities/page.tsx:308`
- **Problema**: `useUrlState(filterPresets.opportunities)` chamado mas `urlState`/`setUrlState` nunca usados.
- **Proposta**: Remover.

### 60. `opportunity/page.tsx` — `setTimeout` sem cleanup
- **Status**: Pendente
- **Severidade**: Baixa
- **Arquivo**: `web/src/app/opportunities/page.tsx:103-106`
- **Problema**: `setTimeout` para auto-close após 1500ms não tem cleanup no unmount. Se componente desmonta antes do timeout, setState em unmounted component warning.
- **Proposta**: Usar `useEffect` return cleanup ou ref check.

### 61. `data-quality/page.tsx:70` — "Quarentena" é hardcoded como status "open + high"
- **Status**: Pendente
- **Severidade**: Baixa (misleading)
- **Arquivo**: `web/src/app/data-quality/page.tsx:70`
- **Problema**: Métrica "Quarentena" conta `status === "open" && severity === "high"` — não são objetos realmente em quarentena.
- **Proposta**: Renomear para "Incidentes Críticos" ou implementar filtro de quarentena real.

### 62. `committee/page.tsx:185` — `d.decidedBy` sempre undefined no ApprovalCard
- **Status**: Pendente
- **Severidade**: Baixa
- **Arquivo**: `web/src/app/committee/page.tsx:185`
- **Problema**: Passa `decidedBy={d.decidedBy}` mas o hook nunca popula (ver item 55).
- **Proposta**: Consertar no hook ou usar fallback.

---

## UX / Formulários

### 63. `portfolios/[id]/page.tsx:322` — NaN injection no edit form
- **Status**: Pendente
- **Severidade**: Média
- **Arquivo**: `web/src/app/portfolios/[id]/page.tsx:322-325`
- **Problema**: `parseFloat(editForm.quantity)` sem validação. Se o campo estiver vazio ou com texto, `NaN` é enviado ao backend.
- **Proposta**: Validar `!isNaN(value) && value > 0` antes de submit.

### 64. `create-portfolio-form.tsx:30` — `parseFloat(initialCapital)` sem NaN guard
- **Status**: Pendente
- **Severidade**: Baixa
- **Arquivo**: `web/src/components/create-portfolio-form.tsx:30`
- **Problema**: Se `initialCapital` for texto, parseFloat retorna NaN.
- **Proposta**: `const cap = parseFloat(initialCapital); isNaN(cap) ? undefined : cap`.

### 65. `add-position-form.tsx:28-29` — parseFloat sem NaN guard
- **Status**: Pendente
- **Severidade**: Baixa
- **Arquivo**: `web/src/components/add-position-form.tsx:28-29`
- **Mesmo problema** que item 63/64.
- **Proposta**: Validar antes de submit.

### 66. `domain.tsx:45` — trailing space no className do Metric
- **Status**: Pendente
- **Severidade**: Baixa
- **Arquivo**: `web/src/components/domain.tsx:45`
- **Problema**: `` `${tone ?? ""}` `` produz `"metric-value "` quando tone é undefined.
- **Proposta**: Usar ternário: `tone ? \`metric-value ${tone}\` : "metric-value"`.

### 67. `decision-components.tsx:93` — `Math.max` com spread de array vazio
- **Status**: Pendente
- **Severidade**: Baixa
- **Arquivo**: `web/src/components/decision-components.tsx:93`
- **Problema**: `Math.max(...scenarios.map(...), 1)` — se scenarios for vazio, retorna -Infinity.
- **Proposta**: Early return para array vazio.

---

## Backend (complementar)

### 68. `portfolio_advisor.py:337` — `performance_outlook` hardcoded
- **Status**: Pendente
- **Severidade**: Baixa
- **Arquivo**: `src/ia_investing/agents/portfolio_advisor.py:337`
- **Problema**: `expected_return_12m: 0.08` é sempre 8% independente do portfolio ou dos scores.
- **Proposta**: Calcular como média ponderada dos scores de momentum dos ativos.

### 69. `paper_portfolio.py:50-52` — N+1 query em `list_all()`
- **Status**: Pendente
- **Severidade**: Média (performance)
- **Arquivo**: `src/ia_investing/application/paper_portfolio.py:50-52`
- **Problema**: Uma query por portfolio para buscar posições. 50 portfolios = 51 queries.
- **Proposta**: Batch-fetch: `SELECT * FROM positions WHERE portfolio_id IN (...)` e agrupar em Python.
