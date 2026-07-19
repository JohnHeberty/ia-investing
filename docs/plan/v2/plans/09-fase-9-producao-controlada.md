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
- [ ] Mapear CVM 19/20/21 e demais obrigações identificadas por especialista.
- [ ] Definir responsabilidades profissionais, disclosures e conflitos.
- [ ] Definir suitability e retenção somente quando aplicáveis ao perímetro.
- [ ] Obter parecer jurídico assinado com premissas, restrições e validade.
- [x] Registrar item `no-go` para qualquer conclusão ausente ou inconclusiva.

### `F9-PR02` — Licenças e retenção

- [ ] Inventariar toda fonte/dataset/documento/model input usado em produção.
- [ ] Comprovar direitos de coletar, armazenar, transformar, exibir e modelar.
- [ ] Registrar território, usuários, retenção, redistribuição e expiração.
- [ ] Mapear dado derivado e lineage até outputs/decisões.
- [ ] Implementar/remediar retenção, exclusão e mudança de termos.
- [ ] Remover/substituir conteúdo sem direito comprovado.
- [ ] Obter aprovação de Jurídico/Data Governance para cada fonte crítica.

### `F9-PR03` — Segurança independente

- [x] Atualizar data flow diagram, trust boundaries e threat model.
- [ ] Revisar OIDC/MFA, RBAC+ABAC, four-eyes e service identities.
- [ ] Revisar secrets, rotação, criptografia, egress, TLS e rate limits.
- [ ] Revisar audit append-only, restricted list e segregação de ambientes.
- [ ] Executar pentest e scans de dependência, secret, SAST e container.
- [ ] Classificar findings, corrigir e obter reteste independente.
- [x] Bloquear gate enquanto houver finding crítico aberto.

### `F9-PR04` — Continuidade e kill switch

- [ ] Definir serviços/dados críticos, RTO, RPO e dependências.
- [ ] Verificar backups, retenção, criptografia e acesso de restauração.
- [ ] Restaurar stack/dados em ambiente isolado e reconciliar integridade.
- [ ] Exercitar disaster recovery e medir RTO/RPO observados.
- [ ] Exercitar source outage, worker loss, replay e reconciliation break.
- [ ] Exercitar kill switch global/por carteira e autoridade de retomada.
- [ ] Atualizar BCP, on-call, comunicação e post-mortem com evidências.

### `F9-PR05` — Model risk e evidência paper

- [ ] Inventariar modelos, versões, datasets, prompts e owners por papel.
- [ ] Documentar finalidade, limites, métricas, drift e critérios de retirada.
- [ ] Executar validação independente de dados, metodologia e resultados.
- [ ] Revisar overrides, guardrails, calibração e champion/challenger.
- [ ] Consolidar backtest PIT, paper, custos, slippage e divergências.
- [ ] Demonstrar janela/SLO definidos sem breach crítico ignorado.
- [ ] Obter parecer formal de Model Risk/Risco sobre risco residual.

### `F9-PR06` — Control matrix

- [x] Mapear cada obrigação/risco para controle preventivo/detectivo.
- [x] Atribuir owner role, frequência, evidência e procedimento de teste.
- [x] Vincular findings, remediações, retestes e exceções com expiração.
- [ ] Amostrar lineage de fonte até decisão paper e audit event.
- [ ] Confirmar que nenhum controle depende de edição manual não auditada.
- [ ] Validar segregação e cobertura com Jurídico, Segurança, Risco e Operações.
- [ ] Congelar versão da matriz usada no decision pack.

### `F9-PR07` — Decision pack e go/no-go

- [ ] Reunir pareceres, auditorias, exercícios, métricas e control matrix.
- [ ] Listar findings/condições/riscos residuais sem omitir dissenso.
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

- [ ] Finalidade/perímetro e parecer jurídico estão formalmente aprovados.
- [ ] Toda fonte crítica possui direitos e retenção comprovados.
- [ ] Segurança foi auditada e não há finding crítico aberto.
- [ ] Segregação de funções, quatro olhos e restricted list foram testados.
- [ ] Backup, restore, DR, kill switch e reconciliação foram exercitados.
- [ ] Paper trading atende a janela/SLOs definidos sem breach crítico ignorado.
- [ ] Model risk governance e validação independente estão aprovados.
- [ ] Decision pack, votos, condições, dissenso e validade estão assinados/auditados.
- [x] Nenhuma credencial, endpoint ou integração de execução real foi criada.

## Resultado do gate

- **`no_go`:** manter somente capacidades autorizadas; remediar findings e repetir o gate.
- **`conditional_go`:** cumprir e validar todas as condições; repetir decisão antes de avançar.
- **`go`:** autorizar a criação de um novo plano para arquitetura e implementação live, com fornecedor, controles e rollout próprios. Não autoriza implementação ou envio de ordem real.

O gate deve falhar fechado diante de parecer ausente, licença incerta, finding crítico, controle não testado, paper instável ou decisão expirada.
