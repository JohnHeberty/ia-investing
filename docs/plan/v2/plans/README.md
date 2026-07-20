# Planos de execução — IA Investing OS v2

Este diretório transforma o roadmap do [plano mestre](../PLAN.md) em planos de implementação incrementais. O plano mestre continua sendo a fonte de verdade para arquitetura, produto e governança; estes arquivos definem a ordem de entrega, os gates e a validação de cada fase.

## Como usar

Execute as fases em ordem. Uma fase só pode começar quando seus critérios de entrada estiverem satisfeitos e só termina após todos os critérios de saída. Dentro de uma fase, cada item `F<n>-PR<nn>` representa um pull request pequeno, revisável e reversível e possui um checklist atômico próprio. O Dev deve concluir e validar todos os itens do bloco antes de considerar o PR pronto; um PR não deve misturar mudanças de fases diferentes.

| Fase | Plano | Gate principal |
| ---: | --- | --- |
| 0 | [Congelamento e baseline](00-fase-0-congelamento-e-baseline.md) | Baseline registrado |
| 1 | [Sistema executável](01-fase-1-sistema-executavel.md) | Fluxo CVM mockado ponta a ponta |
| 2 | [Confiança dos dados](02-fase-2-confianca-dos-dados.md) | Consulta histórica point-in-time reproduzível |
| 3 | [Domínio de pesquisa](03-fase-3-dominio-de-pesquisa.md) | Recomendação explicável por evidência e versão |
| 4 | [Framework de agents](04-fase-4-framework-de-agents.md) | Outputs avaliados, citáveis e governados |
| 5 | [Carteiras, risco e backtest](05-fase-5-carteiras-risco-e-backtest.md) | Carteira/NAV reproduzíveis e backtest sem look-ahead |
| 6 | [Painel MVP](06-fase-6-painel-mvp.md) | Jornada de decisão completa e auditável |
| 7 | [Inteligência política e macro](07-fase-7-inteligencia-politica-e-macro.md) | Evento rastreável da fonte à carteira |
| 8 | [Operação paper institucional](08-fase-8-operacao-paper-institucional.md) | Operação paper autônoma e reconciliada |
| 9 | [Produção controlada](09-fase-9-producao-controlada.md) | Decisão formal de go/no-go para desenhar execução live |

## Regras transversais

- Preservar `effective_at`, `published_at`, `knowledge_at`, `valid_from`, `valid_to` e `revision_number` em todo dado temporal.
- Tratar fatos canônicos como determinísticos; agents interpretam ambiguidades e nunca escrevem diretamente em fatos, posições ou ordens.
- Comandos longos retornam `202 Accepted`, usam `Idempotency-Key` e são executados por Temporal.
- Mudanças de banco são feitas somente por Alembic; cada migration possui upgrade, downgrade testado e estratégia de compatibilidade.
- Claims materiais exigem `evidence_id`; ausência, zero, erro de parsing e não aplicável são estados distintos.
- Eventos de auditoria são append-only e carregam ator, ação, recurso, razão e `correlation_id`.
- Nenhuma entrega está concluída sem testes, telemetria, documentação, tratamento de dado parcial, runbook e rollback aplicáveis.

## Dependências entre fases

```text
F0 -> F1 -> F2 -> F3 -> F4 -> F5 -> F6 -> F7 -> F8 -> F9
```

O design system da Fase 6 pode ser prototipado após os contratos da Fase 1, com mocks versionados. A integração de dados reais no painel continua bloqueada pelos gates das Fases 2–5. A Fase 9 não autoriza integração com corretora nem envio de ordens reais.

## Mapeamento dos PRs iniciais do plano mestre

| PRs do plano mestre | Fase de implementação | Observação |
| --- | --- | --- |
| PR-001 a PR-006 e PR-008 | Fase 1 | Estabilização, contratos, Temporal e infraestrutura |
| PR-009 e PR-010 | Fase 2 | Source Registry, Raw Zone e fatos financeiros |
| PR-011 | Fase 3 | Domínio de pesquisa |
| PR-007 | Fase 4 | Runtime completo; a Fase 1 entrega somente o mock E2E |
| PR-012 e PR-013 | Fase 5 | Identidade institucional antes de carteira/risco |
| PR-014 e PR-015 | Fase 6 | Web shell, design system e primeiros painéis |

As Fases 0 e 7–9 introduzem PRs próprios que não constam na lista inicial da seção 29.

## Definition of Done comum

Para cada PR, registrar requisito, decisão de domínio, impacto de schema/migration, autorização, auditoria, telemetria, testes e rollback. Para cada fase, publicar evidências dos critérios de aceite, atualizar ADRs e runbooks e manter um backlog explícito de débitos que não bloqueiam o gate seguinte.

## Auditoria de implementação

**Última auditoria:** 2026-07-19 (commit `92e2981`)

| Fase | Artefatos verificados | Implementação real | Stubs | Pendências |
|:---:|:---:|:---:|:---:|:---|
| 0 | 7/7 | 7 | 0 | ~~Review técnico~~ ✅ Concluído (2026-07-19) |
| 1 | 6/6 | 6 | 0 | E2E integration, contract round-trip tests |
| 2 | 5/5 | 5 | 0 | Golden tests multi-setoriais, dashboards qualidade |
| 3 | 5/5 | 5 | 0 | E2E workflow, contract tests handlers |
| 4 | 3/3 | 3 | 0 | Tracing correlation, dashboards, shadow runs |
| 5 | 4/4 | 4 | 0 | Walk-forward/out-of-sample, ranking eligibility |
| 6 | 2/2 | 2 | 0 | Integração API real, Storybook, component tests |
| 7 | 3/3 | 3 | 0 | DOU/Reguladores, probabilidade calibrada |
| 8 | 3/3 | 3 | 0 | Simulator golden tests, kill switch drills |
| 9 | 2/2 | 0 | 2 | **threat-model.md** e **bcp-dr.md** são stubs |

**Total:** 40/40 artefatos existem. 38/40 são implementações reais. 2 stubs em Fase 9 (readiness docs).

## Auditoria de implementação (2026-07-19, atualizado 2026-07-19)

**Fase 0 CONCLUÍDA.** Licenciamento resolvido (PDF removido), ADRs revisados e referências atualizadas.
