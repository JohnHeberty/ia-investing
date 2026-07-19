# Fase 8 — Operação paper institucional

[Índice](README.md) · [Fase anterior](07-fase-7-inteligencia-politica-e-macro.md) · [Plano mestre](../PLAN.md)

## Objetivo e resultado esperado

Operar carteiras paper de forma contínua, reconciliada e auditável, simulando o ciclo de ordens, fills, custos e pós-negociação sem conexão com uma corretora real. Toda negociação deve derivar de versão aprovada e seu resultado deve ser atribuível à decisão que a originou.

## Critérios de entrada

- Carteiras/NAV/risco/backtest e RebalanceWorkflow aprovados na Fase 5.
- Comitê, approvals, identidade e auditoria funcionando pelo painel.
- Dados de mercado, corporate actions e calendário possuem SLO e reconciliação.
- Runbooks e on-call técnico disponíveis para operação paper contínua.

## Estado atual e lacunas

A Fase 5 entrega apenas snapshots, propostas e base de execução. Ainda faltam lifecycle operacional de trade intent/order/fill, simulação realista, reconciliação, alertas, post-mortem e governança champion/challenger. Não há integração live e ela permanece proibida.

## Escopo e limites

Implementar trade intents, ordens paper, fills, fees/taxes, slippage, estados, cancelamento/expiração, reconciliação, alertas, post-mortem, attribution e champion/challenger. Toda interface externa é um simulador interno claramente identificado como paper. Não criar adaptador de corretora, credencial de trading, FIX, envio de ordem ou estado `live` habilitável.

## Workstreams técnicos

### Modelo operacional e state machines

`trade_intent` referencia portfolio version/rebalance proposal/decision e contém instrumento, lado, quantidade/valor alvo, janela, limites e razão. Após approvals, gera `order` paper. Estados mínimos da intenção: `draft -> pending_approval -> approved -> submitted -> completed|cancelled|expired|failed`; ordem: `created -> accepted -> partially_filled -> filled|cancelled|rejected|expired`. Transições inválidas falham fechado e são auditadas.

### Simulador de execução

Simular tipo de ordem permitido, lotes, horário/calendário, spread, profundidade/liquidez, participação, latência, partial fills, slippage, fee e tax conforme configuração versionada. Nunca usar preço anterior ao sinal/approval. Seeds e regras ficam no input snapshot para replay determinístico quando desejado.

### Reconciliação e NAV

Comparar intents, orders, fills, transações, posições, caixa e NAV. Diferença gera `reconciliation` com severidade/estado; incidente crítico bloqueia novas intenções da carteira. Reprocessamento é idempotente e correção usa lançamento compensatório ou nova versão, nunca edição destrutiva de fill.

### Operação, alertas e post-mortem

Alertar rejeição, fill atrasado, slippage/custo acima do limite, divergência, breach e schedule atrasado. Post-mortem liga esperado versus realizado, cenário/tese/agent/comitê, qualidade dos inputs e erro operacional/modelo. Notificação deve ser deduplicada, roteável por severidade e reconhecível.

### Champion/challenger

Comparar dentro do mesmo mandato, benchmark, risco, horizonte e janela out-of-sample/paper. Uma champion e até N challengers configurados; promoção nunca é automática e exige critérios pré-registrados, comitê e nova versão. Registrar survivorship, mudanças de metodologia e ablações.

## Interfaces

- Queries: intents, orders, fills, reconciliations, alerts e attribution, com filtros por carteira/estado/data e `as_of`.
- Commands: aprovar/rejeitar/cancelar intent, executar simulação autorizada, reconhecer/resolver reconciliação e abrir post-mortem.
- Não expor endpoint `send-order`; todos os recursos e telas exibem `environment=paper`.
- Eventos: `TradeIntentApproved`, `PaperOrderAccepted`, `PaperFillRecorded`, `ReconciliationBreakDetected`, `PaperNavReconciled` e `PostMortemCompleted`.

## Sequência de pull requests

| PR | Conteúdo | Validação principal |
| --- | --- | --- |
| `F8-PR01` | Trade intents, orders/fills e state machines paper | Transições/constraints unitárias |
| `F8-PR02` | Execution simulator, custos, impostos e slippage | Golden/replay determinísticos |
| `F8-PR03` | RebalanceWorkflow completo e approvals | Idempotência/replay/four-eyes |
| `F8-PR04` | Posições, caixa, NAV e reconciliação diária | Property/golden accounting |
| `F8-PR05` | Alertas, notificações, incidentes e runbooks | Deduplicação/escalation tests |
| `F8-PR06` | Attribution e post-mortem | Lineage decisão-resultado |
| `F8-PR07` | Champion/challenger e promotion pack | Sem promoção automática |
| `F8-PR08` | Painel operacional e operação paper E2E | Ciclo contínuo sem ação técnica |

