# Fase 5 — Carteiras, risco e backtest

[Índice](README.md) · [Fase anterior](04-fase-4-framework-de-agents.md) · [Plano mestre](../PLAN.md)

## Objetivo e resultado esperado

Criar um domínio institucional de carteiras-modelo, risco e simulação. Ao final, uma carteira e seu NAV são reproduzíveis em qualquer data, propostas respeitam mandato/limites, falhas do solver são explícitas e backtests passam por gates point-in-time e anti-look-ahead.

## Critérios de entrada

- Dados, preços, corporate actions e calendários point-in-time aprovados.
- Teses/valuation versionados e outputs de agents governados.
- Temporal, auditoria, identidade e contratos assíncronos estáveis.

## Estado atual e lacunas

O modelo atual reduz carteira a nome/capital e posição mutável com ticker/preço atual. Faltam mandato, benchmark, versões, caixa, NAV, snapshots, custos, risk policies, ordens e reconciliação. O otimizador aceita dados do cliente, pode cair em equal weight inválido e roda CPU-bound no contexto inadequado. O backtest pode incluir benchmark no universo e usar informação futura.

## Escopo e limites

Implementar mandatos, carteiras-modelo, versões aprovadas, snapshots de posição/caixa, NAV/performance, benchmarks, risk policies/snapshots/breaches, stresses, otimizador corrigido, backtest PIT e base mínima de paper execution. A automação diária de ordens/fills/reconciliação e champion/challenger operacional ficam na Fase 8. Nenhuma carteira live ou corretora entra nesta fase.

## Workstreams técnicos

### Identidade e autorização institucional

Concluir organizações, usuários, equipes, memberships, roles, permissions, service identities e contexto de auditoria. Aplicar RBAC+ABAC por organização, equipe, carteira, estratégia, classificação, estado e ambiente paper/live. Esse incremento sucede o OIDC mínimo da Fase 1 e deve estar ativo antes de criar ou aprovar qualquer mandato.

### Mandato, carteira e versionamento

`strategy_mandate` define objetivo, estratégia, universo, benchmark, moeda, horizonte, rebalanceamento, risk budget, volatilidade/drawdown, concentração, fatores, liquidez, caixa, turnover, exclusões, custos, impostos e política de aprovação. Carteira-modelo tem estados `draft -> researching -> simulated -> committee_review -> approved -> paper_live -> eligible_for_live -> live -> suspended -> archived`; nesta fase, transições após `paper_live` permanecem bloqueadas.

`portfolio_version` é imutável e referencia mandato, teses, valuation, input snapshot, proposta, decisão e pesos aprovados. Posição guarda quantidade em `position_snapshot`; valor usa preço válido no `as_of`. Nunca persistir “preço atual” como propriedade da posição.

### NAV, performance e ranking

Calcular caixa, posições, proventos, custos, impostos, benchmark, P&L e NAV por fechamento reconciliado. Revisões criam nova publicação, sem apagar cálculo anterior. Top X compara somente carteiras de mesma categoria/risco/horizonte/moeda/estágio e exige mandato, histórico, NAV/benchmark completos, backtest PIT, versão aprovada, teses saudáveis e ausência de breach crítico.

### Risco e stress

Versionar policies, limites, modelos e cenários. Produzir exposures, liquidez, concentração, volatilidade, drawdown e stress por input snapshot. Limite hard bloqueia proposta; waiver exige autoridade, razão e validade. Risco pode rejeitar/condicionar, mas não editar tese ou proposta.

### Otimização

Construir retornos, covariância e restrições exclusivamente no backend. Validar viabilidade antes do solver, executar em worker dedicado e persistir solver/version/tolerâncias/inputs/slacks. Resultado inclui status, pesos, trades, retorno/risco, liquidez, turnover, custos, constraints vinculantes e diagnósticos. `infeasible` nunca retorna equal weight como sucesso.

### Backtest point-in-time

Reconstruir universo, dados conhecidos, tickers, corporate actions, delistings, IPOs, preços, liquidez, custos, impostos e calendário em cada data. Separar sinal e execução, benchmark e universo investível, treino e out-of-sample. Comparar benchmark, equal weight, estratégia quantitativa sem agents e ablações de notícias/política/LLM.

## Interfaces

