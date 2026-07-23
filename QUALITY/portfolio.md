# Code Quality Analysis — `portfolio` Module

**Data:** 2026-07-21  
**Última atualização:** 2026-07-22 — C-01, W-01 corrigidos  
**Arquivos analisados:** 4 Python files (__init__.py, _optimizer.py)  
**Ferramentas usadas:** ruff, mypy, análise manual de padrões  

---

## Resumo Executivo

| Severidade | Original | Corrigido | Restante | Descrição |
|------------|---------|----------|----------|-----------|
| Crítico | 1 | 1 | 0 | C-01 resolvido — `follow_imports = "skip"` para cvxpy no mypy config |
| Aviso | 3 | 1 | 2 | W-01 corrigido; W-02 (type:ignore) necessário pelo OptimizerConfig(**kwargs); S-02 sugestão |
| Sugestão | 2 | 0 | 2 | Construtor com dual API (`config` vs kwargs) é frágil; `_build_constraints` retorna tipo genérico `list` |

---

## Crítico

### C-01: Mypy `[attr-defined]` para atributos do CVXPY — possível import quebrado
**Arquivo:** `src/portfolio/_optimizer.py`  
Mypy reporta que o módulo não tem os atributos usados (`cp.sum`, `cp.norm`, `cp.quad_form`) — CVXPY não distribui type stubs.

**Corrigido:** Adicionado `[[tool.mypy.overrides]] module = "cvxpy.*" follow_imports = "skip"` no `pyproject.toml`. CVXPY tratado como `Any` pelo type checker. `mypy src/portfolio/` → 0 erros.

---

## Aviso

### W-01: Generics sem parâmetros — 8 ocorrências
**Arquivo:** `src/portfolio/_optimizer.py`  
Linhas 27 (`dict`), 58,97,98 (`ndarray`), 60,100,101,119 (`dict`) e 62-63 (`list`).

**Corrigido:** `constraints: dict` → `dict[str, Any]`, `transactions: list[dict]` → `list[dict[str, object]]`, `constraint_list: list` → `list[cp.Constraint]`.

### W-02: `type: ignore[arg-type]` no constructor
**Arquivo:** `src/portfolio/_optimizer.py:52`  
O constructor usa dual API com kwargs que pode ser frágil — a supressão de erro mascara um problema real de tipagem.

---

## Sugestão

### S-01: Construtor com dual API é frágil
**Arquivo:** `src/portfolio/_optimizer.py:48`  
O constructor aceita tanto `config: OptimizerConfig | None = None, **kwargs` como fallback — padrão que permite inconsistências. Se kwargs não correspondem aos campos de `OptimizerConfig`, o erro só aparece em runtime.

### S-02: `_build_constraints` retorna tipo genérico
**Arquivo:** `src/portfolio/_optimizer.py:63`  
A função retorna `list` sem type params — deveria retornar `list[cp.Constraint]`.

---

## Pontos Positivos

- **Dataclasses frozen com slots para performance e imutabilidade** (`OptimizationResult`, `OptimizerConfig`)
- **Boa separação entre configuração, constraints building, e otimização principal**  
- **Suporte a fallback solver** quando o primário falha

---

## Próximos Passos Sugeridos

1. ~~**Resolver imports do CVXPY para mypy (C-01)**~~ **Concluído** — `follow_imports = "skip"` no mypy config
2. ~~**Adicionar type params aos generics** (W-01)~~ **Concluído**  
3. **Simplificar constructor para aceitar apenas config object** (S-01)
