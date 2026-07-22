# Code Quality Analysis — `backtesting` Module

**Data:** 2026-07-21  
**Arquivos analisados:** 5 Python files (__init__.py, _engine.py, _metrics.py, _walk_forward.py)  
**Ferramentas usadas:** ruff, mypy, análise manual de padrões  

---

## Resumo Executivo

| Severidade | Quantidade | Descrição |
|------------|-----------|-----------|
| Crítico | 0 | Nenhum problema crítico identificado neste módulo |
| Aviso | 2 | Generics sem parâmetros (8 ocorrências), `ndarray` sem type params, `Any` return em `_compute_cagr` |
| Sugestão | 3 | Funções de frequency selection duplicam padrão (`_daily`, `_weekly`, `_monthly`), constants hardcoded como magic numbers, dataclass com campo genérico `list[dict]` |

---

## Aviso

### W-01: Generics sem parâmetros — 8 ocorrências
**Arquivos:**  
- `src/backtesting/_metrics.py:50,61,81` — `np.ndarray` sem type params → use `ndarray[np.float64]` ou similar  
- `src/backtesting/_engine.py:32,112,119,192` — `dict`, `list[dict]` sem type params no dataclass e funções  
- `src/backtesting/_walk_forward.py:100`

**Recomendação:** Adicionar type params explícitos. Para numpy arrays usar `np.ndarray[np.float64_]`.

### W-02: Mypy `[no-any-return]` em `_compute_cagr`
**Arquivo:** `src/backtesting/_metrics.py:35`  
Mypy reporta que a função retorna `Any` quando declarada para retornar `float`. Provavelmente devido à expressão `(final / initial) ** (periods_per_year / n_periods)` onde os operandos são tipados como `object`.

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

1. **Adicionar type params aos generics numpy e dict/list** (W-01)
2. **Consolidar funções de frequency selection** em função parametrizada (S-01)
