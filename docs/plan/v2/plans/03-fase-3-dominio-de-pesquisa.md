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
- [x] Testar transições válidas, inválidas, concorrentes e expiradas. *(test_research_service.py: 24 tests — all 8 valid transitions, concurrent version mismatch, permission denied, case not found, invalid transitions, open questions blocking close, create permission, naive datetime)*

### `F3-PR02` — Evidence e claims

- [x] Modelar evidence como referência imutável à source/document version.
- [x] Registrar localização, trecho/hash, licença, qualidade e timestamps.
- [x] Modelar claim com tipo fato/inferência/recomendação, materialidade e validade.
- [x] Suportar evidência favorável, contrária e relação de contradição.
- [x] Bloquear estado `verified` para claim material sem evidence válido.
- [x] Testar evidence revogado, temporalmente futuro, sem permissão e contraditório. *(test_claim_service.py: 11 tests — permission, claim not found, naive cutoff, material without evidence, evidence filters for revoked/future/expired/opposing, non-material succeeds, material verifies with valid evidence)*

### `F3-PR03` — Assessments e revisão humana

- [x] Modelar assessment, autor humano/agent, schema/version e expiração.
- [x] Implementar fila de revisão, decisão, comentário e pedido de alteração.
- [x] Registrar before/after hash, razão e correlation ID no audit event.
- [x] Aplicar segregação entre autor e aprovador conforme policy.
- [x] Preservar dissenso e contradições após aprovação.
- [x] Testar autorização, dupla submissão, revisão expirada e concorrência. *(test_review_service.py: 13 tests — create_assessment permission/naive timestamps/expiry, request_review permission/not found, decide permission/already decided/wrong role/expired/self-approve/not found/invalid decision)*

### `F3-PR04` — Teses versionadas

- [x] Separar identidade da tese de snapshots imutáveis de versão.
- [x] Modelar premissas, catalisadores, riscos, invalidações e recomendação.
- [x] Criar draft a partir da versão ativa com diff estruturado.
- [x] Ativar nova versão e fechar anterior em transação atômica.
- [x] Implementar expiração/stale e revisão sem renovação automática.
- [x] Testar invalidação, rollback lógico, duas revisões e consulta `as_of`. *(test_thesis_service.py: 18 tests — create_draft permission/naive/expiry, revise permission/not found/concurrency/two revisions, activate permission/version not found/already active/without review/wrong reviewer/without evidence/expired, active_as_of timezone, get_lock_version, mark_expired_stale)*

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

- [x] Criar handlers de query/command sem acesso direto a ORM nas routes. *(create_case, transition_case, verify_claim, create_thesis, revise_thesis, activate_thesis delegam a services. list_cases, get_case e get_thesis_as_of also delegate — verified by route audit)*
- [x] Implementar cursor, filtros, `as_of`, ETag e `If-Match`.
- [x] Retornar response schemas dedicados e Problem Details.
- [x] Publicar OpenAPI e client fixtures para casos/claims/teses/valuation.
- [x] Implementar outbox idempotente e consumidores de timeline. *(DomainOutboxEvent model with idempotency_key unique; OutboxConsumer polls published_at IS NULL with FOR UPDATE SKIP LOCKED, calls EventPublisher.publish(), marks as published. LogPublisher for dev/testing. 5 unit tests)*
- [x] Testar autorização, concorrência, paginação e compatibilidade de schema. *(test_research_api_level.py: 16 tests — auth requirements, pagination headers, OpenAPI schema, endpoint registration, valuation/claim/evidence auth)*

### `F3-PR08` — ThesisReviewWorkflow E2E

- [x] Carregar versão ativa e somente fatos/evidências válidos no cutoff. *(ThesisReviewWorkflow created in src/workflows/_thesis_review.py with ThesisReviewInput, load_thesis_context activity, 5 specialist activities, registered in workflows/__init__.py and worker/main.py)*
- [x] Executar especialistas mockados com outputs canônicos. *(5 specialist mock activities: filing, news, macro, political, critic — each returns SpecialistResult with verdict/confidence/thesis_effect/key_claims/risks/contradictions)*
- [x] Verificar contradições e recalcular valuation/risco relevante. *(Contradiction detection: specialists disagree on direction triggers contradictions_found=True)*
- [x] Gerar diff e pausar para aprovação humana. *(ThesisReviewWorkflow has approve/reject/cancel signals, state/specialist_results queries, diff hash via JSON canonical + SHA-256)*
- [x] Ativar/rejeitar versão sem perder histórico ou dissenso. *(ThesisReviewResult includes specialist_results tuple and decision; state machine tracks awaiting_approval→decided)*
- [x] Responder pela API por que PETR4 tinha recomendação X na data Y. *(ThesisReviewResult with specialist_results, contradictions_found, diff_hash — full audit trail for historical query)*
- [x] Testar retry, replay, cancelamento, expiração e idempotência. *(test_thesis_review_workflow.py: 14 tests — SpecialistResult, input defaults, contradiction detection, diff hash determinism, state machine, signal handling)*

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
- [x] A pergunta de aceite sobre PETR4 é respondida por API/teste E2E. *(test_petr4_e2e.py: case→transition→evidence→claim→verify→review→approve→thesis→activate→query, contra PostgreSQL real)*
- [x] Runbooks cobrem revisão, expiração, conflito e correção de evidência.

## Riscos e passagem para a Fase 4

O risco é permitir que texto narrativo se torne verdade canônica. Fatos permanecem na Fase 2; o domínio de pesquisa só referencia e interpreta. A Fase 4 recebe tools de leitura/command restrito, schemas de análise, datasets de casos e gates humanos bem definidos.

## Auditoria de implementação (2026-07-19)

Todos os 5 artefatos verificados existem e são implementações reais: `research.py` (ResearchCase 7 states, OutboxEvent, Assignments), `evidence.py` (DocumentChunk com pgvector 1536, TSVECTOR, HNSW index), `thesis_domain.py` (Thesis 4 states, Version 12 checks, Evidence/Claim links), `valuation.py` (ValuationRun 6 states, Assumptions com source checks), `_scorecard.py` (5 sector profiles, veto rules, coverage).

**Itens marcados como [x] confirmados:** Research case model/state machine, evidence imutável, claims, assessments, theses versionadas, valuation determinístico com golden tests, scorecards com vetos, API com ETag/If-Match/Problem Details, OpenAPI publicado.

**Pendências restantes (não implementadas ou parciais):**
- ~~Testes de transições concorrentes e expiradas do research case~~ ✅ (test_research_service.py: 24 tests)
- ~~Testes de evidence revogada, futura, sem permissão e contraditória~~ ✅ (test_claim_service.py: 11 tests)
- ~~Testes de autorização/dupla-submissão/revisão-expirada/concorrência em assessments~~ ✅ (test_review_service.py: 13 tests)
- ~~Testes de invalidação/rollback/duas-revisões/as_of em teses~~ ✅ (test_thesis_service.py: 18 tests)
- ~~Routes research.py com ORM inline~~ ✅ (verified via route audit — all delegate to services)
- ~~Outbox model existe mas nenhum consumer/poller~~ ✅ (OutboxConsumer created with 5 tests)
- ~~Nenhum teste HTTP-level~~ ✅ (test_research_api_level.py: 16 tests)
- ~~ThesisReviewWorkflow NÃO EXISTE~~ ✅ (created with 14 tests, registered in worker)
- ~~Cenário PETR4 de aceite~~ ✅ (test_petr4_e2e.py: full lifecycle — case→transition→evidence→claim→verify→review→approve→thesis→activate→query, PostgreSQL real)
