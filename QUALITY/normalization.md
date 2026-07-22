# Code Quality Analysis — `normalization` Module

**Data:** 2026-07-21  
**Arquivos analisados:** 5 Python files (__init__.py, _mappings.py, _derived.py, _financials.py, _normalizers.py)  
**Ferramentas usadas:** ruff, mypy, análise manual de padrões  

---

## Resumo Executivo

| Severidade | Quantidade | Descrição |
|------------|-----------|-----------|
| Crítico | 0 | Nenhum problema crítico identificado neste módulo |
| Aviso | 2 | Generics sem parâmetros (7 ocorrências), import não encontrado pelo mypy |
| Sugestão | 3 | Uso de `float` para valores financeiros, lógica duplicada em funções normalize_*, nomenclatura `_` prefixo ambígua |

---

## Aviso

### W-01: Generics sem parâmetros — 7 ocorrências
**Arquivo:** `src/normalization/_normalizers.py`  
Mypy reporta `[type-arg]` nas linhas 24, 59, 117, 130, 143, 147 e 151. As funções usam `dict` sem type params:

```python
def normalize_bpa(rows: list[dict]) -> dict[str, float]:  # ← retorno OK mas parâmetro genérico
    ...
```

**Recomendação:** Usar `list[dict[str, object]]` ou criar um TypedDict para o formato esperado de entrada.

### W-02: Import não encontrado pelo mypy — `connectors.cvm._financials`
**Arquivo:** `src/normalization/_normalizers.py:5`  
Mypy reporta `[import-not-found]`. O import funciona em runtime mas mypy não resolve o caminho sem configuração de path.

---

## Sugestão

### S-01: Uso de `float` para valores financeiros
**Arquivo:** `src/normalization/_normalizers.py`  
As funções retornam `dict[str, float]` e usam variáveis como `current_assets = 0.0`. Valores monetários deveriam usar `Decimal` para precisão exata.

### S-02: Lógica duplicada em funções normalize_*
Os padrões de validação e agregação se repetem entre `normalize_bpa()`, `normalize_bpp()` e outras funções similares no mesmo arquivo. Cada uma define seus próprios sets de chaves, itera sobre entries, acumula valores — estrutura idêntica.

**Recomendação:** Extrair para função genérica:
```python
def _aggregate(entries, group_map) -> dict[str, float]: ...
```

### S-03: Nomenclatura `_` prefixo ambígua
Arquivos como `_normalizers.py`, `_mappings.py`, etc. usam underscore inicial indicando "privado", mas são importados publicamente pelo `__init__.py`.

---

## Pontos Positivos

- **Boa separação entre mapeamento e normalização:** `_mappings.py` contém apenas dados estáticos (CVM_ACCOUNT_MAP), enquanto `_normalizers.py` implementa a lógica
- **Fallback para matching por descrição** quando o código CVM não é encontrado (`_resolve_canonical`)

---

## Próximos Passos Sugeridos

1. **Adicionar type params aos generics** — `dict[str, object]` ou TypedDict  
2. **Considerar usar Decimal em vez de float** para valores financeiros (S-01)
3. **Consolidar lógica duplicada entre funções normalize_*** (S-02)
