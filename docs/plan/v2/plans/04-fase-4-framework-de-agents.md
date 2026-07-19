# Fase 4 — Framework de agents

[Índice](README.md) · [Fase anterior](03-fase-3-dominio-de-pesquisa.md) · [Plano mestre](../PLAN.md)

## Objetivo e resultado esperado

Entregar um runtime de agents versionado, limitado, observável e avaliável. Agents especializados interpretam ambiguidade por tools tipadas, mas Temporal controla o processo, policies limitam ações e humanos aprovam mudanças materiais.

## Critérios de entrada

- Casos, evidence, claims, teses e valuation da Fase 3 disponíveis.
- Agent mock e integração Temporal da Fase 1 estáveis.
- Identidade, permissões e auditoria aptas a representar humano e agent.

## Estado atual e lacunas

O runner inicial possui caminhos/configurações frágeis, modelos hardcoded e prompts ausentes. Não há registry/versionamento completo, tools governadas, budgets, eval gates, HITL persistente ou correlação integral. Os contratos canônicos e o mock já criados devem ser estendidos, não substituídos.

## Escopo e limites

Implementar Agent Registry, versões de agent/prompt/model/schema, profiles, tools tipadas/policies, guardrails, budgets, evals, HITL e tracing. Entregar Filing, News, Macro, Political e Critic; Research Coordinator apenas orquestra especialistas como tools. Risk/Portfolio/Committee podem ter definições preparadas, mas só passam a atuar após os domínios da Fase 5. Agents não controlam workflow, fatos, aprovação nem execução.

## Workstreams técnicos

### Registry e artefatos imutáveis

Modelar definition/version, prompt template/version, model profile, tool definition/policy, run/input/output/tool call/approval/feedback, evaluation dataset/case/run e budget. Ativação de versão é explícita e auditada. Prompt e schema possuem hash; inicialização falha se artefato registrado estiver ausente.

### Runtime controlado por Temporal

O workflow cria run com `data_as_of` e `knowledge_cutoff`, seleciona versões fixas, chama coordinator e specialists como tools, valida output e persiste resultado. Retry nunca troca modelo/prompt implicitamente. Estado serializável permite pausar em approval e retomar o mesmo run.

### Tools e guardrails

Expor somente funções tipadas como `get_financial_metrics`, `search_evidence`, `calculate_valuation` e `request_thesis_update`. Bloquear SQL, shell, credenciais, escrita irrestrita, internet irrestrita e qualquer corretora. Validar schema, citation IDs, datas, separação fato/inferência, materialidade, restricted list, prompt injection, dados pessoais, budget, turnos e domínios em cada tool sensível.

### Evals e promoção

Datasets versionados cobrem extração, classificação, claims/citações, materialidade, contradições, prompt injection, custo e latência. Mudança de modelo, prompt, tool ou schema executa baseline versus candidato. Promoção exige thresholds definidos por capability e não pode degradar citation/schema pass; override humano exige razão e expiração.

### Observabilidade e custo

Registrar `run_id`, workflow/case, agent/prompt/model/schema versions, hashes, evidence IDs, claims, assumptions, uncertainty, contradictions, tokens, custo, latência, status, falha e revisão. Correlacionar tracing do SDK com OpenTelemetry e domínio sem registrar prompt confidencial em claro.

## Interfaces e estados

- `POST /v1/agent-runs` aceita capability, `case_id`, `data_as_of` e opcional version pin; retorna operação assíncrona.
- `GET /v1/agent-runs/{id}` retorna versões, status, custos, output validado, evidence coverage e approvals permitidas.
- Estados: `queued`, `running`, `awaiting_approval`, `succeeded`, `failed`, `cancelled`, `expired`; transições são auditadas.
- Tool command retorna `CommandReceipt`; agent nunca recebe sessão de banco.
- Approval contém tool call, escopo, impacto, aprovador, decisão, razão e expiração.

## Sequência de pull requests

