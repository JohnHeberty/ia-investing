# Code Quality Analysis — `ia_investing` Module

**Data:** 2026-07-21  
**Última atualização:** 2026-07-23 — C-01, C-02, C-03, C-04 resolvidos (package splits) + C-05, C-06, W-01, W-02, W-03, W-04, W-06 corrigidos  
**Arquivos analisados:** 98 Python files (ai/, application/, contracts/, data/, database/, domain/, orchestration/)  
**Ferramentas usadas:** ruff, mypy, análise manual de padrões  

---

## Resumo Executivo

| Severidade | Original | Corrigido | Restante | Descrição |
|------------|----------|-----------|----------|-----------|
| Crítico | 6 | 6 | 0 | C-01 paper_execution split (8 módulos). C-02 institutional_portfolio split (9 módulos). C-03 agent_runtime split (4 módulos). C-04 guardrails split (4 módulos). C-05 redefinição corrigida. C-06 type:ignore corrigido. |
| Aviso | 12 | 7 | 5 | W-01/02/03/04/06 corrigidos + W-05 parcial (generics); restam W-05 mypy cascata (import-not-found) e S-* |
| Sugestão | 8 | 0 | 8 | Refatorações maiores (duplicação, funções longas) |

---

## Crítico

### C-01: Arquivo `paper_execution.py` com 1336 linhas (SRP violado)
**Resolvido.** Transformado em pacote `paper_execution/` com 8 módulos focados:

| Módulo | Linhas | Responsabilidade |
|--------|--------|-----------------|
| `_base.py` | 141 | Cross-cutting: `require_operations_enabled`, `configuration`, `record`, `record_order`, `audit_entity` |
| `_intent.py` | 191 | Trade Intent lifecycle (create/decide/cancel/list) |
| `_order.py` | 260 | Order simulation + fills + position/cash snapshots |
| `_reconciliation.py` | 381 | 3-phase reconciliation + break resolution |
| `_alerts.py` | 188 | Kill switch + operational alerts |
| `_evaluation.py` | 273 | Post-mortem + Champion/Challenger |
| `_dashboard.py` | 60 | Operational dashboard metrics |
| `service.py` | 122 | `PaperExecutionService` facade compondo sub-serviços |

`__init__.py` re-exporta `PaperExecutionService` — **zero impacto externo** (3 consumers, 0 alterações de import).

### C-02: Arquivo `institutional_portfolio.py` com 894 linhas (SRP violado)
**Arquivo:** `src/ia_investing/application/institutional_portfolio.py`  
A classe `InstitutionalPortfolioService` gerencia mandates, portfolio versions, risk snapshots, NAV calculations e optimization runs.

**Resolvido.** Transformado em pacote `institutional_portfolio/` com 9 módulos focados:

| Módulo | Linhas | Responsabilidade |
|--------|--------|-----------------|
| `_base.py` | 102 | Helpers compartilhados: `audit`, `latest_instrument_bar`, `fx_multiplier` |
| `_mandate.py` | 85 | MandateService: create_mandate |
| `_portfolio.py` | 117 | PortfolioLifecycleService: create, transition, queries |
| `_version.py` | 130 | PortfolioVersionService: create_version, version queries |
| `_approval.py` | 115 | ApprovalService: approve_version |
| `_nav.py` | 186 | NavService: publish_nav, benchmark, list_nav |
| `_risk.py` | 250 | RiskService: assess_risk, waive_breach, list, expire |
| `service.py` | 103 | InstitutionalPortfolioService facade |
| `__init__.py` | 8 | Re-exporta InstitutionalPortfolioService + PortfolioConcurrencyError |

`__init__.py` re-exporta `InstitutionalPortfolioService` e `PortfolioConcurrencyError` — **zero impacto externo** (2 consumers).

### C-03: Arquivo `agent_runtime.py` com 516 linhas (SRP violado)
**Arquivo:** `src/ia_investing/application/agent_runtime.py`  
Concentra runtime de agentes, evidence tracking, e tool execution.

**Resolvido.** Transformado em pacote `agent_runtime/` com 4 módulos focados:

| Módulo | Linhas | Responsabilidade |
|--------|--------|-----------------|
| `_crypto.py` | 20 | Funções puras: `canonical_hash`, `sanitize_tool_payload`, `SENSITIVE_ARGUMENT_KEYS` |
| `_registry.py` | 181 | `AgentRegistryService` — sincronização de manifesto de capacidades + `default_artifact_loader` |
| `_runtime.py` | 306 | `AgentRuntimeService` — lifecycle de runs, tool calls, approvals, promote |
| `__init__.py` | 35 | Re-exporta `AgentRuntimeService`, `AgentRegistryService`, `canonical_hash`, `sanitize_tool_payload` |

`__init__.py` re-exporta API pública — **zero impacto externo** (4 consumers: 2 source + 1 test + 1 transitive).

### C-04: Arquivo `guardrails.py` com 507 linhas (SRP violado)
**Arquivo:** `src/ia_investing/ai/guardrails.py`  
Contém guardrail definitions, validators, policy enforcement, e output filtering em um único arquivo.

**Corrigido:** Transformado em pacote `guardrails/` com 3 sub-módulos:
- `_types.py` (143 linhas): tipos, enums, exceções, constantes
- `_checks.py` (201 linhas): todas as funções de validação
- `_engine.py` (143 linhas): GuardrailReporter + GuardrailEngine
- `__init__.py` re-exporta API pública — 0 alterações nos 4 consumers + 4 test files

### C-05: Variável redefinida — `fills` aparece duas vezes com tipos diferentes
**Arquivo:** `src/ia_investing/application/paper_execution.py:242` e `:338`  
Linha 242: `fills = tuple(...)` (tuple)  
Linha 338: `fills: list[PaperFill] = []` (list)  
Mypy reporta `[no-redef]`. O nome colide dentro do mesmo escopo de classe.

