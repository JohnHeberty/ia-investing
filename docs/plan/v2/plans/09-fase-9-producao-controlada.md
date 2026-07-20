# Fase 9 — Produção controlada e gate para eventual execução real

[Índice](README.md) · [Fase anterior](08-fase-8-operacao-paper-institucional.md) · [Plano mestre](../PLAN.md)

## Objetivo e resultado esperado

Produzir uma decisão formal, documentada e independente de **go/no-go para iniciar um projeto futuro de execução live**. Esta fase comprova prontidão jurídica, de dados, segurança, operação e model risk. Mesmo um resultado `go` não autoriza ordem real: autoriza somente elaborar arquitetura, contratos e novo plano de implementação de integração live.

## Critérios de entrada

- Operação paper estável, reconciliada e observável por janela definida pelo comitê de prontidão.
- Gates das Fases 0–8 encerrados sem exceção crítica aberta.
- Inventário de usos, usuários, dados, modelos, decisões e controles atualizado.
- Patrocínio executivo para auditorias independentes e avaliação jurídica especializada.

## Estado atual e lacunas

O produto foi concebido como plataforma interna de pesquisa/paper e não possui perímetro jurídico aprovado para recomendar, administrar ou executar recursos. Não há auditoria independente de segurança, segregação live, disaster recovery comprovado, governança completa de modelos/dados licenciados ou desenho de integração com corretora. Esses itens são bloqueadores, não backlog opcional.

## Escopo e fora de escopo

Executar workstreams de prontidão, reunir evidências, tratar findings e realizar decisão formal. Inclui revisão jurídica/regulatória, direitos de dados, segurança, segregação, continuidade, kill switch, reconciliação, limites, model risk e governança operacional.

Ficam explicitamente fora de escopo: seleção/contratação de corretora, FIX/API de broker, OMS/EMS live, custódia, roteamento, envio/cancelamento de ordem real, credenciais live, suitability implementada para clientes ou habilitação do estado `live`. Qualquer um desses itens exige novo plano aprovado após este gate.

## Workstreams de prontidão

### Jurídico, regulatório e finalidade

Documentar se o uso é pesquisa interna, relatório, consultoria individualizada ou administração/execução; público, jurisdição, responsabilidades profissionais, disclosures, conflitos, suitability e retenção. Obter parecer jurídico formal sobre CVM 19/20/21 e demais normas aplicáveis. Resultado inconclusivo é `no-go`.

### Dados e propriedade intelectual

Comprovar licença para ingestão, armazenamento, transformação, exibição e uso em modelos de cada fonte. Validar retenção, exclusão, redistribuição, lineage e resposta a mudança de termos. Conteúdo sem direito comprovado é removido/substituído antes do gate.

### Segurança e segregação

Realizar threat model e auditoria independente cobrindo OIDC/MFA, RBAC+ABAC, quatro olhos, secrets, TLS/repouso, rotação, egress, rate limit, append-only audit, restricted list, dependency/secret/SAST/container scans e supply chain. Definir ambientes/contas/chaves live segregados apenas em desenho, sem provisionar credencial de trading nesta fase.

### Operação, continuidade e reconciliação

Exercitar backup/restore, RTO/RPO, disaster recovery, degradação de fontes, worker outage, replay Temporal, reconciliation break, breach e kill switch. Definir SLOs, on-call, incident severity, comunicação, post-mortem e autoridade de suspensão. Nenhum processo crítico pode depender de edição manual não auditada.

### Model risk e performance paper

Registrar modelos/datasets/versions, validação independente, limites, drift, calibração, overrides e critérios de aposentadoria. Demonstrar backtest PIT, paper estável, custo/slippage, divergências, champion/challenger e ausência de violação crítica ignorada. Performance positiva não compensa falha de controle.

### Comitê de prontidão

Montar decision pack imutável com pareceres, auditorias, findings, evidências, riscos residuais, exceções, responsáveis por papel e condições. Jurídico, Segurança, Risco, Compliance, Operações, Dados e Investimentos votam conforme quórum/policy. Conflitos e dissenso ficam registrados.

## Artefatos e interfaces documentais

- Matriz de obrigações e parecer jurídico assinado.
- Data license register e data-processing/retention map.
- Threat model, pentest/audit report e plano de remediação.
- BCP/DR plan com resultados de exercícios e RTO/RPO observados.
- Model risk inventory, validation reports e performance paper pack.
- Control matrix ligando requisito, controle, owner role, evidência, teste e finding.
- `ReadinessDecision` com resultado `go|conditional_go|no_go`, votos, condições, expiração e hash do pack.