## Checklist detalhado de implementação

### `F8-PR01` — Intents, orders e fills paper

- [x] Modelar trade intent ligado a versão/proposta/decisão aprovada.
- [x] Modelar order/fill/fee/tax com `environment=paper` obrigatório.
- [x] Implementar state machines e tabela de transições autorizadas.
- [x] Aplicar unique/idempotency constraints a submit e eventos de fill.
- [x] Impedir overfill, fill pós-cancelamento e instrumento fora do mandato.
- [ ] Emitir audit/domain events em cada transição material. *(Parcial: DomainOutboxEvent emitido para intent (Created/Approved/Rejected/Cancelled) e simulate (OrderSimulated). Falta: PaperOrder status changes (accepted→partially_filled→filled/cancelled/rejected/expired) não emitem outbox events individuais)*
- [ ] Testar concorrência, duplicidade, expiração, cancelamento e rejeição. *(NÃO TESTADO: test_paper_execution.py cobre state machine e simulação determinística. Falta: concurrent order submission, duplicate fill prevention (submit_key), intent expiration no service, cancel/reject paths)*

### `F8-PR02` — Simulador de execução

- [x] Definir tipos de ordem paper e regras de lote/horário/calendário.
- [x] Versionar modelos de spread, liquidez, participação, slippage e latência.
- [x] Implementar partial fills e prioridade determinística/documentada.
- [x] Calcular fees/taxes conforme perfil e configuração versionados.
- [x] Garantir preço posterior ao sinal e approvals.
- [x] Persistir input snapshot, seed e versão do simulador.
- [ ] Criar golden tests para cenários líquidos/ilíquidos e gap de mercado. *(NÃO IMPLEMENTADO: nenhum golden test para paper execution. test_simulation_is_deterministic testa cenário líquido único. Falta: cenário ilíquido (baixa liquidez), gap de mercado (market_open=False), e golden tests com outputs esperados)*

### `F8-PR03` — RebalanceWorkflow completo

- [ ] Carregar somente versão aprovada e validar freshness/risco novamente. *(Parcial: create_intent e simulate verificam status=="approved". PaperRebalanceWorkflow NÃO carrega versão nem re-valida freshness/risco — é puro approval gate)*
- [ ] Calcular diff, custos, liquidez e intents determinísticos. *(NÃO IMPLEMENTADO no workflow: PaperRebalanceWorkflow é 59 linhas puro approval gate. Domínio tem simulate_order e fill_to_ledger, mas não há diff de posições, agregação de custos, ou validação de liquidez)*
- [x] Pausar para approvals exigidos por mandato e segregação.
- [x] Submeter ao simulador de forma idempotente.
- [ ] Tratar fill parcial, cancelamento, janela expirada e kill switch. *(Parcial: domínio/serviço tratam partial fill, cancel, expiry e kill switch. Porém PaperRebalanceWorkflow não manipula nenhum desses — são lógicas de serviço, não do workflow)*
- [x] Atualizar estado sem escrever diretamente em snapshots reconciliados.
- [ ] Testar crash/retry/replay e aprovação duplicada/expirada. *(NÃO TESTADO: nenhum teste de workflow temporal para PaperRebalanceWorkflow. Falta: crash recovery, retry, replay determinism, duplicate approval signal, expired timeout, kill signal)*

### `F8-PR04` — Ledger e reconciliação

- [x] Registrar fills como lançamentos append-only no ledger paper.
- [ ] Atualizar projeções de posição/caixa por processamento idempotente. *(Parcial: idempotência existe para intents, simulation e reconciliation breaks. Porém simulate() cria fills e ledger entries MAS NÃO atualiza PositionSnapshot ou CashSnapshot — projeções não são derivadas incrementalmente)*
- [ ] Calcular e publicar NAV somente após reconciliação. *(verificado: PaperValuationWorkflow executa reconcile_paper_portfolio antes de publish_paper_nav; activity-level verifica publication.reconciled==True)*
- [ ] Comparar intents, orders, fills, ledger, posições, caixa e NAV. *(Parcial: reconcile_execution compara orders↔fills e fills↔ledger. Falta: intent-level invariants, positions vs ledger aggregate, cash balance vs ledger, NAV vs computed)*
- [x] Criar break com severidade, impacto, owner role e estado.
- [ ] Corrigir por lançamento compensatório/nova versão, nunca editando fill. *(Parcial: API aceita compensating_reference, mas resolve_break() apenas seta status="resolved" — não cria lançamento compensatório. Fills são append-only imutáveis)*
- [ ] Testar identidade contábil, corporate actions e quebra injetada. *(Parcial: identidade contábil testada (test_nav_preserves_accounting_identity). Corporate actions testadas no backtest, não no paper NAV. Reconciliation breaks testados em domain unit, não via service layer com injeção)*