- Queries: carteiras, versões, NAV, posições, performance, risco, breaches, proposals e backtests, todas com `as_of` quando temporais.
- Commands: criar mandato/carteira, gerar rebalance proposal, executar stress, solicitar backtest e submeter versão ao comitê.
- Proposta contém versão de inputs, trades, custos, impactos, constraints/slacks, teses e pareceres; alteração gera nova proposta.
- Backtest config é imutável e retorna operation ID; resultado guarda code/data/config versions e hashes.
- Eventos: `PortfolioVersionProposed`, `RiskBreachOpened`, `PortfolioVersionApproved`, `NavPublished` e `BacktestCompleted`.

## Sequência de pull requests

| PR | Conteúdo | Validação principal |
| --- | --- | --- |
| `F5-PR01` | Identity, organizações, RBAC+ABAC e audit context (PR-012) | Segregação/autorização integradas |
| `F5-PR02` | Mandatos, model portfolios e state machine (PR-013) | Transições/policies unitárias |
| `F5-PR03` | Versions, position/cash snapshots e benchmarks | Snapshot imutável/reprodutível |
| `F5-PR04` | NAV, proventos, custos e performance | Identidade contábil/property tests |
| `F5-PR05` | Risk policies, limits, snapshots, stress e breaches | Hard limit sempre bloqueia |
| `F5-PR06` | Optimizer backend/worker, diagnostics e persistência | Infeasible falha fechado |
| `F5-PR07` | Backtest engine PIT e universo histórico | Anti-look-ahead suite |
| `F5-PR08` | PortfolioConstruction/Committee/Rebalance workflows mínimos | Replay e approval tests |
| `F5-PR09` | API, Top X elegibilidade e cenário E2E | Contract + reprodução por data |

## Checklist detalhado de implementação

### `F5-PR01` — Identity e autorização institucional

- [x] Modelar organizations, users, teams, memberships, roles e permissions.
- [x] Modelar service identities e vínculo entre agent/worker e organização.
- [x] Integrar claims OIDC a usuário, organização e sessão auditável.
- [x] Implementar RBAC e atributos de carteira/estratégia/estado/ambiente.
- [x] Criar matriz de permissões por persona do plano mestre.
- [x] Implementar four-eyes e impedir autoaprovação quando configurado.
- [x] Testar isolamento entre organizações e tentativas de privilege escalation.

### `F5-PR02` — Mandatos e carteiras-modelo

- [x] Modelar todos os campos obrigatórios do mandato com unidade e constraints.
- [x] Modelar model portfolio, owner team, moeda, estratégia e estado.
- [x] Implementar state machine sem saltos e com razão/auditoria.
- [x] Versionar policies de aprovação ligadas ao mandato.
- [x] Validar universo, benchmark, cash range e limites coerentes.
- [x] Criar commands/queries e testes de autorização/transição.

### `F5-PR03` — Versions e snapshots

- [x] Modelar `portfolio_version` imutável com mandato e input snapshot.
- [x] Modelar position/cash snapshots com instrumento, quantidade e `as_of`.
- [x] Remover ticker/preço atual como propriedade canônica da posição.
- [x] Resolver preço e ticker pela versão válida no instante do snapshot.
- [x] Vincular versão a teses, valuation, proposta e decisão.
- [x] Testar reprodução, revisão, corporate action e instrumento deslistado. *(Implementado: test_portfolio_version_snapshots.py com 9 testes — version revision deterministic hash, split adjusts quantity, dividend adds to cash, JCP net of tax, delist removes position + adds cash, delisted excluded from future universe, delisted with liquidation price)*

### `F5-PR04` — NAV e performance

- [x] Definir ledger/transações mínimas para caixa, proventos, fees e taxes.
- [x] Implementar cálculo de market value, P&L, NAV e benchmark.
- [x] Aplicar corporate actions e FX conhecidos no `as_of`.
- [x] Versionar metodologia e input snapshot do cálculo.
- [x] Reconciliar identidade contábil antes de publicar NAV.
- [x] Criar golden/property tests e fluxo de republicação auditada.

### `F5-PR05` — Risco e stress

- [x] Modelar risk policy/limit/model/version/snapshot/breach/waiver.
- [x] Implementar concentração, fatores, liquidez, volatilidade e drawdown.
- [x] Implementar stress scenarios versionados e resultados reproduzíveis.
- [x] Classificar limites hard/soft e ações de bloqueio/alerta.
- [x] Exigir autoridade, razão e expiração para waiver.
- [x] Testar breach, waiver, expiração, restricted list e dado stale.

### `F5-PR06` — Otimizador

- [x] Construir retornos/covariância/constraints somente no backend.
- [x] Validar dimensões, qualidade, universo e viabilidade antes do solver.
- [x] Executar CVXPY em worker CPU-bound com timeout/cancelamento.
- [x] Persistir solver/version/tolerâncias/inputs/status/slacks/diagnósticos.
- [x] Retornar `infeasible`/`failed` sem equal-weight silencioso.
- [x] Testar universos pequenos, constraint conflitante, cash e restricted list.
- [x] Comparar resultado contra solução conhecida em golden tests.

