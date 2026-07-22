# Code Quality Analysis — `ia_investing` Module

**Data:** 2026-07-21  
**Arquivos analisados:** 98 Python files (ai/, application/, contracts/, data/, database/, domain/, orchestration/)  
**Ferramentas usadas:** ruff, mypy, análise manual de padrões  

---

## Resumo Executivo

| Severidade | Original | Corrigido | Restante | Descrição |
|------------|----------|-----------|----------|-----------|
| Crítico | 6 | 2 | 4 | Arquivos >500 linhas (SRP) — paper_execution, institutional_portfolio, agent_runtime, guardrails |
| Aviso | 12 | 5 | 7 | type hints, imports, __all__, exceções |
| Sugestão | 8 | 0 | 8 | Refatorações maiores (duplicação, funções longas) |

---

## Crítico

### C-01: Arquivo `paper_execution.py` com 1336 linhas (SRP violado)
**Arquivo:** `src/ia_investing/application/paper_execution.py`  
A classe `PaperExecutionService` concentra toda a lógica de execução paper em um único arquivo gigante. Contém criação de intents, simulação, reconciliação, challenger evaluation e post-mortem — responsabilidades distintas que merecem módulos separados.

**Recomendação:** Dividir em:
- `paper_intent.py` — create/decide/cancel intent (~200 linhas)
- `paper_simulation.py` — simulate/fill logic (~350 linhas)  
- `paper_reconciliation.py` — reconcile ledger, breaks (~400 linhas)
- `paper_challenger.py` — challenger evaluation, post-mortem (~250 linhas)

### C-02: Arquivo `institutional_portfolio.py` com 894 linhas (SRP violado)
**Arquivo:** `src/ia_investing/application/institutional_portfolio.py`  
A classe `InstitutionalPortfolioService` gerencia mandates, portfolio versions, risk snapshots, NAV calculations e optimization runs. Cada subdomínio deveria ter seu próprio service module.

**Recomendação:** Dividir em:
- `mandate_service.py` — create/update mandate (~150 linhas)
- `portfolio_version_service.py` — version creation/approval/evidence (~300 linhas)
- `risk_snapshot_service.py` — risk limits, breaches, waivers (~250 linhas)

### C-03: Arquivo `agent_runtime.py` com 516 linhas (SRP violado)
**Arquivo:** `src/ia_investing/application/agent_runtime.py`  
Concentra runtime de agentes, evidence tracking, e tool execution. O módulo deveria ser particionado entre agent lifecycle management e tool/evidence handling.

### C-04: Arquivo `guardrails.py` com 507 linhas (SRP violado)
**Arquivo:** `src/ia_investing/ai/guardrails.py`  
Contém guardrail definitions, validators, policy enforcement, e output filtering em um único arquivo.

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

**Recomendação:** Usar `dict[str, int]`, `dict[str, Any]`, etc.  
**Corrigido (parcial):** errors.py `dict` → `dict[str, Any]`. Pendente: shadow_integration.py.

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
Em `paper_execution.py`, cada operação usa `datetime.now(UTC)` separadamente, o que pode causar inconsistência temporal em caso de falha parcial. Use uma única captura no início da transação.

---

## Cobertura de Testes

| Arquivo | Teste correspondente | Status |
|---------|---------------------|--------|
| `paper_execution.py` (1368 linhas) | `test_worker_smoke.py`, `test_workflow_behavioral.py` | Parcial — cobertura limitada para arquivo tão grande |
| `guardrails.py` (507 linhas) | `test_guardrails.py` (534 linhas, 29 testes) | Bom |
| `errors.py` (47 linhas) | `test_error_hierarchy.py` (132 linhas) | Bom |

**Recomendação:** Aumentar cobertura para `paper_execution.py`, especialmente os caminhos de reconciliação e challenger evaluation.

---

## Próximos Passos Sugeridos

1. **Dividir `paper_execution.py`** — maior impacto em legibilidade
2. **Corrigir C-05 (variável redefinida)** — bug real detectado pelo mypy  
3. **Renomear exceções para sufixo Error** — conformidade PEP 8  
4. **Adicionar type params aos generics** — type safety completa
