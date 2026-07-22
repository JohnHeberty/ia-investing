# Code Quality Analysis — `data_quality` Module

**Data:** 2026-07-21  
**Arquivos analisados:** 8 Python files (__init__.py, _models.py, _accounting.py, _balance_sheet.py, _dre.py, _cash_flow.py, _temporal.py, _completeness.py)  
**Ferramentas usadas:** ruff, mypy, análise manual de padrões  

---

## Resumo Executivo

| Severidade | Quantidade | Descrição |
|------------|-----------|-----------|
| Crítico | 0 | Nenhum problema crítico identificado neste módulo |
| Aviso | 3 | Generics sem parâmetros (7 ocorrências), `__all__` ausente nos módulos, equity pode ser negativo em empresas reais |
| Sugestão | 4 | Duplicação de padrão `_make(...)` para validações non-negative, early return bloqueia checks subsequentes, tolerância fixa demais, nomenclatura ambígua com prefixo `_` |

---

## Aviso

### W-01: Generics sem parâmetros — 7 ocorrências
**Arquivos:**  
- `src/data_quality/_models.py:35` — `_get(line_items: dict)` → use `dict[str, object]`  
- `src/data_quality/_temporal.py:9` — `time_series: list[dict]` → use `list[dict[str, Any]]`  
- `src/data_quality/_dre.py:6`, `_cash_flow.py:6`, `_balance_sheet.py:6`, `_completeness.py:8`, `_accounting.py:33`

**Recomendação:** Adicionar type params para type safety completa. Criar TypedDict se a estrutura for conhecida.

### W-02: `__all__` ausente nos módulos
Os arquivos exportam símbolos mas não declaram `__all__`. Mypy reporta `[attr-defined]` ao tentar importar de `_accounting`, pois sem `__all__` ele não sabe o que é parte da API pública.

**Recomendação:** Adicionar `__all__ = ["ValidationResult", "validate_balance_sheet"]` nos módulos exportadores.

### W-03: Equity pode ser negativo em empresas reais
**Arquivo:** `src/data_quality/_balance_sheet.py:86-95`  
O check `"equity_non_negative"` reporta erro quando equity < 0, mas uma empresa com prejuízo acumulado tem equity negativo — isso é válido contabilmente.

```python
_make("equity_non_negative", equity >= 0, ..., severity="error" if equity < 0 else "info")
```

**Recomendação:** Mudar para `"warning"` em vez de `"error"`, ou remover esta validação pois equity negativo é situação contábil legítima.

---

## Sugestão

### S-01: Duplicação de padrão `_make(...)` para validações non-negative
**Arquivo:** `src/data_quality/_balance_sheet.py`  
O mesmo bloco se repete 7 vezes (current_assets, non_current_assets, total_liabilities, equity, cash, accounts_receivable, inventory):

```python
results.append(
    _make("X_non_negative", X >= 0, entity_type, entity_id, severity="error" if X < 0 else "info")
)
```

**Recomendação:** Extrair para função helper:
```python
def _check_non_negative(value, name):
    return _make(f"{name}_non_negative", value >= 0, ...)

for field in ["current_assets", "cash", ...]:
    results.append(_check_non_negative(_get(line_items, field), field))
```

### S-02: Early return bloqueia checks subsequentes
**Arquivo:** `src/data_quality/_accounting.py:56`  
Se o completeness check falhar, as validações contábeis nunca rodam — perde-se informações úteis sobre outros problemas nos dados.

```python
if not completeness[0].passed:
    return completeness  # ← retorna sem rodar handler(line_items)
```

**Recomendação:** Rodar todos os checks e retornar a lista completa, não apenas o primeiro que falha.

### S-03: Tolerância fixa em `_close()` pode ser inadequada
**Arquivo:** `src/data_quality/_models.py:42`  
A tolerância de 0.1% (`tolerance_pct=0.001`) é hardcoded e usada para verificar se balanço fecha. Para empresas com valores muito grandes, essa margem pode ser insuficiente devido a arredondamentos em escala (milhões/bilhões).

**Recomendação:** Tornar a tolerância configurável por caller ou usar tolerance absoluta baseada na magnitude dos valores.

### S-04: Nomenclatura `_` prefixo ambígua
Arquivos como `_models.py`, `_accounting.py`, etc. usam underscore inicial mas são importados publicamente via `__init__.py`. A nomenclatura é enganosa.

---

## Pontos Positivos

- **Boa estrutura de validação:** separação clara entre models, checks específicos por statement type, e dispatcher central
- **Temporal consistency check bem implementado** (`_temporal.py`): verifica ordenação, duplicatas, e gaps com lógica robusta  
- **Helper `_make()` simplifica criação de ValidationResult**, reduzindo boilerplate

---

## Próximos Passos Sugeridos

1. **Corrigir equity validation (W-03)** — mudar severity para warning
2. **Adicionar type params aos generics** (W-01)  
3. **Refatorar duplicação de validações non-negative** com loop + helper (S-01)