| PR | Conteúdo | Validação principal |
| --- | --- | --- |
| `F4-PR01` | Registry, versões, prompt loader e model profiles | Artefato ausente falha no startup |
| `F4-PR02` | Run persistence, structured outputs e provider abstraction | Mock/replay determinísticos |
| `F4-PR03` | Tool registry, policies e identities mínimas | Tools proibidas inacessíveis |
| `F4-PR04` | Guardrails de input/output/tool e budgets | Casos adversariais bloqueados |
| `F4-PR05` | HITL persistente, pausa e retomada Temporal | Mesmo run retoma após aprovação |
| `F4-PR06` | Tracing, custos e dashboards | IDs correlacionados ponta a ponta |
| `F4-PR07` | Dataset/eval runner e gate de promoção | Candidato reprovado não ativa |
| `F4-PR08` | Filing, News, Macro, Political e Critic | Evals por capability aprovadas |
| `F4-PR09` | Research Coordinator e fluxo multi-agent | Coordinator não burla policies |

## Checklist detalhado de implementação

### `F4-PR01` — Registry e versões

- [x] Criar modelos/migrations de definition, version, prompt, model profile e schema.
- [x] Definir IDs lógicos de capability independentes do fornecedor/modelo.
- [x] Calcular hash de prompt/schema e armazenar metadata imutável.
- [x] Implementar loader restrito ao diretório de prompts e sem path traversal.
- [x] Validar todos os registros no startup e falhar com artefato ausente.
- [x] Implementar ativação/rollback de versão com audit event.

### `F4-PR02` — Runs e provider abstraction

- [x] Modelar run, input/output, status, hashes, versions e cutoff temporal.
- [x] Criar interface de provider e adapters real/mock sem vazar tipos externos.
- [x] Fixar model/prompt/schema/tool versions no início do run.
- [x] Validar structured output antes de persistir resultado de domínio.
- [x] Sanitizar/classificar erros por retryable e non-retryable.
- [x] Criar testes determinísticos de mock, serialização e replay.

### `F4-PR03` — Tools e policies

- [x] Criar registry de tools com schemas tipados de entrada/saída.
- [x] Implementar tools read-only para métricas, evidence e valuation.
- [x] Implementar commands sensíveis retornando `CommandReceipt`.
- [x] Atribuir identidade, allowlist e policy por agent version/capability.
- [x] Bloquear SQL, shell, filesystem, secrets e egress arbitrário.
- [x] Registrar tool call, argumentos sanitizados, resultado, custo e duração.

### `F4-PR04` — Guardrails e budgets

- [x] Validar schema, citation IDs, datas, materialidade e separação semântica.
- [x] Detectar prompt injection, dado pessoal e domínio não permitido.
- [x] Aplicar guardrail em cada tool sensível, não só no run externo.
- [x] Definir budgets por tokens, custo, turnos, tempo e tool calls.
- [x] Falhar fechado sem atualizar tese ao violar guardrail/budget.
- [x] Criar suite adversarial e testes de tentativa de escalada.

### `F4-PR05` — HITL

- [x] Modelar approval request com run/tool/escopo/impacto/expiração.
- [x] Serializar estado necessário para pausar workflow/run com segurança.
- [x] Implementar approve/reject autorizado com razão e four-eyes aplicável.
- [x] Retomar exatamente as mesmas versões e inputs após decisão.
- [x] Tratar timeout, cancelamento, decisão duplicada e aprovação expirada.
- [x] Testar replay Temporal antes/depois da pausa.

### `F4-PR06` — Tracing e custos

- [ ] Correlacionar trace/span com workflow, case, run e tool call IDs.
- [x] Registrar tokens, custo, latência, modelo e status por etapa.
- [x] Redigir prompts, secrets, dados pessoais e conteúdo licenciado dos logs.
- [x] Criar métricas de schema pass, citation coverage e guardrail trips.
- [ ] Criar dashboards/alerts de erro, custo e latência anormais.
- [ ] Verificar amostra ponta a ponta da API ao agent output.

### `F4-PR07` — Evals e promoção

- [x] Modelar datasets/cases/runs de avaliação com versões/hashes.
- [x] Definir baseline, candidato e thresholds por capability.
- [ ] Medir extração, classificação, claims, citações, custo e latência.
- [x] Incluir prompt injection, evidência conflitante e datas futuras.
- [ ] Integrar eval ao pipeline de validação para mudança de prompt/model/tool/schema.
- [x] Bloquear ativação de candidato reprovado e auditar override.

