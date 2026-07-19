# Fase 6 — Painel MVP

[Índice](README.md) · [Fase anterior](05-fase-5-carteiras-risco-e-backtest.md) · [Plano mestre](../PLAN.md)

## Objetivo e resultado esperado

Entregar uma estação de trabalho institucional em que um usuário autorizado percorra oportunidade, evidências, tese, valuation, risco, proposta, comitê, carteira e auditoria sem perder contexto, temporalidade ou qualidade dos dados.

## Critérios de entrada

- APIs e contratos de pesquisa, agents, carteira e risco versionados.
- OIDC/RBAC+ABAC, operações assíncronas, SSE e auditoria disponíveis.
- Dados reais só entram após os gates das Fases 2–5; mocks OpenAPI podem antecipar componentes.

## Estado atual e lacunas

Não existe frontend no repositório. A API ainda precisa ser consumida por client gerado e os papéis/telas do plano mestre não foram materializados. O principal risco é transformar dado stale/parcial em dashboard aparentemente confiável.

## Escopo e limites

Criar app Next.js/React/TypeScript, design system, app shell, Mission Control, Top carteiras, Portfolio 360, Asset 360, Oportunidades, Risk Center, Committee Room, Agent Operations e Data Quality Center. Backtest Lab pode entrar como leitura/submissão mínima. Mobile cobre monitoramento, alertas, resumos, aprovações permitidas e posições; não replica a estação desktop. Execução paper detalhada entra na Fase 8.

## Workstreams técnicos

### Fundação e identidade

Criar app separado com TanStack Query/Table, Radix, tokens CSS/Tailwind, ECharts, React Hook Form, Zod, client OpenAPI, Storybook, Vitest/Testing Library, Playwright e axe-core. Integrar OIDC; aplicar RBAC+ABAC por organização, equipe, carteira, classificação, estado e ambiente. UI oculta ações não permitidas, mas backend continua sendo autoridade.

### Design system institucional

Implementar temas claro/escuro, grid desktop, tipografia tabular e cores semânticas que não dependem só de vermelho/verde. Componentes centrais incluem badges de mandato/estágio/evidência/freshness, qualidade/confiança, tese/risco/materialidade, fact-inference-recommendation tags, source drawer, timelines, portfolio diff, scenario waterfall, approvals e `AsOfIndicator`.

### Leitura operacional

Mission Control agrega Top X comparáveis, brief diário, eventos, funil e pendências. Portfolio 360 apresenta visão geral, posições, performance, atribuição, risco, teses, eventos, rebalanceamento e auditoria. Asset 360 apresenta métricas/proveniência, valuation, tese, notícias/política e pares. Toda consulta mostra `as_of`, fonte, freshness e qualidade.

### Decisão e operações

Oportunidades suportam triagem e abertura de caso. Committee Room congela decision pack, votos, dissenso, condições e assinaturas. Agent Operations mostra runs, versões, tools, custo, tracing e approvals. Data Quality permite triagem/resolução conforme papel, nunca edição direta de raw/fato.

### Assincronismo e estados

Usar SSE para operações/notificações e polling de fallback. Filtros ficam na URL. Toda tela trata loading, empty, partial, stale, quarantined, no permission, source/model unavailable, calculation failed, no/conflicting evidence e awaiting approval. Zero só aparece quando for valor conhecido.

## Interfaces frontend/backend

- Gerar client a partir do OpenAPI fixado no build; diff incompatível falha CI.
- Datas são apresentadas no timezone da organização; dinheiro permanece decimal/string até formatação.
- Commands enviam `Idempotency-Key` e `If-Match`; respostas 202 alimentam status via SSE.
- Deep links preservam organização, recurso, aba e `as_of`, sem incluir secrets.
- Feature flags controlam telas/capabilities incompletas e devem ser avaliadas no servidor para ações sensíveis.

## Sequência de pull requests

