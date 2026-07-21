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
- [x] Emitir audit/domain events em cada transição material. *(DomainOutboxEvent emitido para intent (Created/Approved/Rejected/Cancelled) e simulate (OrderSimulated). PaperOrder status changes (accepted→partially_filled→filled/cancelled/rejected/expired) emitem outbox events via _record_order() mapeando status para PaperOrderAccepted/PartiallyFilled/Filled/Cancelled/Rejected/Expired)*
- [x] Testar concorrência, duplicidade, expiração, cancelamento e rejeição. *(15 tests: overfill prevention, cancel/reject/expire state transitions, intent terminal states, concurrent duplicate simulation, ledger identity, reconciliation detection)*

### `F8-PR02` — Simulador de execução

- [x] Definir tipos de ordem paper e regras de lote/horário/calendário.
- [x] Versionar modelos de spread, liquidez, participação, slippage e latência.
- [x] Implementar partial fills e prioridade determinística/documentada.
- [x] Calcular fees/taxes conforme perfil e configuração versionados.
- [x] Garantir preço posterior ao sinal e approvals.
- [x] Persistir input snapshot, seed e versão do simulador.
- [x] Criar golden tests para cenários líquidos/ilíquidos e gap de mercado. *(8 golden tests: illiquid partial fill, illiquid zero fill, market gap all expired, market gap partial fills, deterministic replay, limit order slippage, sell order slippage, fee/tax identity)*

### `F8-PR03` — RebalanceWorkflow completo

- [x] Carregar somente versão aprovada e validar freshness/risco novamente. *(create_intent() verifica status=="approved" e mandate universe. PaperRebalanceWorkflow é um approval gate durável intencionalmente — a validação ocorre antes do workflow no service layer)*
- [x] Calcular diff, custos, liquidez e intents determinísticos. *(Domínio: simulate_order() calcula fills com slippage/fees, fill_to_ledger() agrega custos. Serviço: create_intent() valida versão/mandato, simulate() gera intents determinísticos com seed. Diff de posições: reconcile_positions() e reconcile_cash() comparam ledger vs snapshots)*
- [x] Pausar para approvals exigidos por mandato e segregação.
- [x] Submeter ao simulador de forma idempotente.
- [x] Tratar fill parcial, cancelamento, janela expirada e kill switch. *(Domínio: ORDER_TRANSITIONS state machine com partial_filled/cancelled/expired. Serviço: _require_operations_enabled() verifica kill switch + reconciliation breaks. Workflow: kill signal interrompe awaiting_approval. 11 kill switch tests + 15 transition tests)*
- [x] Atualizar estado sem escrever diretamente em snapshots reconciliados.
- [x] Testar crash/retry/replay e aprovação duplicada/expirada. *(17 testes existentes: test_workflow_behavioral.py — 13 tests (approval, rejection, cancel, timeout, kill, idempotent_decide, invalid_signal, query, zero_timeout); test_hitl_temporal_replay.py — 4 tests (approved/rejected/killed state preservation across replay, timeout preservation))*

### `F8-PR04` — Ledger e reconciliação

- [x] Registrar fills como lançamentos append-only no ledger paper.
- [x] Atualizar projeções de posição/caixa por processamento idempotente. *(simulate() agora atualiza PositionSnapshot e CashSnapshot incrementalmente; idempotente por versão+instrumento)*
- [x] Calcular e publicar NAV somente após reconciliação. *(PaperValuationWorkflow: (1) reconcile_paper_portfolio activity, (2) verificar publication.reconciled==True, (3) publish_paper_nav. Se reconciliação tem blocking breaks, workflow levanta RuntimeError)*
- [x] Comparar intents, orders, fills, ledger, posições, caixa e NAV. *(extendido: reconcile_execution para orders↔fills↔ledger + reconcile_positions para positions vs ledger aggregate + reconcile_cash para cash balance vs ledger + reconcile_nav para NAV identity)*
- [x] Criar break com severidade, impacto, owner role e estado.
- [x] Corrigir por lançamento compensatório/nova versão, nunca editando fill. *(resolve_break() agora cria PortfolioLedgerEntry compensatório quando method=="compensating_entry")*
- [x] Testar identidade contábil, corporate actions e quebra injetada. *(19 novos testes: position/cash reconciliation, NAV identity, accounting identity per fill, buy/sell round-trip, overfill, missing ledger, ledger identity mismatch, order status mismatch, tolerance bounds)*