`conditional_go` permite somente remediação/reavaliação; não permite desenhar ou implementar live enquanto condição bloqueante estiver aberta.

## Sequência de pull requests

Estes PRs versionam políticas, evidências e eventuais correções de controles; não implementam execução real.

| PR | Conteúdo | Validação principal |
| --- | --- | --- |
| `F9-PR01` | Perímetro, pareceres e matriz regulatória | Aprovação jurídica/compliance |
| `F9-PR02` | Registro de licenças, retenção e remediações | Nenhuma fonte crítica sem direito |
| `F9-PR03` | Threat model, auditoria e findings de segurança | Zero finding crítico aberto |
| `F9-PR04` | BCP/DR, restore, incidentes e kill switch drills | RTO/RPO e evidências aprovados |
| `F9-PR05` | Model risk, validação independente e paper evidence | Limites/drift/overrides governados |
| `F9-PR06` | Control matrix e fechamento de findings | Evidências rastreáveis |
| `F9-PR07` | Decision pack e reunião go/no-go | Decisão assinada e expirada/controlada |

## Checklist detalhado de implementação

### `F9-PR01` — Perímetro e pareceres

- [x] Documentar finalidade, usuários, destinatários e jurisdições do produto.
- [x] Classificar capacidades como pesquisa, relatório, consultoria ou gestão/execução.
- [ ] Mapear CVM 19/20/21 e demais obrigações identificadas por especialista.<!-- audit: processo humano — não verificável em código; requer parecer de advogado/regulatório -->
- [ ] Definir responsabilidades profissionais, disclosures e conflitos.<!-- audit: processo humano — não verificável em código -->
- [ ] Definir suitability e retenção somente quando aplicáveis ao perímetro.<!-- audit: processo humano — não verificável em código -->
- [ ] Obter parecer jurídico assinado com premissas, restrições e validade.<!-- audit: processo humano — não verificável em código; bloqueador para gate -->
- [x] Registrar item `no-go` para qualquer conclusão ausente ou inconclusiva.

### `F9-PR02` — Licenças e retenção

- [ ] Inventariar toda fonte/dataset/documento/model input usado em produção.<!-- audit: processo humano — requer levantamento manual de cada fonte (CVM, B3, news, etc.) -->
- [ ] Comprovar direitos de coletar, armazenar, transformar, exibir e modelar.<!-- audit: processo humano — requer verificação de licenças contratuais -->
- [ ] Registrar território, usuários, retenção, redistribuição e expiração.<!-- audit: processo humano — não verificável em código -->
- [ ] Mapear dado derivado e lineage até outputs/decisões.<!-- audit: PARTIAL — lineage infra existe (MetricFactLineage em financial_facts.py:184-193, raw_zone.py content_sha256, post-mortem lineage validation em paper_execution.py:364-398), mas não há query/pipeline que percorra source→fact→metric→thesis→decision→paper em cadena única -->
- [ ] Implementar/remediar retenção, exclusão e mudança de termos.<!-- audit: não há lógica de retenção/expiração de dados no código; apenas freshness_grace_minutes em data_foundation.py para stale data -->
- [ ] Remover/substituir conteúdo sem direito comprovado.<!-- audit: processo humano — não verificável em código -->
- [ ] Obter aprovação de Jurídico/Data Governance para cada fonte crítica.<!-- audit: processo humano — não verificável em código -->

### `F9-PR03` — Segurança independente

- [x] Atualizar data flow diagram, trust boundaries e threat model.
- [ ] Revisar OIDC/MFA, RBAC+ABAC, four-eyes e service identities.<!-- audit: PARTIAL — OIDC/JWT em apps/api/security.py, RBAC com PERSONA_PERMISSIONS em domain/identity.py (6 personas), four-eyes em domain/identity.py:67-69. Porém: PERSONA_PERMISSIONS não mapeia readiness:verify/freeze; roles/permissions DB tables existem mas não são consumidos pelo app -->
- [ ] Revisar secrets, rotação, criptografia, egress, TLS e rate limits.<!-- audit: security-baseline.md existe (detect-secrets + pip-audit), mas não há evidência de rotação de secrets, rate limit code, ou egress filtering no código -->
- [ ] Revisar audit append-only, restricted list e segregação de ambientes.<!-- audit: PARTIAL — AuditLog em _audit.py:78-96 com correlation_id indexado; append-only pattern (nenhum UPDATE/DELETE em audit_logs). Restricted list: não encontrado. Segregação live/paper: authorize() em identity.py:52-64 bloqueia live ops -->
- [ ] Executar pentest e scans de dependência, secret, SAST e container.<!-- audit: security-baseline.md tem pip-audit findings; detect-secrets configurado. Pentest/SAST/container scans são processos humanos -->
- [ ] Classificar findings, corrigir e obter reteste independente.<!-- audit: processo humano — requer execução de pentest e classificação manual -->
- [x] Bloquear gate enquanto houver finding crítico aberto.