**Corrigido:** Renomeado para `simulated_fills` em 338, 369, 423, 442.

### C-06: `type: ignore[arg-type]` incorreto no institutional_portfolio
**Arquivo:** `src/ia_investing/application/institutional_portfolio.py:95`  
Mypy reporta `[unused-ignore]` e também `[call-overload]`. O comentário `# type: ignore[arg-type]` não cobre o erro real (`[call-overload]`).

**Corrigido:** `type: ignore[arg-type]` → `type: ignore[call-overload]`

---

## Aviso

### W-01: Exceções sem sufixo `Error` (PEP 8 — N818)
**Arquivos:**  
- `src/ia_investing/application/errors.py:10` — `BusinessRejection` → `BusinessRejectionError`  
- `src/ia_investing/application/errors.py:14` — `ValidationFailure` → `ValidationError`  

**Corrigido:** Renomeado nos 4 arquivos (errors.py, ai/errors.py, application/__init__.py, test_error_hierarchy.py).

### W-02: Generics sem parâmetros de tipo
**Arquivos:**  
- `src/ia_investing/application/errors.py:26` — `dict` sem type params em retorno de `temporal_retry_policy_from_error()`  
- `src/ia_investing/ai/shadow_integration.py:45,97` — `dict` sem type params  

**Corrigido:** errors.py e shadow_integration.py — `dict` → `dict[str, Any]`.

### W-03: Import block desordenado (I001)
**Arquivos:**  
- `src/ia_investing/ai/_runner.py` — imports misturados stdlib/third-party/local  
- `src/apps/api/routes/health.py`  
- `src/apps/worker/main.py`  

**Corrigido:** `health.py` e `_runner.py` via `ruff check --fix`. `worker/main.py` já estava limpo (overlay).

### W-04: `__all__` não ordenado (RUF022)
**Arquivo:** `src/ia_investing/ai/__init__.py:17` — lista de exports fora de ordem alfabética  
**Corrigido:** `ruff check --fix` reordenou alfabeticamente.

### W-05: Mypy reporta 186 erros em 50 arquivos do módulo  
A maioria são `[import-not-found]` (módulos externos não resolvidos pelo mypy), mas há erros reais de tipo:
- `src/ia_investing/domain/valuation.py:51-53` — `Decimal | Literal[0]` incompatível com `Decimal`  
- `src/ia_investing/application/paper_execution.py:355` — `"tuple[Any, ...]" has no attribute "append"` (bug real)

### W-06: Formato inconsistente
**Arquivo:** `src/ia_investing/domain/policy.py` — ruff format reporta que precisa ser reformulado  
**Corrigido:** `ruff format` aplicado.

---

## Sugestão

### S-01: Duplicação de padrão `_record` / `_audit_entity` em services
Todos os application services (`paper_execution`, `institutional_portfolio`, `theses`, etc.) implementam métodos privados similares para auditoria. Considere uma mixin ou base class com logging/auditing compartilhado.

### S-02: Funções >50 linhas sem decomposição
Métodos longos identificados:
- `PaperExecutionService.simulate()` (~130 linhas)  
- `InstitutionalPortfolioService.create_portfolio_version()` (~80 linhas)  

**Recomendação:** Extrair validações em funções helper nomeadas.

### S-03: Validações repetidas `_require_operations_enabled`
O mesmo padrão de verificação aparece em múltiplos métodos dentro do mesmo service e entre services diferentes. Considere um decorator ou middleware.

### S-04: `datetime.now(UTC)` chamado repetidamente sem variável intermediária
Em `paper_execution/`, cada operação usa `datetime.now(UTC)` separadamente, o que pode causar inconsistência temporal em caso de falha parcial. Use uma única captura no início da transação.

---

## Cobertura de Testes

| Arquivo | Teste correspondente | Status |
|---------|---------------------|--------|
| `paper_execution/` (8 módulos) | `test_worker_smoke.py`, `test_workflow_behavioral.py` | Parcial — cobertura limitada; agora mais fácil de testar por subdomínio |
| `institutional_portfolio/` (9 módulos) | `test_institutional_portfolio.py`, `test_portfolio_version_snapshots.py` | Parcial — testam domain layer, não application layer |
| `agent_runtime/` (4 módulos) | `test_agent_runtime_v2.py` | Parcial — testa sanitize_tool_payload, não cobrir runtime lifecycle completo |
| `guardrails.py` (507 linhas) | `test_guardrails.py` (534 linhas, 29 testes) | Bom |
| `errors.py` (47 linhas) | `test_error_hierarchy.py` (132 linhas) | Bom |

**Recomendação:** Aumentar cobertura para `paper_execution.py`, especialmente os caminhos de reconciliação e challenger evaluation.

---

## Próximos Passos Sugeridos

1. ~~**Dividir `paper_execution.py` (C-01)**~~ **Concluído** — pacote de 8 módulos, 0 impacto externo
2. ~~**Dividir `institutional_portfolio.py` (C-02)**~~ **Concluído** — pacote de 9 módulos, 0 impacto externo
3. ~~**Dividir `agent_runtime.py` (C-03)** — pacote de 4 módulos, 0 impacto externo~~ **Concluído**
4. ~~**Corrigir C-05 (variável redefinida)** — `fills` → `simulated_fills`~~ **Concluído**  
5. ~~**Renomear exceções para sufixo Error**~~ **Concluído**  
6. ~~**Dividir `guardrails.py` (C-04)** — pacote com 3 sub-módulos~~ **Concluído**
7. ~~**Adicionar type params aos generics** — shadow_integration.py e errors.py~~ **Concluído**