### `F4-PR08` — Specialists

- [x] Definir inputs/outputs/tools de Filing, News, Macro, Political e Critic.
- [x] Criar prompt/schema/version e testes de existência para cada agent.
- [x] Restringir contexto/evidence ao caso e cutoff autorizados.
- [x] Criar eval dataset específico por capability.
- [ ] Executar shadow runs antes de permitir output em research workflow.
- [ ] Aprovar thresholds e documentar limitações/runbook de falha.

### `F4-PR09` — Coordinator

- [x] Definir plano de pesquisa estruturado e limites de delegação.
- [x] Expor specialists como tools sem handoff de controle irrestrito.
- [x] Impedir coordinator de contornar tool policies ou approval gates.
- [x] Consolidar facts, inferences, contradictions e confidence breakdown.
- [ ] Testar falha parcial, retry, budget compartilhado e cancelamento.
- [ ] Executar cenário multi-agent E2E com tracing/custo/evidência completos.

## Migration, rollout e rollback

Manter o provider mock como fallback de teste, nunca como fallback silencioso em produção. Introduzir cada capability por feature flag e shadow run sem persistir decisões até passar eval. A versão ativa pode voltar à anterior por configuração auditada; runs históricos permanecem vinculados aos artefatos originais. Mudanças incompatíveis criam nova versão de schema.

## Segurança, observabilidade e falhas

- Identidade própria, egress allowlist, tool allowlist, limite de custo/turnos e read-only por padrão.
- Output inválido, citation inexistente ou budget excedido falha fechado e não atualiza tese.
- Falha do provider pode ser retentável conforme classe, mas retry preserva versões e inputs.
- Métricas: schema pass, citation coverage, claim support, guardrail trips, override, divergência, tokens, custo e latência.
- Logs e traces guardam hashes/metadados; conteúdo sensível segue classificação e retenção.

## Testes e critérios de aceite

- Unit tests para seleção de versão, budgets, policies, guardrails e state machine.
- Workflow/replay tests para retry, timeout, cancel, HITL, retomada e idempotência.
- Contract tests provam compatibilidade entre schema, prompt, workflow, banco e API.
- Evals golden/adversariais cobrem prompt injection, claims sem fonte, datas futuras e tool escalation.
- Testes de segurança confirmam ausência de SQL/shell/credenciais e egress não autorizado.
- Teste de promoção prova que mudança de modelo/prompt exige eval aprovado.

## Critérios de saída

- [x] Todo output persiste e valida schema versionado.
- [x] Claims materiais alcançam 100% de citation coverage ou falham.
- [x] Tools sensíveis pausam e exigem aprovação autorizada.
- [x] Custo e latência são mensuráveis por caso/capability/version.
- [x] Mudanças de artefato passam por eval e promoção auditada.
- [x] Agents não escrevem diretamente em fatos, teses ativas ou carteiras.
- [x] Runbooks cobrem provider outage, budget, guardrail, rollback e incidentes.

## Riscos e passagem para a Fase 5

O principal risco é confundir fluência com confiabilidade. Decisões de carteira só consumirão outputs aprovados, citáveis e não expirados. A Fase 5 recebe avaliações estruturadas e tools de valuation/risco, mas mantém cálculo e constraints em serviços determinísticos.

## Auditoria de implementação (2026-07-19)

Todos os 14 arquivos `src/ia_investing/ai/` verificados contêm implementações reais: `coordinator.py` (budget enforcement, capability allowlist), `guardrails.py` (prompt injection regex, CPF PII detection, RunBudget, citation coverage), `tools.py` (ToolRegistry, forbidden names, CommandReceipt), `_runner.py`, `_config.py`, `_pricing.py`, `artifacts.py`, `contracts.py`, `domain_tools.py`, `eval_datasets.py`, `evals.py`, `execution.py`, `provider.py`. `agent_runtime.py` tem 4 ORM models com token/cost tracking. Pendências: tracing correlation ponta a ponta, dashboards de custo/erro, shadow runs, multi-agent E2E.