### `F9-PR04` — Continuidade e kill switch

- [ ] Definir serviços/dados críticos, RTO, RPO e dependências.<!-- audit: bcp-dr.md é STUB (21 linhas) — declara "O comite deve definir RTO/RPO antes do exercicio; valores nao sao inferidos neste documento" -->
- [ ] Verificar backups, retenção, criptografia e acesso de restauração.<!-- audit: bcp-dr.md não documenta backups, retenção ou criptografia concretos -->
- [ ] Restaurar stack/dados em ambiente isolado e reconciliar integridade.<!-- audit: bcp-dr.md tem script de restore de 5 passos mas é genérico; sem evidência de execução real -->
- [ ] Exercitar disaster recovery e medir RTO/RPO observados.<!-- audit: nenhum exercício de DR documentado ou testado no código -->
- [ ] Exercitar source outage, worker loss, replay e reconciliation break.<!-- audit: PARTIAL — reconciliation break testado em test_paper_execution.py:156-168 (domain-level). Worker outage/source outage: não testados. Replay: idempotency testado em activities.py:19-23 mas não como cenário de falha -->
- [ ] Exercitar kill switch global/por carteira e autoridade de retomada.<!-- audit: PARTIAL — kill switch implementado (paper_execution.py:536-605, 4-eyes enforcement), endpoints existem (paper_execution.py:456-485). Zero testes exercitam activation/blocking/release. Runbook existe em docs/plan/v2/runbooks/paper-operations.md -->
- [ ] Atualizar BCP, on-call, comunicação e post-mortem com evidências.<!-- audit: bcp-dr.md é STUB; on-call não definido; post-mortem endpoint existe (paper_execution.py:488) mas sem list/query API -->

### `F9-PR05` — Model risk e evidência paper

- [ ] Inventariar modelos, versões, datasets, prompts e owners por papel.<!-- audit: PARTIAL — agent registry em database/models/agent_registry.py com model_id, version, provider; MockProvider em ai/provider.py sem versionamento formal. Sem inventário consolidado de prompts ou datasets -->
- [ ] Documentar finalidade, limites, métricas, drift e critérios de retirada.<!-- audit: PARTIAL — eval thresholds em agent_registry.py (schema_pass, citation_coverage, cost_per_task, accuracy); guardrails em ai/guardrails.py. Sem detecção de drift, sem critérios de aposentadoria documentados -->
- [ ] Executar validação independente de dados, metodologia e resultados.<!-- audit: processo humano — requer revisão independente separada do desenvolvimento -->
- [ ] Revisar overrides, guardrails, calibração e champion/challenger.<!-- audit: PARTIAL — champion/challenger para paper existe (paper_execution.py:640-763, 4-eyes). Guardrails em ai/guardrails.py. Sem calibração de modelos, sem override tracking formal -->
- [ ] Consolidar backtest PIT, paper, custos, slippage e divergências.<!-- audit: PARTIAL — building blocks existem: backtest PIT (backtest.py), paper execution (paper_execution.py), cost/slippage simulation (domain/paper_execution.py:121-210), reconciliation breaks (domain/paper_execution.py:273-361). Sem pack consolidado de evidência -->
- [ ] Demonstrar janela/SLO definidos sem breach crítico ignorado.<!-- audit: NOT FOUND — sem definição de SLO em código; sem breach tracking; risk breaches model existe (database/models/paper_execution.py) mas sem SLO association -->
- [ ] Obter parecer formal de Model Risk/Risco sobre risco residual.<!-- audit: processo humano — requer parecer assinado -->

### `F9-PR06` — Control matrix