### `F5-PR07` — Backtest PIT

- [x] Definir configuração imutável com universe, dates, delay, custos e seed.
- [x] Reconstruir universo/tickers/constituintes conhecidos em cada data.
- [x] Separar publicação, sinal e preço/horário de execução.
- [x] Aplicar delistings, IPOs, corporate actions, dividendos/JCP e impostos.
- [x] Manter benchmark fora do conjunto investível.
- [x] Implementar walk-forward, out-of-sample e baselines/ablações. *(Implementado: _walk_forward.py com rolling windows, _baselines.py com 4 baselines — equal-weight, market-cap-proxy, momentum, sector-neutral — e testes unitários)*
- [x] Criar suite anti-look-ahead e teste de hash/reprodutibilidade.

### `F5-PR08` — Workflows de decisão

- [x] Implementar PortfolioConstructionWorkflow com snapshots fixos.
- [x] Executar elegibilidade, retorno esperado, risco, optimizer e constraints. *(Implementado: PortfolioConstructionWorkflow._run_pipeline() encadeia run_scorecard → optimize_model_portfolio → validate_proposal_constraints. PipelineConfig define inputs brutos. Rejeição de elegibilidade/optimizer/hard_breach retorna early antes do committee review. 22 testes passando.)*
- [x] Gerar proposta imutável e pareceres de Risk/Compliance. *(verificado: SHA-256 hashing em decision_pack_sha256, PortfolioDecisionInputs com risk_opinion/compliance_opinion, validate_decision_inputs() fail-closed, approve_version() valida risk snapshot sem hard breaches)*
- [x] Implementar decision pack, quórum, votos, condições e assinatura.
- [x] Criar versão aprovada sem executar ordem live.
- [x] Implementar RebalanceWorkflow somente até intents paper aprováveis.
- [x] Testar pause/approval/retry/replay/idempotência e rejeição. *(Implementado: 48 testes em test_workflow_behavioral.py cobrindo ApprovalGate, PaperRebalance, PolicyEvent, PortfolioConstruction e ThesisReview workflows — approval, rejection, cancel, timeout, idempotency, signal buffering, conditional approval, self-approve rejection, duplicate actor, unauthorized role, kill, non-material shortcut, contradiction detection.)*

### `F5-PR09` — APIs, ranking e E2E

- [x] Criar endpoints de mandato, carteira, versão, NAV, posição, risco e backtest.
- [x] Criar commands assíncronos de proposal, stress e backtest. *(Implementado: OperationService.submit_portfolio_operation() suporta 202+Location com idempotência e dispatch via Temporal. Endpoints de optimization, risk-assessment e backtests agora retornam 202 com Location header. 16 testes unitários em test_async_commands.py.)*
- [x] Implementar filtros/cursor/ETag/`as_of` e response schemas dedicados. *(verificado: cursor com X-Next-Cursor em list_model_portfolios, ETag/If-Match em transitions, as_of em NAV/backtests, 18+ Pydantic V1 response schemas)*
- [x] Implementar elegibilidade Top X por categoria comparável. *(Implementado: rank_portfolios_by_category agrupa por ComparableCategory — strategy_type/risk_level/horizon/currency/stage — e ordena por final_score com penalidades. 13 testes unitários + 9 E2E)*
- [x] Calcular score/penalidades com versão e freshness explícitas. *(Implementado: calculate_penalty_score() aplica penalidades por thesis_expired, freshness_low, critical_breach, data_stale, version_stale; PortfolioRankingEntry com final_score. 13 testes)*
- [x] Executar E2E de mandato a versão aprovada/NAV reproduzível. *(Implementado: test_mandate_to_nav_e2e.py com 9 testes — mandate validation, full lifecycle (5 transitions), decision pack immutability, four-eyes enforcement, NAV reproducibility, NAV non-negative, top_x eligibility, backtest reproducibility, ineligible excluded from ranking)*
- [x] Provar que carteira inelegível ou breach crítico não aparece no ranking.

## Migration, rollout e rollback

Criar o novo domínio em paralelo ao CRUD legado. Importações geram carteira/versão marcada como `legacy_import`, sem inventar aprovações ou histórico. Leitura muda por feature flag após reconciliação; escrita legada é desativada antes da remoção. Snapshots/NAV/backtests são append-only. Rollback volta os leitores e suspende novos workflows sem apagar versões ou transações.