| PR | Conteúdo | Origem no plano mestre |
| --- | --- | --- |
| `F6-PR01` | Next.js, client OpenAPI, auth, shell e CI frontend | PR-014 |
| `F6-PR02` | Tokens, temas, componentes e Storybook | PR-014 |
| `F6-PR03` | Estados comuns, SSE, notificações e URL filters | Design 13.7/13.8 |
| `F6-PR04` | Mission Control e Top carteiras | PR-015 |
| `F6-PR05` | Portfolio 360 e Risk Center | Telas 12.3/12.7 |
| `F6-PR06` | Asset 360 e Oportunidades | Telas 12.4/12.5 |
| `F6-PR07` | Committee Room e approvals | Tela 12.8 |
| `F6-PR08` | Agent Operations e Data Quality Center | Telas 12.9/12.10 |
| `F6-PR09` | Jornada E2E, acessibilidade, responsividade e hardening | Gate da Fase 6 |

## Checklist detalhado de implementação

### `F6-PR01` — Fundação web

- [x] Criar workspace/app Next.js com TypeScript strict e comandos canônicos.
- [x] Configurar lint, format, type check, Vitest, Playwright e build no CI.
- [x] Gerar client a partir de uma versão fixada do OpenAPI.
- [x] Integrar OIDC, refresh/logout e contexto de organização/timezone.
- [x] Criar app shell, sidebar, topbar, rotas protegidas e error boundary.
- [x] Garantir que nenhum secret/config de serviço entre no bundle.
- [ ] Criar smoke test de login, rota protegida e client autenticado.

### `F6-PR02` — Design system

- [x] Implementar tokens de cor, spacing, radius, shadow e tipografia.
- [x] Implementar temas claro/escuro e números tabulares.
- [x] Criar primitives acessíveis com Radix e estados de foco/teclado.
- [ ] Criar componentes de domínio listados no plano mestre.
- [x] Representar semântica com texto/ícone/padrão além de cor.
- [ ] Documentar props, estados e exemplos no Storybook.
- [ ] Adicionar visual regression e axe para cada componente crítico.

### `F6-PR03` — Estado de dados e assincronismo

- [x] Configurar TanStack Query, cache keys e invalidação por recurso/`as_of`.
- [x] Implementar cliente SSE com reconnect, last-event ID e fallback polling.
- [ ] Implementar URL state para filtros, ordenação, paginação e abas.
- [ ] Criar componentes para todos os estados obrigatórios.
- [ ] Diferenciar zero, missing, stale, partial e quarantined.
- [x] Propagar correlation ID e Problem Details para suporte autorizado.
- [ ] Testar reconnect, duplicate event, cache stale e operação falha.

### `F6-PR04` — Mission Control e Top carteiras

- [ ] Integrar agregação de mission control via query dedicada.
- [ ] Renderizar rankings separados por categoria comparável.
- [ ] Exibir estágio, retorno/risco, confiança, teses, decisão e freshness.
- [ ] Implementar brief, eventos críticos, funil e pendências.
- [ ] Criar filtros persistidos e comparação de carteiras elegíveis.
- [ ] Não exibir carteira inelegível como top nem misturar moedas/horizontes.
- [ ] Cobrir loading/empty/partial/stale/no permission em testes.

### `F6-PR05` — Portfolio 360 e Risk Center

- [ ] Implementar abas de visão, posições, performance, atribuição e risco.
- [ ] Implementar teses, eventos, rebalanceamento e auditoria.
- [ ] Exibir benchmark, NAV reconciliado, `as_of` e metodologia.
- [ ] Exibir limits, breaches, exposures, stresses e waivers.
- [ ] Implementar actions autorizadas para stress/breach/proposal.
- [ ] Exibir portfolio diff e constraints antes de submit/approval.
- [ ] Testar dinheiro/percentual/timezone e datasets grandes de posições.

### `F6-PR06` — Asset 360 e Oportunidades

- [ ] Implementar cabeçalho com instrumento/listagem temporal e status.
- [ ] Exibir summary, métricas/provenance, valuation e cenários.
- [ ] Exibir tese/versões, evidence, notícias/política e pares.
- [ ] Implementar funil e origem/materialidade de oportunidades.
- [ ] Permitir abrir caso sem duplicar oportunidade/caso existente.
- [ ] Exigir permissão e idempotency key em commands.
- [ ] Testar no evidence, conflicting evidence e valuation failed.

### `F6-PR07` — Committee Room

- [ ] Implementar agenda, quórum, conflitos e decision pack congelado.
- [ ] Exibir tese, valuation, risco, proposta, dissenso e condições.
- [ ] Implementar votos permitidos e confirmação explícita da versão.
- [ ] Impedir autoaprovação/quórum inválido e voto após encerramento.
- [ ] Exibir assinatura/hash, timeline e resultado final.
- [ ] Tratar concorrência com ETag/If-Match.
- [ ] Criar E2E de aprovação, rejeição e decisão condicionada.

