# Fase 7 — Inteligência política e macro completa

[Índice](README.md) · [Fase anterior](06-fase-6-painel-mvp.md) · [Plano mestre](../PLAN.md)

## Objetivo e resultado esperado

Conectar eventos macroeconômicos, legislativos, regulatórios e oficiais a drivers operacionais, métricas, empresas, teses e carteiras, com fonte, versão, probabilidade, incerteza e revisão humana explícitas.

## Critérios de entrada

- Source Registry, Raw Zone, evidence e temporalidade aprovados.
- Political/Macro agents governados, com tools e evals da Fase 4.
- Pesquisa, valuation, carteiras e painel aceitam eventos/impactos versionados.

## Estado atual e lacunas

Há conectores BCB/SIDRA e análise macro inicial, mas não existe cobertura completa de Câmara, Senado, DOU e reguladores, nem identidade/versionamento jurídico, policy graph, base rates, mapeamento setorial e propagação à carteira. O painel ainda não possui dados políticos reais integrados.

## Escopo e limites

Implementar conectores/contratos para Câmara, Senado, DOU e reguladores priorizados; aprofundar BCB/SIDRA; criar policy graph, probabilidades com intervalo, exposições setor/empresa/carteira, cenários e dashboard. Não inferir probabilidade como fato nem automatizar mudança de tese/carteira; impacto material sempre abre revisão humana.

## Workstreams técnicos

### Fontes e normalização

Registrar fonte, licença, rate limit, schema/SLA e fixtures por Câmara, Senado, DOU, reguladores, BCB e SIDRA. Descobrir proposição/ato, versões, tramitação, autores/relatores, pauta, parecer, votação, sanção/veto/regulamentação e publicação. Canonicalizar identidade sem perder texto/metadata originais.

### Policy graph e temporalidade

Modelar content item/version, detected event, corroboration, impact, proposal/stage/actor/vote/regulatory action e exposures. Arestas são versionadas e carregam fonte/confiança. Estado jurídico e probabilidade usam somente conhecimento disponível no `as_of`; mudança de texto ou estágio gera evento/diff, não update silencioso.

### Avaliação quantitativa e qualitativa

Calcular base rate por tipo/estágio, apoio, urgência, histórico, calendário e impeditivos em código. Political Agent analisa materialidade, diff, mecanismo econômico, winners/losers, timing, judicialização e regulamentação posterior. Probabilidade retorna intervalo, hipóteses e calibração; Critic procura evidências contrárias.

### Propagação de impacto

Materializar o caminho `policy_event -> setor -> driver operacional -> métrica -> empresa -> tese -> carteira`. Cada elo possui método, versão e evidência. Mudança relevante dispara `PolicyEventWorkflow`, cenários determinísticos e revisão de tese; nenhuma posição é alterada automaticamente.

### Experiência e alertas

Adicionar visão macro, legislative tracker, matriz de exposição, timeline e badges de estágio/probabilidade ao painel. Alertas consideram materialidade, exposição, freshness e corroboration para evitar ruído. Estágio jurídico e probabilidade são dimensões visuais separadas.

## Interfaces

- `GET /v1/policy/events` oferece filtros por fonte, estágio, tema, setor, emissor, materialidade e `as_of`.
- Detalhe retorna versões/diff, fontes, atores, base rate, intervalo, cenários e caminho de impacto.
- Commands de revisão/correção são assíncronos, autorizados e auditados; não editam raw.
- Eventos: `PolicyObjectDiscovered`, `PolicyStageChanged`, `PolicyImpactAssessed`, `MaterialPolicyReviewRequested` e `MacroScenarioUpdated`.

## Sequência de pull requests

| PR | Conteúdo | Validação principal |
| --- | --- | --- |
| `F7-PR01` | Contratos/fixtures e conectores Câmara/Senado | Contract tests e idempotência |
| `F7-PR02` | DOU e reguladores priorizados | Proveniência/licença/freshness |
| `F7-PR03` | BCB/SIDRA completo, séries e revisões | Consulta macro PIT |
| `F7-PR04` | Policy identity, versions, stages, actors e votes | Diff/temporalidade corretos |
| `F7-PR05` | Base rates, probabilidades, intervalos e calibração | Backtest/calibration tests |
| `F7-PR06` | Policy graph e exposure mapping | Lineage fonte-carteira completa |
| `F7-PR07` | PolicyEventWorkflow, agents e human review | Workflow/replay/evals |
| `F7-PR08` | Dashboard, timeline, matriz e alertas | E2E de evento material |

## Checklist detalhado de implementação

### `F7-PR01` — Câmara e Senado

- [x] Registrar fontes, endpoints, schemas, licença, rate limit e SLA.
- [x] Criar fixtures para proposição, versão, tramitação, ator e votação.
- [x] Implementar clients com timeout, retry, paginação e egress allowlist.
- [x] Preservar raw/hash/timestamps antes de parsing.
- [x] Normalizar identidades sem colidir Câmara e Senado.
- [x] Implementar discovery incremental/idempotente e contract tests.

### `F7-PR02` — DOU e reguladores

- [ ] Priorizar reguladores e tipos de ato por materialidade do produto.
- [ ] Documentar autenticação, termos, retenção e restrições de redistribuição.
- [ ] Criar discovery/download/parser por fonte com fixtures legais.
- [ ] Extrair órgão, tipo, número, data, vigência, assunto e referências.
- [ ] Vincular retificação/revogação/versão ao objeto anterior.
- [ ] Testar schema drift, documento ausente, duplicado e source outage.

### `F7-PR03` — BCB e SIDRA