- [x] Mapear cada obrigação/risco para controle preventivo/detectivo.
- [x] Atribuir owner role, frequência, evidência e procedimento de teste.
- [x] Vincular findings, remediações, retestes e exceções com expiração.
- [ ] Amostrar lineage de fonte até decisão paper e audit event.<!-- audit: PARTIAL — segments existem: raw_zone.py (source→version), FinancialFact.source_object_version_id (fact→source), MetricFactLineage (metric→fact), post-mortem REQUIRED_POST_MORTEM_LINEAGE (paper→thesis→agent_run→decision). Falta query/pipeline end-to-end que percorra a cadeia completa; ReadinessDecisionPack.manifest é JSONB livre sem schema que exigia control_matrix_id ou metric_observation_ids -->
- [ ] Confirmar que nenhum controle depende de edição manual não auditada.<!-- audit: FOUND (app-layer) — todas as mutações passam por Application Services; nenhum route faz INSERT/UPDATE/DELETE direto em tabelas críticas. AuditLog registrado em toda mutação readiness (readiness.py:222-240). Financial facts usam revision_number (append-only). Métricas são idempotent inserts. Porém: não há DB triggers/RLS que impeçam SQL direto; proteção é apenas application-layer -->
- [ ] Validar segregação e cobertura com Jurídico, Segurança, Risco e Operações.<!-- audit: PARTIAL — 6 personas em PERSONA_PERMISSIONS (identity.py:6-32), 7 REQUIRED_VOTER_ROLES em readiness.py:8, DB CHECK constraint em ReadinessVote.voter_role (readiness.py:155-158). Porém: PERSONA_PERMISSIONS não mapeia readiness:verify/freeze; DB roles/permissions tables não são consumidos pelo app -->
- [ ] Congelar versão da matriz usada no decision pack.<!-- audit: PARTIAL — ReadinessDecisionPack tem content_sha256 + manifest JSONB (readiness.py:118-136). freeze_pack_manifest() produz hash determinístico (domain/readiness.py:100-103). "control_matrix" é REQUIRED_EVIDENCE_TYPES. Porém: não há ControlMatrixVersion model que congele snapshot agregado da matriz; manifest é JSONB livre sem schema que exija referência à matriz congelada -->

### `F9-PR07` — Decision pack e go/no-go

- [ ] Reunir pareceres, auditorias, exercícios, métricas e control matrix.<!-- audit: PARTIAL — ReadinessDecisionPack armazena manifest JSONB com evidence_ids (readiness.py:118-136). ReadinessEvidence armazena pareceres/auditorias como typed evidence (readiness.py:17-44). ReadinessControl armazena control matrix entries (readiness.py:47-74). Porém: não há GET endpoints para listar packs/votes/decisions; manifest não valida schema que inclua métricas ou control_matrix -->
- [ ] Listar findings/condições/riscos residuais sem omitir dissenso.<!-- audit: PARTIAL — ReadinessDecision.armazena dissent JSONB (readiness.py:174) com {role, vote, rationale}. ReadinessDecision.armazena conditions e blockers. ReadinessFinding model com lifecycle open→remediating→closed/risk_accepted (readiness.py:90-115). Porém: sem residual risk model dedicado; sem GET endpoints para consultar dissent/findings -->
- [x] Calcular hash e congelar o decision pack antes da reunião.
- [x] Verificar quórum, conflitos e autoridade de cada voto.
- [x] Registrar `go`, `conditional_go` ou `no_go`, razões e condições.
- [x] Registrar assinaturas, expiração e data obrigatória de revisão.
- [x] Impedir que `conditional_go` ou decisão expirada autorize avanço.
- [x] Confirmar que `go` autoriza somente um novo plano, não execução live.

## Rollout, rollback e falhas

Não há rollout live. Correções de controle seguem rollout normal, feature flags e rollback das fases anteriores. Durante auditorias, finding crítico pode suspender paper e bloquear novos approvals. Um `no_go` mantém pesquisa/paper dentro do perímetro jurídico aprovado e cria backlog de remediação. Uma decisão expirada volta automaticamente a `no_go` até nova avaliação.

## Testes e exercícios obrigatórios

- Restore completo de backup em ambiente isolado e verificação de integridade.
- Disaster recovery e perda de dependência crítica medidos contra RTO/RPO.
- Kill switch, breach, reconciliation break e credencial comprometida simulados.
- Pentest, dependency/secret/SAST/container scans sem finding crítico aberto.
- Replay/reprocessamento provam auditabilidade e idempotência.
- Tabletop regulatório/operacional cobre conflito, ordem sem aprovação, dado sem licença e falha de modelo.
- Revisão independente valida amostra de lineage da fonte à decisão paper.

## Critérios de saída