### `F6-PR08` — Agents e Data Quality

- [ ] Exibir runs, versões, status, custo, tokens, tracing e tool calls.
- [ ] Exibir output, citations, contradictions, guardrails e approvals.
- [ ] Permitir approve/reject/cancel somente conforme policy.
- [ ] Exibir freshness, completude, quarentena e incidentes por fonte.
- [ ] Implementar acknowledge/resolve/waive sem editar fatos diretamente.
- [ ] Vincular incidente ao raw/parser/fato/métrica impactados.
- [ ] Testar dados sensíveis, no permission e source/model unavailable.

### `F6-PR09` — Jornada, acessibilidade e hardening

- [ ] Automatizar os dez passos da jornada de aceite em Playwright.
- [x] Executar axe e navegação somente por teclado nas telas críticas.
- [ ] Validar contraste, zoom, leitores de tela e não dependência de cor.
- [x] Validar desktop 1440+, tablet e escopo mobile aprovado.
- [x] Executar visual regression em temas e estados de erro.
- [ ] Medir performance/bundle/web vitals e corrigir regressões críticas.
- [ ] Validar auth expiry, SSE outage, API partial failure e feature rollback.
- [ ] Publicar runbook de deploy, flags, incidente e suporte.

## Rollout e rollback

Publicar shell e componentes atrás de feature flags, primeiro com mocks versionados e depois por capability real. Liberar a usuários internos/papéis selecionados antes da expansão. Client e API seguem compatibilidade aditiva; breaking change exige versão. Rollback desativa flag ou reverte bundle, sem alterar decisões já persistidas. Erro visual nunca dispara repetição automática de command sem mesma idempotency key.

## Segurança, observabilidade e falhas

- Nenhuma chave sensível, token de serviço ou payload confidencial entra no bundle/log do navegador.
- Registrar web vitals, erros, latência de query, falhas SSE, command outcomes e correlation IDs, respeitando privacidade.
- Aprovações pedem confirmação, exibem impacto/versão e registram razão quando exigido.
- `no permission` não revela existência/conteúdo do recurso.
- Source/model/calculation failure exibe estado acionável e link para incidente autorizado.

## Testes e critérios de aceite

- Storybook e visual regression para componentes/temas/estados.
- Unit/component tests para formatação financeira, permissões, filtros e commands idempotentes.
- axe-core e testes de teclado/contraste em fluxos críticos.
- Playwright cobre login, oportunidade, caso, evidência, tese, valuation, risco, proposta, voto, atualização e auditoria.
- Contract tests validam client gerado, Problem Details, SSE reconnect e concorrência ETag.
- Viewports desktop, tablet e mobile cobrem o escopo definido sem ocultar freshness/qualidade.

## Critérios de saída

- [ ] Usuário autorizado conclui os dez passos da jornada de aceite.
- [ ] Toda métrica/decisão material expõe fonte, `as_of`, qualidade e auditoria.
- [ ] Top X compara apenas carteiras elegíveis da mesma categoria.
- [ ] Permissões são coerentes entre frontend e API.
- [ ] Estados obrigatórios existem em todas as telas críticas.
- [ ] Acessibilidade, visual regression e E2E passam no CI.
- [ ] Runbooks cobrem auth, SSE, feature flags e falhas de dependência.

## Riscos e passagem para a Fase 7

O risco é otimizar aparência antes da confiabilidade. Nenhum mock pode ser indistinguível de dado real fora de desenvolvimento. A Fase 7 reutiliza Asset 360, timeline, matriz de exposição e componentes de provenance para política/macro.

## Auditoria de implementação (2026-07-19)

Web frontend Next.js implementado com: 15+ page routes (agents, assets, audit, backtests, committee, data-quality, login, macro, opportunities, paper, policy, portfolios, risk), app-shell com sidebar e theme toggle (135 lines), dashboard page (173 lines), Radix/TanStack/ECharts deps, Playwright e2e, visual regression screenshots. Pendências: integração API real com client gerado, Storybook, URL state, componentes de domínio customizados, testes unitários de componentes, jornada E2E completa.
