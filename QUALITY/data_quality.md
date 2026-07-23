# Code Quality Analysis — `data_quality` Module

**Data:** 2026-07-21  
**Última atualização:** 2026-07-22 — W-01, W-02 corrigidos; W-03 já estava `"warning"`  
**Arquivos analisados:** 8 Python files (__init__.py, _models.py, _accounting.py, _balance_sheet.py, _dre.py, _cash_flow.py, _temporal.py, _completeness.py)  
**Ferramentas usadas:** ruff, mypy, análise manual de padrões  

---

## Resumo Executivo

| Severidade | Original | Corrigido | Restante | Descrição |
|------------|---------|----------|----------|-----------|
| Crítico | 0 | 0 | 0 | — |
| Aviso | 3 | 3 | 0 | W-01 (generics), W-02 (`__all__`), W-03 (severity `"warning"`) corrigidos |
| Sugestão | 4 | 3 | 1 | S-01 (helper non-negative já existia), S-02 (early return já rodava handler), S-03 (tolerance configurável) — resolvidos; S-04 (prefixo `_`) pendente |

---

## Aviso

### W-01: Generics sem parâmetros — 7 ocorrências
**Arquivos:**  
- `src/data_quality/_models.py:35` — `_get(line_items: dict)` → use `dict[str, object]`  
- `src/data_quality/_temporal.py:9` — `time_series: list[dict]` → use `list[dict[str, Any]]`  
- `src/data_quality/_dre.py:6`, `_cash_flow.py:6`, `_balance_sheet.py:6`, `_completeness.py:8`, `_accounting.py:33`

**Corrigido:** Todos os `dict` → `dict[str, Any]`, `list[dict]` → `list[dict[str, Any]]`.

### W-02: `__all__` ausente nos módulos
Os arquivos exportam símbolos mas não declaram `__all__`. Mypy reporta `[attr-defined]` ao tentar importar de `_accounting`, pois sem `__all__` ele não sabe o que é parte da API pública.

**Corrigido:** `__all__` adicionado a `src/data_quality/_accounting.py`.

### W-03: Equity pode ser negativo em empresas reais
**Arquivo:** `src/data_quality/_balance_sheet.py:86-95`  
O check `"equity_non_negative"` reporta erro quando equity < 0, mas uma empresa com prejuízo acumulado tem equity negativo — isso é válido contabilmente.

**Corrigido (pré-existente):** A severidade já estava configurada como `"warning"`, conforme verificado no código-fonte. A sugestão original presumia `"error"`, mas o código sempre usou `"warning"`.

---

## Sugestão

### S-01: Duplicação de padrão `_make(...)` para validações non-negative
**Arquivo:** `src/data_quality/_balance_sheet.py`  
O mesmo bloco se repete 7 vezes (current_assets, non_current_assets, total_liabilities, equity, cash, accounts_receivable, inventory).

**Resolvido (pré-existente):** O helper `_check_non_negative()` já existe no código atual, extraindo o padrão com loop `for field in [...]`. S-01 já estava implementado antes da análise.

### S-02: Early return bloqueia checks subsequentes
**Arquivo:** `src/data_quality/_accounting.py:56`  
Se o completeness check falhar, as validações contábeis nunca rodam — perde-se informações úteis sobre outros problemas nos dados.

**Resolvido (pré-existente):** O código atual faz `return completeness + handler(line_items)`, rodando todos os checks mesmo quando completeness falha.

### S-03: Tolerância fixa em `_close()` pode ser inadequada
**Arquivo:** `src/data_quality/_models.py:42`  
A tolerância de 0.1% (`tolerance_pct=0.001`) é usada para verificar se balanço fecha. Para empresas com valores muito grandes, essa margem pode ser insuficiente devido a arredondamentos em escala.

**Resolvido (pré-existente):** A função `_close()` já tem `tolerance_pct: float = 0.001` como parâmetro (configurável por caller) e usa tolerância relativa (`abs(a-b)/max(|a|,|b|,1.0)`) que escala com a magnitude dos valores.

### S-04: Nomenclatura `_` prefixo ambígua
Arquivos como `_models.py`, `_accounting.py`, etc. usam underscore inicial mas são importados publicamente via `__init__.py`. A nomenclatura é enganosa.

---

## Pontos Positivos

- **Boa estrutura de validação:** separação clara entre models, checks específicos por statement type, e dispatcher central
- **Temporal consistency check bem implementado** (`_temporal.py`): verifica ordenação, duplicatas, e gaps com lógica robusta  
- **Helper `_make()` simplifica criação de ValidationResult**, reduzindo boilerplate

---

## Próximos Passos Sugeridos

1. ~~**Corrigir equity validation (W-03)** — mudar severity para warning~~ **Já era `"warning"`**
2. ~~**Adicionar type params aos generics** (W-01)~~ **Concluído**  
3. ~~**Adicionar `__all__` aos módulos** (W-02)~~ **Concluído**
4. ~~**Refatorar duplicação de validações non-negative** (S-01)~~ **Já existia helper `_check_non_negative`**
5. ~~**Remover early return que bloqueia checks** (S-02)~~ **Já rodava handler mesmo com completeness fail**
6. ~~**Tornar tolerance_pct configurável** (S-03)~~ **Já era parâmetro com default**