### `F8-PR05` — Alertas e operação

- [ ] Definir catálogo de alertas, severidades, canais e escalonamento. *(Parcial: OperationalAlert model existe com severity/route/status. Falta: catálogo de tipos (só "reconciliation_break" é gerado), canais de notificação (route é string livre), regras de escalation)*
- [ ] Alertar rejeição, atraso, slippage/custo, break, breach e schedule. *(NÃO IMPLEMENTADO: único alert_type gerado é "reconciliation_break". Falta: alertas de rejeição, atraso, slippage/custo acima do limite, breach de risco, schedule atrasado)*
- [x] Deduplicar por recurso/regra/janela e permitir acknowledge auditado.
- [x] Bloquear novas operações diante de condição crítica configurada.
- [x] Implementar kill switch por carteira e global com autoridade explícita.
- [ ] Criar dashboards/SLOs e testar notification outage/flood control. *(NÃO IMPLEMENTADO: nenhum endpoint de dashboard, definição de SLO, tratamento de notification outage, ou flood control)*
- [ ] Exercitar runbooks de suspensão, recuperação e reconciliação. *(NÃO EXERCITADO: runbook existe em docs/plan/v2/runbooks/paper-operations.md, mas nenhum teste/exercício valida o procedimento end-to-end)*

### `F8-PR06` — Attribution e post-mortem

- [x] Vincular resultado a tese, cenário, agent, decisão e trades.
- [x] Calcular attribution por ativo, setor, fator, decisão e custos.
- [x] Comparar esperado, backtest, paper e resultado realizado.
- [x] Classificar erro de dado, modelo, decisão, execução ou operação.
- [x] Registrar ação corretiva, owner role, prazo e verificação.
- [x] Preservar versão do relatório e dissenso humano.
- [ ] Criar golden/E2E de lineage decisão-resultado. *(NÃO IMPLEMENTADO: validate_post_mortem_lineage existe no domínio, mas nenhum teste E2E/golden traça lineage de decisão → trade → fill → ledger → NAV)*

### `F8-PR07` — Champion/challenger

- [x] Definir N, janela, benchmark, risco e critérios por mandato.
- [x] Garantir comparação out-of-sample/paper e mesma base de custos.
- [x] Calcular performance, drawdown, estabilidade e divergências.
- [x] Aplicar gates de dados, tese, risco, liquidez e histórico mínimo.
- [x] Criar promotion pack imutável com evidências/limitações.
- [ ] Exigir comitê e nova versão para qualquer promoção. *(Parcial: comitê obrigatório (4-eyes, DB constraint decision_requires_human). Falta: decide_challenger NÃO cria nova InstitutionalPortfolioVersion — promove decisão mas não gera nova versão)*
- [ ] Testar survivorship, mudança metodológica e tentativa automática. *(NÃO TESTADO: methodology_version existe no model mas não há testes de survivorship, mudança metodológica, ou prevenção de auto-promoção)*

### `F8-PR08` — Operação E2E

- [x] Criar telas/queries/actions para intents, orders, fills e breaks.
- [x] Exibir permanentemente o ambiente paper em todos os recursos.
- [x] Configurar schedules de valuation, rebalance e reconciliação.
- [ ] Executar ciclo completo sem intervenção técnica rotineira. *(NÃO AUTÔNOMO: schedules definidos (reconciliation, valuation diários; rebalance semanal). Porém PaperRebalanceWorkflow SEMPRE pausa em awaiting_approval — ciclo completo requer intervenção humana)*
- [ ] Injetar falha de fonte, worker, preço, fill e reconciliação. *(NÃO IMPLEMENTADO: nenhum teste de fault injection em todo o test suite)*
- [ ] Exercitar kill switch e retomada sob aprovação. *(Parcial: kill switch implementado com 4-eyes release. Falta: zero testes exercitam ativação → blocking → release → retomada)*
- [ ] Publicar evidências de SLO, attribution, auditoria e post-mortem. *(Parcial: post-mortem create endpoint existe, audit log populado. Falta: endpoints de SLO, query de audit logs, list de post-mortems/challenger evaluations)*
- [x] Confirmar ausência de endpoint, SDK, secret ou egress de corretora.

