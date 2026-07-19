# Fase 3 — Domínio de pesquisa

[Índice](README.md) · [Fase anterior](02-fase-2-confianca-dos-dados.md) · [Plano mestre](../PLAN.md)

## Objetivo e resultado esperado

Criar o ciclo auditável que transforma fatos e evidências em claims, teses versionadas, cenários de valuation e recomendações com validade. Ao final, a pergunta “por que PETR4 possuía recomendação X na data Y?” deve ser respondida com dados, versões, responsáveis e aprovações.

## Critérios de entrada

- Dados canônicos, evidências citáveis e consultas `as_of` aprovados na Fase 2.
- Identity mínima e contexto de auditoria disponíveis para autoria/revisão.
- Contratos canônicos v1 e operações assíncronas estáveis.

## Estado atual e lacunas

Há schemas iniciais de tese, risco e avaliação, além de RAG/avaliação prototípicos, mas não existe ciclo integrado de caso, assignment, claim-evidence, revisão, versionamento, expiração ou reprodução temporal. Valuation e scorecards ainda não vinculam premissas a evidências/versionamento.

## Escopo e limites

Implementar research cases, perguntas/assignments, evidence, claims, assessments, teses/versões, catalisadores, riscos, invalidação, valuation scenarios, recomendações, revisão humana e timeline. Automação usa apenas mocks/serviços determinísticos; specialists reais entram na Fase 4. Comitê e efeito em carteira pertencem às Fases 5–6.

## Modelo e regras de domínio

### Caso e evidência

`research_case` possui tipo, emissores/instrumentos, perguntas, prioridade, estado, `data_as_of`, prazo e responsáveis por papel. Estados mínimos: `draft -> triage -> in_research -> review -> approved|rejected -> closed`, com reabertura auditada. Evidence referencia versão imutável da fonte, localização, trecho/hash, licença, timestamps e qualidade.

### Claims e avaliações

Claim distingue fato, inferência e recomendação, declara materialidade, confiança, validade e evidências favoráveis/contrárias. Claim material sem evidência não pode ser verificado. Contradições ficam explícitas; aprovação não as apaga. Assessment registra autor humano/agent, schema/version, resultado e expiração.

### Teses e recomendações

Tese é identidade estável; `thesis_version` é snapshot imutável com resumo, premissas, catalisadores, riscos, invalidações, cenário, recomendação e evidências. Edição cria draft novo e diff; aprovação encerra versão ativa anterior. Toda decisão expira e revisão atrasada marca a tese como stale, sem renovar automaticamente.

### Valuation e scorecards

Valuation retorna bear/base/bull, ponderado, reverse DCF, relativo e cenário implícito. Premissas têm fonte, versão, sensibilidade e aprovação; fórmulas executam em código. Scorecards partem de métricas brutas, transformações versionadas e pilares setoriais; ausência reduz confiança/cobertura e veto produz `eligibility=blocked`, nunca simples penalidade numérica.

## Interfaces

- Queries: casos com filtros/cursor, caso detalhado, tese/versões/diff, evidências e valuation com `as_of`.
- Commands: criar/submeter caso, adicionar claim/evidence, solicitar revisão, criar revisão de tese e aprovar/rejeitar.
- Escritas concorrentes exigem `ETag`/`If-Match`; comandos longos usam operação Temporal e idempotência.
- `ThesisVersionResponse` nunca embute ORM nem conteúdo sem licença; retorna referências e permissões.
- Eventos: `ResearchCaseOpened`, `ClaimVerified`, `ThesisRevisionRequested`, `ThesisVersionApproved`, `ThesisExpired` e `RecommendationChanged`.

## Sequência de pull requests

| PR | Conteúdo | Validação principal |
| --- | --- | --- |
| `F3-PR01` | Research case, perguntas, assignments e state machine | Transições e autorização unitárias |
| `F3-PR02` | Evidence, claim, claim-evidence e contradições | Claim material falha sem evidence |
| `F3-PR03` | Assessments, revisão humana e audit timeline | Autoria/razão preservadas |
| `F3-PR04` | Tese, versões, catalisadores, riscos e invalidação | Diff e ativação atômica |
| `F3-PR05` | Valuation scenarios e engine determinístico | Golden tests de fórmulas |
| `F3-PR06` | Scorecards setoriais, cobertura, confiança e vetos | Missing não aumenta score |
| `F3-PR07` | API/handlers e eventos/outbox do domínio | Contract/OpenAPI tests |
| `F3-PR08` | ThesisReviewWorkflow mockado e cenário explicável E2E | Resposta histórica completa |

## Checklist detalhado de implementação

### `F3-PR01` — Research cases

- [x] Modelar caso, perguntas, assignments, prioridade, prazo e `data_as_of`.
- [x] Implementar state machine e tabela explícita de transições autorizadas.
- [x] Definir permissões para criar, atribuir, submeter, revisar, fechar e reabrir.
- [x] Impedir fechamento com perguntas obrigatórias pendentes.
- [x] Emitir eventos de domínio/outbox em cada transição material.
- [ ] Testar transições válidas, inválidas, concorrentes e expiradas. *(Parcial: test_research_domain.py testa 6 transições válidas + 1 inválida. Falta: transições concurrent (lock_version mismatch/ResearchConcurrencyError) e expiradas (due_at). Transições review->rejected e rejected->closed também não testadas)*