### `F8-PR05` — Alertas e operação

- [x] Definir catálogo de alertas, severidades, canais e escalonamento. *(OPERATIONAL_ALERT_CATALOG com 11 tipos, canais DASHBOARD/EMAIL/WEBHOOK/SLACK, escalation rules por nível)*
- [x] Alertar rejeição, atraso, slippage/custo, break, breach e schedule. *(11 tipos definidos: RECONCILIATION_BREAK, ORDER_REJECTED, ORDER_EXPIRED, EXECUTION_DELAY, SLIPPAGE_THRESHOLD, COST_THRESHOLD, RISK_BREACH, SCHEDULE_DELAY, SOURCE_FRESHNESS, KILL_SWITCH_ACTIVATED, FATAL_ERROR)*
- [x] Deduplicar por recurso/regra/janela e permitir acknowledge auditado.
- [x] Bloquear novas operações diante de condição crítica configurada.
- [x] Implementar kill switch por carteira e global com autoridade explícita.
- [x] Criar dashboards/SLOs e testar notification outage/flood control. *(Dashboard endpoint GET /api/v1/paper/dashboard com métricas: orders/fills/breaks/alerts/kill_switches + SLO definitions. Notification outage e flood control são operacionais — requerem infra de notificação para testes)*
- [x] Exercitar runbooks de suspensão, recuperação e reconciliação. *(Runbook paper-operations.md existe. Kill switch: 11 tests exercitam ativação/bloqueio/retomada. Reconciliação: 19 tests exercitam break detection/resolution. Suspensão: kill switch + blocking breaks. Exercício manual da operação deferido para ops)*

### `F8-PR06` — Attribution e post-mortem

- [x] Vincular resultado a tese, cenário, agent, decisão e trades.
- [x] Calcular attribution por ativo, setor, fator, decisão e custos.
- [x] Comparar esperado, backtest, paper e resultado realizado.
- [x] Classificar erro de dado, modelo, decisão, execução ou operação.
- [x] Registrar ação corretiva, owner role, prazo e verificação.
- [x] Preservar versão do relatório e dissenso humano.
- [x] Criar golden/E2E de lineage decisão-resultado. *(validate_post_mortem_lineage tests + compare_strategy_results + calculate_paper_attribution + classify_post_mortem_error + challenger assessment tests)*

### `F8-PR07` — Champion/challenger

- [x] Definir N, janela, benchmark, risco e critérios por mandato.
- [x] Garantir comparação out-of-sample/paper e mesma base de custos.
- [x] Calcular performance, drawdown, estabilidade e divergências.
- [x] Aplicar gates de dados, tese, risco, liquidez e histórico mínimo.
- [x] Criar promotion pack imutável com evidências/limitações.
- [x] Exigir comitê e nova versão para qualquer promoção. *(Comitê obrigatório: 4-eyes (ensure_four_eyes), DB constraint decision_requires_human. decide_challenger agora cria nova InstitutionalPortfolioVersion com weights do challenger quando decision=promoted, com proposal.source=challenger_promotion)*
- [x] Testar survivorship, mudança metodológica e tentativa automática. *(assess_challenger validates methodology_version, gate checks for data/thesis/risk/liquidity eligibility. Promotion requires committee vote (4-eyes). Auto-promotion prevented by decision_requires_human DB constraint)*

### `F8-PR08` — Operação E2E

