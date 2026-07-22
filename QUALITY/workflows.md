# Code Quality Analysis — `workflows` Module

**Data:** 2026-07-21  
**Última atualização:** 2026-07-22 — W-01 corrigido, imports candidates com noqa E402  
**Arquivos analisados:** 17 Python files (__init__.py + 16 workflows)  
**Ferramentas usadas:** ruff, mypy, análise manual de padrões  

---

## Resumo Executivo

| Severidade | Original | Corrigido | Restante | Descrição |
|------------|----------|-----------|----------|-----------|
| Crítico | 2 | 0 | 2 | C-01/02 — dependentes de mypy config |
| Aviso | 3 | 1 | 2 | W-01 corrigido (`call-overload`), W-02/03 pendentes (precisa verificar se overlay removeu) |
| Sugestão | 2 | 0 | 2 | S-01/02 — refatorações maiores pendentes |

---

## Crítico

### C-01: Imports absolutos não resolvidos pelo mypy no `__init__.py`
**Arquivo:** `src/workflows/__init__.py`  
Mypy reporta 14+ erros `[import-not-found]`. Os imports usam caminho absoluto (`workflows._analyze_filing`) mas mypy não resolve sem configuração de path correta. Não é um problema de imports relativos — todos os módulos usam `from workflows._x import ...` (absoluto), não `from ._x import ...` (relativo).

**Recomendação:** Adicionar `python_path = src` ao `mypy.ini` ou usar imports relativos (`from ._analyze_filing import ...`).

### C-02: Imports absolutos quebrados em múltiplos arquivos  
Múltiplos workflows usam caminhos como `ia_investing.orchestration.policies`, `data_quality._accounting`, etc — mypy não resolve esses módulos porque o path de importação está inconsistente entre runtime e type-checker.  
*Nota: O overlay Candidate Intelligence adicionou 2 novos workflows (`candidate_dispatch.py`, `candidate_intelligence.py`) que seguem o mesmo padrão de import e podem estar sujeitos ao mesmo problema.*

---

## Aviso

### W-01: Mypy errors em `_portfolio_construction.py`
**Arquivo:** `src/workflows/_portfolio_construction.py:165`  
Dois erros: `[unused-ignore]` — o `type: ignore[arg-type]` não cobre o erro real que é `[call-overload]`. A linha tenta converter um objeto genérico para dict com `dict(opt_result.get("weights", {}))`, mas mypy detecta incompatibilidade de overload.

**Corrigido:** `type: ignore[arg-type]` → `type: ignore[call-overload]`.

### W-02: Mypy `[no-any-return]` em `_run_agent.py`
**Arquivo:** `src/workflows/_run_agent.py:51`  
Função retorna `Any` quando deveria retornar `dict[str, Any]`. Provavelmente devido a uma conversão implícita.

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

1. **Corrigir imports quebrados no `__init__.py` (C-01)** — usar relativos ou corrigir mypy config
2. **Resolver import paths absolutos em workflows** que não são resolvidos pelo type checker  
3. **Fixar o `type: ignore[arg-type]` incorreto** em `_portfolio_construction.py:165` para `[call-overload]`
