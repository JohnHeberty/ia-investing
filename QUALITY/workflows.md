# Code Quality Analysis — `workflows` Module

**Data:** 2026-07-21  
**Última atualização:** 2026-07-22 — W-01, W-02, C-01, C-02 corrigidos; imports candidates com noqa E402  
**Arquivos analisados:** 17 Python files (__init__.py + 16 workflows)  
**Ferramentas usadas:** ruff, mypy, análise manual de padrões  

---

## Resumo Executivo

| Severidade | Original | Corrigido | Restante | Descrição |
|------------|----------|-----------|----------|-----------|
| Crítico | 2 | 2 | 0 | C-01/02 resolvidos — `mypy_path = \"src\"` adicionado ao pyproject.toml |
| Aviso | 3 | 2 | 1 | W-01 (`call-overload`), W-02 (`no-any-return`) corrigidos; W-03 (import style) pendente |
| Sugestão | 2 | 0 | 2 | S-01/02 — refatorações maiores pendentes |

---

## Crítico

### C-01: Imports absolutos não resolvidos pelo mypy no `__init__.py`
**Arquivo:** `src/workflows/__init__.py`  
Mypy reporta 14+ erros `[import-not-found]`. Os imports usam caminho absoluto (`workflows._analyze_filing`) mas mypy não resolve sem configuração de path correta. Não é um problema de imports relativos — todos os módulos usam `from workflows._x import ...` (absoluto), não `from ._x import ...` (relativo).

**Corrigido:** `mypy_path = "src"` adicionado ao `[tool.mypy]` em pyproject.toml. Todos os imports absolutos (`workflows._x`, `ia_investing.*`, etc.) agora resolvidos.

### C-02: Imports absolutos quebrados em múltiplos arquivos  
Múltiplos workflows usam caminhos como `ia_investing.orchestration.policies`, `data_quality._accounting`, etc — mypy não resolve esses módulos porque o path de importação está inconsistente entre runtime e type-checker.

**Corrigido:** Mesmo fix do C-01 — `mypy_path = "src"` resolve todos os imports internos em todos os 17 workflows, incluindo os 2 do overlay Candidate Intelligence.

---

## Aviso

### W-01: Mypy errors em `_portfolio_construction.py`
**Arquivo:** `src/workflows/_portfolio_construction.py:165`  
Dois erros: `[unused-ignore]` — o `type: ignore[arg-type]` não cobre o erro real que é `[call-overload]`. A linha tenta converter um objeto genérico para dict com `dict(opt_result.get("weights", {}))`, mas mypy detecta incompatibilidade de overload.

**Corrigido:** `type: ignore[arg-type]` → `type: ignore[call-overload]`.

### W-02: Mypy `[no-any-return]` em `_run_agent.py`
**Arquivo:** `src/workflows/_run_agent.py:34`  
Função retorna `Any` quando deveria retornar `dict[str, Any]` — `workflow.execute_activity()` retorna `Any` pelos stubs do Temporal.

**Corrigido:** Extraído para variável tipada `result: dict[str, Any]` antes do return, eliminando o false positive do mypy.

### W-03: Padrão de import inconsistente entre arquivos do mesmo módulo  
Alguns usam imports relativos (`from ._models import ...`) e outros absolutos (`import workflows._x`). Inconsistência dentro do mesmo pacote.

---

## Sugestão

### S-01: Arquivos com lógica similar poderiam compartilhar base comum
`_analyze_filing.py`, `_analyze_news.py`, `_discover.py` seguem padrão idêntico de workflow Temporal — mesma estrutura de activity execution, error handling, e policy enforcement. Extrair para classe base `BaseWorkflow`.

### S-02: `__init__.py` muito grande (90 linhas, 37 símbolos)
O arquivo re-exporta muitos símbolos (17 módulos, 37 exports). O overlay Candidate Intelligence adicionou 5 novos imports e 5 exports. Considerar usar lazy import ou documentar a API pública explicitamente com `__all__` (já existe, mas é grande).

---

## Pontos Positivos

- **Boa separação entre workflows** — cada workflow é um módulo independente  
- **Uso correto do Temporal SDK** com activity execution e timeout configuration
- **Hash verification para proposals** (`_portfolio_construction.py`) garante integridade dos dados de otimização

---

## Próximos Passos Sugeridos

1. ~~**Corrigir imports quebrados no `__init__.py` (C-01)**~~ **Concluído** — `mypy_path = "src"`
2. ~~**Resolver import paths absolutos em workflows** (C-02)~~ **Concluído** — mesmo fix
3. ~~**Fixar o `type: ignore[arg-type]` incorreto** em `_portfolio_construction.py:165`~~ **Concluído**
4. ~~**Corrigir `[no-any-return]` em `_run_agent.py`** (W-02)~~ **Concluído**