- [ ] Finalidade/perímetro e parecer jurídico estão formalmente aprovados.<!-- audit: product-perimeter.md existe (REAL, 23 linhas) classifica 5 capacidades. Parecer jurídico: pendente -->
- [ ] Toda fonte crítica possui direitos e retenção comprovados.<!-- audit: não há data license register; processo humano -->
- [ ] Segurança foi auditada e não há finding crítico aberto.<!-- audit: security-baseline.md existe (detect-secrets + pip-audit). Pentest formal pendente -->
- [ ] Segregação de funções, quatro olhos e restricted list foram testados.<!-- audit: PARTIAL — four-eyes implementado em domain/identity.py:67-69 com testes em test_paper_execution.py. Restricted list: não encontrado. Sem testes HTTP-level de autorização -->
- [ ] Backup, restore, DR, kill switch e reconciliação foram exercitados.<!-- audit: PARTIAL — kill switch implementado mas zero testes. Reconciliation testada em domain-level (test_paper_execution.py:156-168). Backup/restore/DR: bcp-dr.md é STUB sem exercício documentado -->
- [ ] Paper trading atende a janela/SLOs definidos sem breach crítico ignorado.<!-- audit: PARTIAL — paper execution funciona (testes em test_paper_execution.py). Sem SLO definitions, sem breach tracking, sem janela definida -->
- [ ] Model risk governance e validação independente estão aprovados.<!-- audit: PARTIAL — agent registry com eval thresholds existe (agent_registry.py). Sem model risk inventory formal, sem validação independente, sem drift detection -->
- [ ] Decision pack, votos, condições, dissenso e validade estão assinados/auditados.<!-- audit: PARTIAL — ReadinessDecisionPack com hash, ReadinessVote com rationale/conflicts, ReadinessDecision com dissent/conditions/blockers/expiry. Mas sem GET endpoints para consulta, manifest sem schema validation -->
- [x] Nenhuma credencial, endpoint ou integração de execução real foi criada.

## Resultado do gate

- **`no_go`:** manter somente capacidades autorizadas; remediar findings e repetir o gate.
- **`conditional_go`:** cumprir e validar todas as condições; repetir decisão antes de avançar.
- **`go`:** autorizar a criação de um novo plano para arquitetura e implementação live, com fornecedor, controles e rollout próprios. Não autoriza implementação ou envio de ordem real.

O gate deve falhar fechado diante de parecer ausente, licença incerta, finding crítico, controle não testado, paper instável ou decisão expirada.

## Auditoria de implementação (2026-07-19)

5 arquivos de readiness/ verificados: `README.md`, `product-perimeter.md`, `control-matrix.md` (REAL — 3 arquivos mapeiam obrigações/controles/owners/evidências). **2 STUBS identificados**: `threat-model.md` (19 linhas, esqueleto sem STRIDE/mitigations) e `bcp-dr.md` (21 linhas, skeleton sem RTO/RPO/runbook concreto). 2 baseline docs: `quality-baseline.md` (REAL — dados empíricos: 98 testes, 24% coverage, ruff/mypy) e `security-baseline.md` (REAL — detect-secrets + pip-audit findings). Pendências críticas: ambos os stubs devem ser expandidos para documentação completa antes do gate Fase 9.

### Auditoria de código (2026-07-19)

**Encontrado no código:**
- Readiness gate completo: ReadinessDecisionPack, ReadinessDecision, ReadinessVote, ReadinessEvidence, ReadinessFinding, ReadinessControl (6 tabelas em database/models/readiness.py, migration 6904a13eb7a7)
- API lifecycle completo: POST endpoints para evidence register/verify, pack freeze, vote sign, decide (routes/readiness.py:128-215)
- AuditLog com correlation_id em toda mutação readiness (readiness.py:222-240)
- Dissent registrado explicitamente em ReadinessDecision.dissent (readiness.py:174)
- Persona permissions com 6 roles (identity.py:6-32) e 7 REQUIRED_VOTER_ROLES (readiness.py:8)
- Control matrix em database/models/readiness.py:47-74 com versionamento
- Lineage building blocks: raw_zone.py, MetricFactLineage, post-mortem lineage validation
- Append-only patterns: financial facts (revision_number), metric observations (idempotent inserts), raw zone (immutable)
- Kill switch com 4-eyes (paper_execution.py:536-605) e endpoints (paper_execution.py:456-485)

**Gaps críticos:**
- `threat-model.md` e `bcp-dr.md` permanecem como STUBS (19 e 21 linhas)
- Sem GET endpoints para listar decision packs, votes, dissent, ou findings
- Sem ControlMatrixVersion model (manifest é JSONB livre)
- Sem end-to-end lineage query (segments existem individualmente)
- Sem SLO definitions ou breach tracking
- Sem drift detection
- Sem model risk inventory formal
- PERSONA_PERMISSIONS não mapeia readiness:verify/freeze
- Proteção contra SQL direto é apenas app-layer (sem triggers/RLS)