### `F3-PR02` — Evidence e claims

- [x] Modelar evidence como referência imutável à source/document version.
- [x] Registrar localização, trecho/hash, licença, qualidade e timestamps.
- [x] Modelar claim com tipo fato/inferência/recomendação, materialidade e validade.
- [x] Suportar evidência favorável, contrária e relação de contradição.
- [x] Bloquear estado `verified` para claim material sem evidence válido.
- [ ] Testar evidence revogado, temporalmente futuro, sem permissão e contraditório. *(Nenhum teste existe: ClaimService.verify() filtra revoked_at, knowledge_at <= cutoff, valid_until > cutoff e permissions — mas nenhum teste exercita esses caminhos. ClaimContradiction model existe mas não testado)*

### `F3-PR03` — Assessments e revisão humana

- [x] Modelar assessment, autor humano/agent, schema/version e expiração.
- [x] Implementar fila de revisão, decisão, comentário e pedido de alteração.
- [x] Registrar before/after hash, razão e correlation ID no audit event.
- [x] Aplicar segregação entre autor e aprovador conforme policy.
- [x] Preservar dissenso e contradições após aprovação.
- [ ] Testar autorização, dupla submissão, revisão expirada e concorrência. *(Parcial: test_research_reviews.py testa ensure_segregation (segregation of duties). Falta: testes dos 3 service-level permissions (create/request/decide), double submission (status != pending), expired assessment (expires_at <= now), e pessimistic locking (with_for_update))*

### `F3-PR04` — Teses versionadas

- [x] Separar identidade da tese de snapshots imutáveis de versão.
- [x] Modelar premissas, catalisadores, riscos, invalidações e recomendação.
- [x] Criar draft a partir da versão ativa com diff estruturado.
- [x] Ativar nova versão e fechar anterior em transação atômica.
- [x] Implementar expiração/stale e revisão sem renovação automática.
- [ ] Testar invalidação, rollback lógico, duas revisões e consulta `as_of`. *(Nenhum teste existe: test_thesis_domain.py testa apenas hash reprodutível, diff e serialização. ThesisService tem revise/activate/active_as_of mas nenhum teste cobre invalidation, rollback, two revisions ou as_of queries)*

### `F3-PR05` — Valuation determinístico

- [x] Definir contratos de bear/base/bull, ponderado, reverse DCF e relativo.
- [x] Modelar premissas com fonte, versão, unidade, horizonte e aprovação.
- [x] Implementar fórmulas fora do agent com Decimal/tolerâncias definidas.
- [x] Persistir code/input snapshot, sensibilidades e resultados.
- [x] Bloquear cenário sem evidência ou dado crítico válido.
- [x] Criar golden tests, casos limite e reprodução pelo mesmo hash.

### `F3-PR06` — Scorecards

- [x] Versionar métricas brutas, winsorization, z-score/percentil e ajustes.
- [x] Definir pilares/pesos específicos por estratégia e setor.
- [x] Calcular coverage, data quality e thesis freshness separadamente.
- [x] Implementar veto como elegibilidade bloqueada com razão.
- [x] Impedir que missing repondere automaticamente os demais pilares.
- [x] Criar golden/property tests para indústria, banco e utility.

### `F3-PR07` — API e eventos

- [ ] Criar handlers de query/command sem acesso direto a ORM nas routes. *(Parcial: create_case, transition_case, verify_claim, create_thesis, revise_thesis, activate_thesis delegam a services. Porém list_cases, get_case e get_thesis_as_of em research.py ainda têm ORM inline)*
- [x] Implementar cursor, filtros, `as_of`, ETag e `If-Match`.
- [x] Retornar response schemas dedicados e Problem Details.
- [x] Publicar OpenAPI e client fixtures para casos/claims/teses/valuation.
- [ ] Implementar outbox idempotente e consumidores de timeline. *(Parcial: DomainOutboxEvent model existe com idempotency_key unique; eventos são publicados atomicamente em research.py, theses.py, reviews.py. Porém: nenhum consumer/poller existe — published_at nunca é populado por consumidor, nenhum timeline worker)*
- [ ] Testar autorização, concorrência, paginação e compatibilidade de schema. *(Nenhum teste HTTP-level: test_api_contracts.py valida OpenAPI shape mas não testa 403/412/409, nenhum teste de cursor pagination, nenhum teste de schema backward-compatibility)*

### `F3-PR08` — ThesisReviewWorkflow E2E