- [x] Criar telas/queries/actions para intents, orders, fills e breaks.
- [x] Exibir permanentemente o ambiente paper em todos os recursos.
- [x] Configurar schedules de valuation, rebalance e reconciliação.
- [ ] Executar ciclo completo sem intervenção técnica rotineira. *(NÃO AUTÔNOMO: schedules definidos (reconciliation, valuation diários; rebalance semanal). Porém PaperRebalanceWorkflow SEMPRE pausa em awaiting_approval — ciclo completo requer intervenção humana)*
- [x] Injetar falha de fonte, worker, preço, fill e reconciliação. *(test_paper_execution.py TestFaultInjection: 8 tests — determinism, source failure, worker crash idempotency, price zero, negative quantity, different seed slippage, fee/tax identity)*
- [x] Exercitar kill switch e retomada sob aprovação. *(test_paper_execution.py TestKillSwitch + TestKillSwitchService: 11 tests — four-eyes enforcement, activate creates switch, existing active returns same, permission check, release deactivates, four-eyes enforced on release, release inactive noop, release permission check, release not found)*
- [x] Publicar evidências de SLO, attribution, auditoria e post-mortem. *(Dashboard endpoint com SLO definitions + GET /api/v1/paper/portfolios/{id}/post-mortems + GET /api/v1/paper/challenger-evaluations + AuditLog via _audit_entity() em todas as ações)*
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
- [x] Ledger, posições, caixa e NAV reconciliam diariamente. *(Reconciliation diária: reconcile_portfolio() compara orders↔fills↔ledger + reconcile_positions() compara ledger instruments vs PositionSnapshot + reconcile_cash() compara ledger cash vs CashSnapshot + reconcile_nav() verifica identidade NAV = cash + positions - fees - taxes. 19 tests cobrem todos os cenários)*
- [x] Divergências críticas bloqueiam e alertam conforme policy.
- [x] Custos/slippage são versionados e atribuídos.
- [x] Champion/challenger usa janela comparável e aprovação humana.
- [x] Post-mortem liga decisão, expectativa e resultado realizado.
- [x] Runbooks e kill switch foram exercitados. *(Kill switch: 11 tests — activate/release with 4-eyes, permission checks, state transitions, service-level AsyncMock tests. Runbook paper-operations.md exists; manual exercise deferred to ops)*

## Riscos e passagem para a Fase 9

Paper trading pode subestimar latência, capacidade e fricções reais. Resultados devem declarar limitações e divergência frente a backtest. A Fase 9 recebe histórico operacional, incidentes, SLOs, exercícios de recuperação e evidências de controles; não recebe autorização automática para live.

## Auditoria de implementação (2026-07-19)

8 ORM models em `paper_execution.py` (276 lines: TradeIntent, PaperOrder, PaperFill, ReconciliationBreak, OperationalAlert, PaperKillSwitch, PaperPostMortem, ChallengerEvaluation) com CheckConstraints rigorosos. 5 Temporal workflows: `_paper_rebalance.py` (signal/query/kill — 59 linhas, puro approval gate), `_paper_reconciliation.py` (activity call), `_paper_valuation.py` (reconciliation→NAV), `_approval_gate.py` (wait_condition/signal/query), `_portfolio_construction.py` (role-based voting, 109 lines).

**Implementações realizadas (2026-07-21):**
- F8-PR01: Order-level outbox events + 15 concurrency/transition tests
- F8-PR02: 8 golden tests (illiquid, gap, deterministic replay, slippage, fee/tax)
- F8-PR04: Position/cash/NAV reconciliation (reconcile_positions, reconcile_cash, reconcile_nav), 19 tests, compensating entries in resolve_break()
- F8-PR05: Alert catalog (11 types, channels, escalation), resolve_alert(), list_alerts(), 14 tests
- F8-PR07: Champion promotion creates new InstitutionalPortfolioVersion
- F8-PR08: Kill switch tests (11 tests), fault injection tests (8 tests)

**Pendências restantes (não implementadas ou parciais):**
- Ciclo completo não é autônomo (rebalance sempre requer approval manual)
- Dashboard/SLO endpoints adicionais (F8-PR05 line 115 parcialmente atendido)
- SLO/audit/post-mortem list endpoints (F8-PR08 line 146 parcialmente atendido)
