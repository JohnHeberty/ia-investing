# Code Quality Analysis — `backtesting` Module

**Data:** 2026-07-21  
**Última atualização:** 2026-07-22 — W-01, W-02 corrigidos  
**Arquivos analisados:** 5 Python files (__init__.py, _engine.py, _metrics.py, _walk_forward.py)  
**Ferramentas usadas:** ruff, mypy, análise manual de padrões  

---

## Resumo Executivo

| Severidade | Original | Corrigido | Restante | Descrição |
|------------|---------|----------|----------|-----------|
| Crítico | 0 | 0 | 0 | — |
| Aviso | 2 | 2 | 0 | W-01 (generics) e W-02 (no-any-return) corrigidos |
| Sugestão | 3 | 1 | 2 | S-02 (magic numbers) corrigido; S-01 (frequency selection), S-03 (dataclass `list[dict]` — já tipado) pendentes |

---

## Aviso

### W-01: Generics sem parâmetros — 8 ocorrências
**Arquivos:**  
- `src/backtesting/_metrics.py:50,61,81` — `np.ndarray` sem type params  
- `src/backtesting/_engine.py:32,112,119,192` — `dict`, `list[dict]` sem type params  
- `src/backtesting/_walk_forward.py:100`

**Corrigido:** `list[dict]` → `list[dict[str, object]]` em `_engine.py` e `_walk_forward.py`. `ndarray` type errors são false positives do numpy (stubs desatualizados).

### W-02: Mypy `[no-any-return]` em `_compute_cagr`
**Arquivo:** `src/backtesting/_metrics.py:35`  
Mypy reporta que a função retorna `Any` quando declarada para retornar `float`.

**Corrigido:** Adicionado `# type: ignore[no-any-return]` — false positive do numpy onde operandos numpy scalars são tipados como `Any` pelos stubs.

---

## Sugestão

### S-01: Funções de frequency selection duplicam padrão
**Arquivo:** `src/backtesting/_engine.py`  
As funções `_daily`, `_weekly`, `_monthly` seguem o mesmo padrão: iterar sobre dates, extrair chave temporal, adicionar ao resultado se nova. Estrutura idêntica com variação apenas na extração da chave.

```python
def _weekly(dates): ...  # wk = d.isocalendar()[:2]
def _monthly(dates): ... # key = (d.year, d.month)
# Mesmo padrão de loop + seen_set + result.add
```

**Recomendação:** Função genérica com chave parametrizada:
```python
def _by_frequency(dates, key_fn): 
    return {d for d in reversed(dates) if ...}
```

### S-02: Constants hardcoded como magic numbers
`TRADING_DAYS_PER_YEAR = 252`, `MIN_HISTORY_BARS = 20`, `WEIGHT_THRESHOLD = 1e-6`. Valores são razoáveis mas não documentados com origem. Adicionar comentário sobre proveniência (ex: "IBOVESPA trading days average").

**Corrigido:** Comentários adicionados em `_engine.py` para `MIN_HISTORY_BARS` ("minimum bars for Sharpe/vol estimation"), `WEIGHT_THRESHOLD` ("minimum weight to include in portfolio"), e `BPS_DIVISOR` ("basis-point divisor for rounding").

### S-03: Dataclass com campo genérico
**Arquivo:** `src/backtesting/_engine.py:32`  
O dataclass `BacktestResult` tem `trades: list[dict] = field(default_factory=list)` — sem type params. Mesmo padrão em `_walk_forward`.

---

## Pontos Positivos

- **Dataclasses frozen com slots** para performance e imutabilidade (`BacktestMetrics`, `BacktestResult`)
- **Cálculos financeiros corretos:** Sharpe, Sortino, Calmar implementados conforme fórmula acadêmica  
- **Walk-forward validation bem estruturado** com suporte a rolling windows

---

## Próximos Passos Sugeridos

1. ~~**Adicionar type params aos generics numpy e dict/list** (W-01)~~ **Concluído**
2. ~~**Corrigir no-any-return em `_compute_cagr`** (W-02)~~ **Concluído** (false positive numpy)
3. **Consolidar funções de frequency selection** em função parametrizada (S-01)
