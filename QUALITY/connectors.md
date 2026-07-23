# Code Quality Analysis — `connectors` Module

**Data:** 2026-07-21  
**Última atualização:** 2026-07-22 — W-01/02/03 corrigidos  
**Arquivos analisados:** 23 Python files (base.py + b3/, cvm/, investor_relations/, macro/, news/, policy/)  
**Ferramentas usadas:** ruff, mypy, análise manual de padrões  

---

## Resumo Executivo

| Severidade | Original | Corrigido | Restante | Descrição |
|------------|----------|-----------|----------|-----------|
| Crítico | 0 | 0 | 0 | — |
| Aviso | 3 | 3 | 0 | W-01/02/03 corrigidos |
| Sugestão | 5 | 1 | 4 | S-04 (frozen=True) corrigido; S-01/02/03/05 pendentes |

---

## Aviso

### W-01: Formato inconsistente — `policy/_official.py`
**Arquivo:** `src/connectors/policy/_official.py`  
Ruff format reporta que o arquivo precisa ser reformulado. Corrigir com `ruff format src/connectors/`.

**Corrigido:** `ruff format` aplicado.

### W-02: Import não encontrado pelo mypy — `connectors.base`
**Arquivo:** `src/connectors/policy/_official.py:12`  
O módulo usa import absoluto (`from connectors.base import ...`) enquanto os demais usam relative imports (`from ..base import ...`). Mypy não resolve o caminho absoluto sem configuração de path.

**Corrigido:** Substituído por `from ..base import HttpClient, HttpClientProtocol`.

### W-03: `no-any-return` em `_next_link()`
**Arquivo:** `src/connectors/policy/_official.py:192`  
Mypy reporta que a função retorna `Any` quando deveria retornar `str | None`. Ocorre porque `item.get("href")` pode ser qualquer tipo.

**Corrigido:** Extraído `href` para variável local com `isinstance(href, str)` — mypy consegue estreitar o tipo corretamente.

---

## Sugestão

### S-01: Imports inconsistentes — relative vs absolute
O módulo mistura dois estilos de import para o mesmo alvo (`connectors.base`):

**Relative (padrão da maioria):**  
```python
from ..base import HttpClient  # _bcb.py, fca.py, _financials.py, etc.
```

**Absolute (apenas `_official.py`):**  
```python
from connectors.base import HttpClient, HttpClientProtocol  # policy/_official.py:12
```

**Recomendação:** Padronizar em relative imports (`..base`) para consistência com o resto do módulo e evitar problemas de resolução do mypy.

### S-02: Nomenclatura `_` prefixo ambígua
Arquivos como `_bcb.py`, `_financials.py`, `_cotahist.py`, etc. usam underscore inicial, indicando "privado/internal" em Python. Mas esses módulos são importados e usados externamente pelos services da camada application.

**Recomendação:** Remover o prefixo `_` dos arquivos que fazem parte da API pública do módulo (exportados via `__init__.py`). Manter apenas para funções/variáveis verdadeiramente internas.

### S-03: Sem testes unitários
Não foram encontrados testes específicos para o módulo `connectors`. Os conectores são componentes críticos de integração externa e merecem cobertura com mocks HTTP.

**Recomendação:** Adicionar testes que simulam respostas dos endpoints (B3, CVM, BCB, etc.) usando `httpx` mock ou `respx`, cobrindo sucesso, timeout, retry logic e parsing failures.

### S-04: Dataclass mutável para dados financeiros
**Arquivo:** `src/connectors/cvm/_financials.py:42`  
A classe `FinancialEntry` usa `@dataclass(slots=True)` (mutável) com campo `valor: float = 0.0`.

**Corrigido:** `frozen=True` adicionado — `@dataclass(frozen=True, slots=True)`.

### S-05: Parsing de preços como `float` em vez de `Decimal`
Múltiplos conectores usam `float` para valores monetários:
- `_financials.py`: `valor: float = 0.0`, `_parse_value()` retorna `float`  
- `_bcb.py`: `value: float` em `MacroObservation`

Para dados financeiros, especialmente de demonstrativos padronizados (DFP), o uso de `Decimal` é mais preciso e evita erros de arredondamento IEEE 754.

**Recomendação:** Substituir `float` por `Decimal` nos campos monetários dos dataclasses. O módulo `_bcb.py` já importa corretamente, mas usa `float`. Considere manter float apenas para indicadores macroeconômicos (onde precisão decimal não é crítica) e usar Decimal para dados financeiros corporativos.

---

## Pontos Positivos

- **Boa separação por provedor:** Cada subpasta (`b3/`, `cvm/`, etc.) encapsula a lógica do respectivo conector
- **Protocol pattern bem aplicado:** `HttpClientProtocol` permite injeção de dependência e mocking fácil nos testes
- **Retry com backoff exponencial** implementado corretamente em `base.py:79-101`  
- **Allowlist para egresso externo:** `_official.py:14-26` restringe conexões a hosts oficiais, boa prática de segurança
- **Dataclasses frozen + slots** usados consistentemente no módulo policy (boa performance e imutabilidade)

---

## Próximos Passos Sugeridos

1. **Corrigir import em `_official.py:12`** — mudar para relative import  
2. **Adicionar testes unitários com mocks HTTP** — prioridade alta dado o papel crítico dos conectores
3. **Padronizar nomenclatura sem prefixo `_`** nos arquivos públicos