## Migration, rollout e rollback

Iniciar com uma carteira e universo reduzido, depois ampliar por feature flag/mandato. Rodar shadow simulation para comparar o simulador com preços de referência antes de publicar NAV paper. Versões de custo/slippage nunca recalculam histórico silenciosamente. Rollback suspende schedules e novas intents, deixa cancelamento/reconciliação ativos e preserva ledger append-only.

## Segurança, observabilidade e falhas

- Serviço paper não recebe credenciais, SDKs ou rede para corretoras; egress segue allowlist de dados.
- Quatro olhos e segregação impedem criador de aprovar/executar sozinho quando policy exigir.
- Kill switch paper pausa novas intents/orders sem impedir leitura, cancelamento e reconciliação.
- Métricas: order/fill rates, latency, rejection, slippage, costs, breaks, NAV freshness, breaches e divergência backtest/paper.
- Falta de preço, calendário, aprovação, liquidez ou risco válido bloqueia execução; nunca usa fallback silencioso.

## Testes e critérios de aceite

- Property tests preservam caixa/posição/NAV e impedem overfill, fill após cancelamento e violação de lote.
- Golden tests cobrem partial fills, custos, impostos, proventos, split e slippage.
- Workflow/replay tests cobrem approval, retry, crash, cancel, expiration, duplicate event e kill switch.
- Testes de reconciliação injetam divergências e validam bloqueio/escalation/resolução.
- E2E percorre proposta aprovada, intents, fills, NAV, alertas, attribution e post-mortem.
- Security tests provam ausência de endpoint/credencial/egress de execução live.

## Critérios de saída

- [ ] Carteira paper opera pelos schedules sem intervenção técnica manual rotineira. *(PaperRebalanceWorkflow sempre requer approval manual — ciclo não é autônomo)*
- [x] Toda negociação referencia versão, proposta e decisão aprovadas.
- [ ] Ledger, posições, caixa e NAV reconciliam diariamente. *(Parcial: reconciliation diária agendada, compara orders/fills/ledger. Falta: reconciliação explícita de positions e cash como entidades independentes)*
- [x] Divergências críticas bloqueiam e alertam conforme policy.
- [x] Custos/slippage são versionados e atribuídos.
- [x] Champion/challenger usa janela comparável e aprovação humana.
- [x] Post-mortem liga decisão, expectativa e resultado realizado.
- [ ] Runbooks e kill switch foram exercitados. *(Runbook paper-operations.md existe. Kill switch não foi exercitado/testado)*

## Riscos e passagem para a Fase 9

Paper trading pode subestimar latência, capacidade e fricções reais. Resultados devem declarar limitações e divergência frente a backtest. A Fase 9 recebe histórico operacional, incidentes, SLOs, exercícios de recuperação e evidências de controles; não recebe autorização automática para live.

## Auditoria de implementação (2026-07-19)

8 ORM models em `paper_execution.py` (276 lines: TradeIntent, PaperOrder, PaperFill, ReconciliationBreak, OperationalAlert, PaperKillSwitch, PaperPostMortem, ChallengerEvaluation) com CheckConstraints rigorosos. 5 Temporal workflows: `_paper_rebalance.py` (signal/query/kill — 59 linhas, puro approval gate), `_paper_reconciliation.py` (activity call), `_paper_valuation.py` (reconciliation→NAV), `_approval_gate.py` (wait_condition/signal/query), `_portfolio_construction.py` (role-based voting, 109 lines).

**Pendências restantes (não implementadas ou parciais):**
- Domain events incompletos (falta order-level outbox events)
- Testes de concorrência/duplicidade/expiração/cancelamento/rejeição inexistentes
- Golden tests para cenários ilíquidos/gap de mercado inexistentes
- PaperRebalanceWorkflow é puro approval gate — não calcula diff/custos/liquidez
- Testes de workflow behavioral (crash/retry/replay/idempotency) inexistentes
- Reconciliação não cobre intents/positions/cash/NAV como entidades independentes
- Compensating entries não implementadas (só documenta referência)
- Alertas limitados a "reconciliation_break" — falta catálogo, canais, escalation
- Dashboards/SLOs/notification outage/flood control inexistentes
- Runbook paper-operations.md existe mas não foi exercitado
- Kill switch implementado mas zero testes
- E2E lineage decisão-resultado inexistente
- Champion/challenger: committee enforced mas nova versão não criada na promoção
- Survivorship/methodology change testing inexistente
- Ciclo completo não é autônomo (rebalance sempre requer approval manual)
- Fault injection testing inexistente
- Post-mortem/attribution endpoints de list inexistentes