- [ ] Inventariar séries, unidades, frequência, revisão e calendário.
- [x] Registrar metadata e versões da definição de cada série.
- [x] Ingerir observações com published/knowledge/effective timestamps.
- [x] Tratar revisões sem sobrescrever valor anteriormente conhecido.
- [x] Implementar resampling/transformações determinísticas versionadas.
- [ ] Criar contract/PIT/golden tests e métricas de freshness.

### `F7-PR04` — Domínio político versionado

- [x] Modelar proposal, version, stage, actor, vote e regulatory action.
- [x] Definir taxonomia de eventos e state machine por tipo jurídico.
- [x] Implementar diff de texto/metadata entre versões.
- [ ] Versionar temas, prazos, setores e relacionamentos do graph.
- [x] Persistir fontes/corroboration em cada fato/evento.
- [ ] Testar retificação, apensamento, veto parcial e consulta `as_of`.

### `F7-PR05` — Probabilidade e calibração

- [ ] Definir datasets históricos e evitar leakage temporal.
- [x] Calcular base rate por tipo, estágio e janela em código.
- [ ] Versionar features, metodologia, modelo e calibration window.
- [x] Retornar intervalo, hipóteses e fatores, não somente ponto.
- [x] Registrar previsão antes do resultado e avaliar calibration depois.
- [ ] Testar amostra pequena, dado missing, mudança de regime e futuro oculto.

### `F7-PR06` — Policy graph e exposições

- [x] Modelar arestas evento-setor-driver-métrica-emissor-tese-carteira.
- [x] Guardar método, versão, evidência, confiança e validade por aresta.
- [x] Criar mappings iniciais como draft sujeitos a revisão.
- [x] Implementar propagação determinística e detecção de impacto material.
- [x] Evitar duplicidade/ciclo inválido e respeitar organização/permissões.
- [ ] Criar teste de lineage completo e recalculação por nova versão.

### `F7-PR07` — Workflow e agents

- [ ] Implementar descoberta, normalização, comparação e atualização de estágio.
- [ ] Calcular base rate antes de executar Political Agent.
- [ ] Fornecer somente evidence citável e cutoff temporal ao agent.
- [ ] Executar Critic/corroboration e validar schema/citations.
- [ ] Rodar cenários e identificar teses/carteiras sem alterá-las.
- [x] Pausar impacto material para revisão humana autorizada.
- [ ] Testar retry, replay, quarentena, budget e prompt injection.

### `F7-PR08` — Dashboard e alertas

- [x] Implementar visão macro, legislative tracker e timeline versionada.
- [x] Implementar matriz de exposição por setor/emissor/carteira.
- [x] Exibir fonte, diff, estágio, probabilidade/intervalo e `as_of`.
- [x] Separar visualmente estágio jurídico, chance e impacto econômico.
- [ ] Criar regras de alerta por materialidade/freshness/corroboration.
- [ ] Implementar deduplicação, acknowledge e link para revisão.
- [ ] Executar E2E de fonte oficial a tese/carteira impactada.

## Migration, rollout e rollback

Ativar fontes uma por vez, inicialmente em shadow ingestion e sem alertas. Validar schema/freshness e somente então promover a canônica. Mapeamentos de exposição começam como draft e exigem aprovação. Mudança de metodologia cria versão e recalcula prospectivamente; histórico mantém output original. Rollback pausa schedule/fonte e retorna à última versão validada, marcada stale quando necessário.

## Segurança, observabilidade e falhas

- Respeitar termos de uso, rate limits, retenção e classificação de cada fonte.
- Egress limitado a domínios registrados; conteúdo externo é input não confiável contra prompt injection.
- Métricas: source freshness, parse/schema rate, eventos/deduplicação, corroboration, calibration, aging de revisão e alertas por severidade.
- Fonte indisponível não reduz probabilidade automaticamente nem mantém dado como fresco.
- Correção humana cria nova assessment/version e audit event; não reescreve previsão histórica.

## Testes e critérios de aceite

- Contract/golden tests por fonte e por mudança representativa de schema.
- Property tests de idempotência, versões e ausência de conhecimento futuro.
- Evals de diff, materialidade, mecanismo econômico, citações e prompt injection.
- Workflow/replay tests para descoberta, atualização, retry, quarentena e aprovação.
- Teste de calibração separa previsão registrada do resultado realizado.
- E2E rastreia ato oficial da fonte até métrica, tese e exposição de carteira.

## Critérios de saída

- [ ] Fontes priorizadas possuem registry, licença, fixtures, health e contract tests.
- [ ] Versões/estágios jurídicos são reproduzíveis por `as_of`.
- [ ] Probabilidades mostram intervalo, método, versão e calibração.
- [ ] Cada impacto material possui lineage até teses/carteiras afetadas.
- [x] Revisão humana é obrigatória antes de alterar tese.
- [x] Dashboard diferencia fato, estágio, probabilidade e impacto.
- [x] Runbooks cobrem schema drift, source outage, correção e falso alerta.

## Riscos e passagem para a Fase 8

Risco político não pode ser apresentado como certeza. Incerteza, corroboration e fonte devem permanecer visíveis. A Fase 8 recebe eventos e cenários como inputs de risco, nunca como instruções diretas de negociação.

## Auditoria de implementação (2026-07-19)

Conectores policy/ e macro/ verificados como implementações reais: `_official.py` (268 lines, Câmara/Senado/DOU com egress allowlist, parallel fetch), `_bcb.py` (146 lines, BCB SGS API com Selic/IPCA/USD), `_sidra.py` (145 lines, SIDRA GDP/IP). 7 fixtures sintéticos para Câmara/Senado/DOU. Policy graph modelado com proposal, version, stage, actor, vote. Pendências: DOU e reguladores completos, BCB/SIDRA com PIT tests, probabilidades calibradas, workflow completo com agents.