- [ ] Carregar versão ativa e somente fatos/evidências válidos no cutoff. *(ThesisReviewWorkflow não existe — nenhum dos 12 workflows exportados em __init__.py é de revisão de tese)*
- [ ] Executar especialistas mockados com outputs canônicos. *(Atividades mock existem em research_mock.py mas não são orquestradas por workflow de tese)*
- [ ] Verificar contradições e recalcular valuation/risco relevante. *(Não implementado — nenhum workflow de revisão de tese)*
- [ ] Gerar diff e pausar para aprovação humana. *(ApprovalGateWorkflow é genérico, não implementa diff de tese nem lógica específica)*
- [ ] Ativar/rejeitar versão sem perder histórico ou dissenso. *(Não implementado em workflow)*
- [ ] Responder pela API por que PETR4 tinha recomendação X na data Y. *(Nenhum teste E2E nem endpoint demonstra isso — PETR4 aparece apenas em fixtures B3)*
- [ ] Testar retry, replay, cancelamento, expiração e idempotência. *(Nenhum teste de ThesisReviewWorkflow — workflow não existe)*

## Migration, rollout e rollback

Adicionar tabelas e eventos sem substituir schemas antigos de imediato. Adaptadores leem contratos legados durante a migração; novas escritas usam somente modelos canônicos. Backfill pode criar versões importadas marcadas com origem e confiança, nunca fingir aprovação humana. Rollback desabilita commands por feature flag e mantém versões/evidências append-only.

## Segurança, observabilidade e falhas

- Analista cria/edita; revisor aprova conforme segregação configurada. Auditor é read-only.
- Conteúdo licenciado é retornado apenas a papéis permitidos; auditoria registra acesso material.
- Métricas: casos por estado, aging, teses ativas/expiradas, coverage, tempo de revisão e claims sem suporte.
- Falha de valuation ou dado stale impede aprovação ou exige waiver explícito conforme policy.
- Conflito de concorrência retorna 412/409, sem sobrescrever revisão de outro autor.

## Testes e critérios de aceite

- Unit/property tests para state machines, expiração, diffs, policies e scorecards.
- Integration tests para constraints, versionamento atômico, outbox e consultas `as_of`.
- Contract tests de API, Problem Details, cursor, ETag e decimal/date serialization.
- Golden tests para DCF/relativo e transformações por setor.
- E2E cria caso, vincula evidência, aprova claim/tese e reproduz recomendação em data passada.
- Teste negativo prova que claim material, tese stale ou dado em quarentena não é aprovado silenciosamente.

## Critérios de saída

- [x] Caso, evidência, claim, assessment e tese possuem identidade e versão claras. *(verificado: ResearchCase 7 states, Evidence ref imutável, Thesis 4 states, ValuationRun 6 states)*
- [x] Toda recomendação possui responsável, validade, dados `as_of` e evidências. *(verificado: ValuationRun com Assumptions vinculadas a evidence/financial_facts/metric_observations)*
- [x] Fórmulas e scorecards são determinísticos e versionados.
- [x] Diffs e contradições são visíveis e auditáveis. *(verificado: ThesisVersionEvidence, ThesisVersionClaim, ResearchEvidence com CheckConstraints)*
- [ ] A pergunta de aceite sobre PETR4 é respondida por API/teste E2E. *(Nenhum teste E2E existe — PETR4 aparece apenas em fixtures B3, não no domínio de pesquisa)*
- [x] Runbooks cobrem revisão, expiração, conflito e correção de evidência.

## Riscos e passagem para a Fase 4

O risco é permitir que texto narrativo se torne verdade canônica. Fatos permanecem na Fase 2; o domínio de pesquisa só referencia e interpreta. A Fase 4 recebe tools de leitura/command restrito, schemas de análise, datasets de casos e gates humanos bem definidos.

## Auditoria de implementação (2026-07-19)

Todos os 5 artefatos verificados existem e são implementações reais: `research.py` (ResearchCase 7 states, OutboxEvent, Assignments), `evidence.py` (DocumentChunk com pgvector 1536, TSVECTOR, HNSW index), `thesis_domain.py` (Thesis 4 states, Version 12 checks, Evidence/Claim links), `valuation.py` (ValuationRun 6 states, Assumptions com source checks), `_scorecard.py` (5 sector profiles, veto rules, coverage).

**Itens marcados como [x] confirmados:** Research case model/state machine, evidence imutável, claims, assessments, theses versionadas, valuation determinístico com golden tests, scorecards com vetos, API com ETag/If-Match/Problem Details, OpenAPI publicado.

**Pendências restantes (não implementadas ou parciais):**
- Testes de transições concorrentes e expiradas do research case
- Testes de evidence revogada, futura, sem permissão e contraditória
- Testes de autorização/dupla-submissão/revisão-expirada/concorrência em assessments
- Testes de invalidação/rollback/duas-revisões/as_of em teses
- Routes research.py com ORM inline (list_cases, get_case, get_thesis_as_of)
- Outbox model existe mas nenhum consumer/poller
- Nenhum teste HTTP-level de autorização/concorrência/paginação/schema
- ThesisReviewWorkflow NÃO EXISTE (nenhum dos 12 workflows é de revisão de tese)
- Cenário PETR4 de aceite não respondido