## Segurança, observabilidade e falhas

- Gestor propõe; risco condiciona/rejeita; comitê aprova; nenhuma pessoa aprova a própria ação quando policy exigir quatro olhos.
- Dados enviados pelo cliente nunca definem retornos, preços, covariância ou limites canônicos.
- Métricas: NAV freshness, breaches, solver status/latência, infeasibility, backtest duration, turnover e divergência entre proposta/resultado.
- Preço ausente, NAV não reconciliado, tese expirada ou dado em quarentena bloqueiam elegibilidade conforme policy.
- CPU-heavy optimization/backtest executa fora do event loop com timeout/cancelamento seguros.

## Testes e critérios de aceite

- Property tests: pesos/caixa fecham 100%, limites não são ultrapassados e NAV preserva identidade.
- Golden tests de custos, proventos, corporate actions, benchmark, stress e performance.
- Testes integrados para versões, concorrência, outbox, solver e workflows de aprovação.
- Anti-look-ahead altera dado futuro e prova passado invariável; benchmark nunca recebe peso.
- Reprodutibilidade executa o mesmo input/code/config e obtém os mesmos hashes/resultados dentro da tolerância.
- Security tests exercitam segregação, restricted list, waiver e tentativa de client-supplied returns.

## Critérios de saída

- [x] Carteira, posições, caixa e NAV são reproduzíveis por data.
- [x] Toda versão aprovada liga mandato, inputs, teses, risco e decisão.
- [x] Propostas respeitam constraints e mostram diagnósticos/slacks. *(verificado: _optimizer.py com CVXPY, slacks, diagnostics; _portfolio_construction.py com role-based voting)*
- [x] Solver nunca mascara falha com fallback inválido.
- [x] Backtest passa por suite PIT, replay e anti-look-ahead.
- [x] Apenas carteiras elegíveis aparecem no ranking comparável. *(Implementado: rank_portfolios_by_category filtra por top_portfolio_eligible() antes de agrupar. Inelegíveis (approved=False ou critical_breach=True) são excluídos. 9 testes E2E)*
- [x] Runbooks cobrem NAV, breach, solver, backtest e suspensão.

## Riscos e passagem para a Fase 6

O risco é exibir precisão aparente sobre inputs incompletos. Confidence/freshness e bloqueios devem acompanhar todo resultado. A Fase 6 recebe APIs de leitura estáveis, commands auditáveis, estados e componentes de domínio necessários à jornada visual.

## Auditoria de implementação (2026-07-19)

Todos os 4 artefatos verificados existem e são implementações reais: `identity.py` (8 ORM models: Organization, User, Team, Role, Permission), `portfolio_domain.py` (StrategyMandate com 20+ cols e 8 checks, ModelPortfolio com 10 states, 426 lines), `_optimizer.py` (CVXPY mean-variance com 12 parâmetros, solver fallback, 229 lines), `_engine.py` (event-driven backtest com CAGR/Sharpe/Sortino/Calmar, 260 lines).

**Itens marcados como [x] confirmados:** Identity/RBAC/ABAC completo, mandatos com 20+ campos, model portfolio 10 states, position/cash snapshots, NAV com reconciliation, risk policies/limits/stress/breaches/waiver, optimizer com infeasible fail-closed, backtest PIT com anti-look-ahead suite.

**Pendências restantes (não implementadas ou parciais):**
- ~~Testes de revisão de versão, corporate action em snapshots e delist~~ ✅ Implementado
- ~~Walk-forward/out-of-sample NÃO implementados (só validation helpers)~~ ✅ Implementado
- ~~Baselines além de equal-weight inexistentes~~ ✅ 4 baselines implementadas
- ~~PortfolioConstructionWorkflow não orquestra elegibilidade→risco→optimizer~~ ✅ Pipeline chain implementado
- ~~Nenhum teste de workflow behavioral (pause/approval/retry/replay/idempotency)~~ ✅ 48 testes implementados
- ~~Commands assíncronos (202) para proposals/stress/backtest inexistentes~~ ✅ 202+Location com OperationService
- ~~Top X ranking por categoria comparável não implementado~~ ✅ rank_portfolios_by_category
- ~~Score/penalidades dinâmicas não calculadas~~ ✅ calculate_penalty_score
- ~~Nenhum teste E2E mandato→versão→approval→NAV~~ ✅ test_mandate_to_nav_e2e.py
- ~~Ranking eligibility não wired em nenhum endpoint~~ ✅ Filtrado por top_portfolio_eligible
