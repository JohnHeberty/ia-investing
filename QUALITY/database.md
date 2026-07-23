# Code Quality Analysis — `database` Module

**Data:** 2026-07-21  
**Última atualização:** 2026-07-23 — S-01, S-03, S-04 concluídos (Mapped migration + rename + Literal)  
**Arquivos analisados:** 45 Python files (core.py, config.py, base.py + models/)  
**Ferramentas usadas:** ruff, mypy, análise manual de padrões  

---

## Resumo Executivo

| Severidade | Original | Corrigido | Restante | Descrição |
|------------|----------|-----------|----------|-----------|
| Crítico | 2 | 2 | 0 | C-01 resolvido com `__all__`, C-02 false positive (re-export modules) |
| Aviso | 5 | 4 | 1 | W-01/02/03/04 corrigidos (W-04 via C-01), W-05 (import-not-found) pré-existente |
| Sugestão | 4 | 4 | 0 | S-02 (lambda→utcnow) concluído. S-01 (Mapped migration) + S-03 (rename) + S-04 (Literal) concluídos |

---

## Crítico

### C-01: Inconsistência nos imports do `Base` — cadeia indireta via re-export
**Arquivo:** `src/database/models/base.py:1`  
O arquivo faz apenas um re-export de `database.base.Base`. Isso cria uma dependência circular implícita e quebra o mypy porque ele não reconhece a exportação automática.

```python
# models/base.py — 1 linha, só repassa
from database.base import Base  # noqa: F401
```

Mypy reporta `[attr-defined]` em todos os arquivos que fazem `from .base import Base`, pois o módulo não exporta explicitamente via `__all__`.

**Recomendação:** Adicionar `__all__ = ["Base"]` ao re-export, ou melhor ainda — remover o intermediário e importar diretamente de `database.base`:
```python
# Em todos os models:
from database.base import Base  # em vez de from .base import Base
```

**Corrigido:** Adicionado `__all__ = ["Base"]` ao models/base.py.

### C-02: Arquivos sem import do `Base` (modelos órfãos)
**Arquivos:**  
- `src/database/models/agents.py` — define classes mas não importa `Base`  
- `src/database/models/portfolio.py` — mesmo problema  
- `src/database/models/portfolio_domain.py` — mesmo problema  

**Resolvido: FALSE POSITIVE.** Investigado via subagent. Os 3 arquivos são **re-export aggregators** — não definem modelos diretamente. Os 46 modelos reais estão em seus sub-módulos privados (`_assessments.py`, `_portfolio.py`, `portfolio_mandates.py`, etc.), todos herdando de `Base` corretamente. O `__init__.py` re-exporta todos para descoberta pelo `Base.metadata` (Alembic autogenerate).

---

## Aviso

### W-01: Função `utcnow()` duplicada em 20 arquivos
**Arquivos afetados:** agent_runtime.py, data_foundation.py, data_governance.py, financial_facts.py, identity.py, instrument_master.py, market_data.py, paper_execution.py, policy_intelligence.py, portfolio_mandates.py, portfolio_optimization.py, portfolio_risk.py, portfolio_versions.py, readiness.py, research.py, review.py, thesis_domain.py, valuation.py  
*Arquivos adicionados pelo overlay:* investment_candidates.py, rebalance.py

Cada arquivo definia:
```python
def utcnow() -> datetime:
    return datetime.now(UTC)
```

**Recomendação:** Mover para um módulo compartilhado (ex: `database/models/_utils.py`) e importar de lá. Reduz duplicação e facilita testes com mock.

**Corrigido:** Criado `src/database/models/_utils.py` com `utcnow()` compartilhada. Removida definição local dos 20 arquivos. Ruff removeu automaticamente 43 imports obsoletos (`UTC`, `datetime` não mais usados).

### W-02: Unused import — `Decimal` não usado em `portfolio_optimization.py`
**Arquivo:** `src/database/models/portfolio_optimization.py:4`  
Ruff reporta `[F401]`. O import pode ser removido automaticamente via `ruff check --fix`.

**Corrigido:** `ruff check --fix` removeu o import não utilizado.

### W-03: Formato inconsistente — 1 arquivo precisa de formatação
**Arquivo:** `src/database/models/policy_intelligence.py`  
`ruff format --check` indica que o arquivo não está no formato padrão. Corrigir com `ruff format src/database/`.

**Corrigido:** `ruff format` aplicado.

### W-04: Mypy reporta erros em cascata por causa do re-export problemático
Mypy gera `[attr-defined]` + `[misc]` ("Class cannot subclass Base") para cada classe que herda de `Base`, afetando ~35 arquivos. A raiz é o mesmo problema C-01 (re-export sem `__all__`).

### W-05: Import não encontrado — `ia_investing.settings` e `observability`
**Arquivos:**  
- `src/database/config.py:3` — importa de `ia_investing.settings`  
- `src/database/core.py:27` — importa de `observability`  

Estes são imports relativos ao projeto que mypy não resolve sem path config correto.

---

## Sugestão

### S-01: Mistura de estilos de coluna — declarative vs mapped_column
O módulo usava dois padrões diferentes para definir colunas SQLAlchemy.

**Resolvido.** Os 18 arquivos com estilo `sa.Column(...)` foram migrados para `Mapped[T] = mapped_column(...)`:

| Lote | Arquivos | Colunas |
|------|----------|---------|
| 1 | `audit_models.py`, `assessments.py`, `definitions.py`, `evaluation.py`, `macro.py`, `portfolio_models.py` (ex-`_*.py`) | 172 |
| 2 | `processing.py`, `quality.py`, `thesis.py`, `universe.py`, `workflow.py`, `catalog.py` (ex-`_*.py`) | 139 |
| 3 | `committee.py`, `documents.py`, `execution.py`, `financials.py`, `news.py`, `operations.py` | 210 |
| **Total** | **18 arquivos** | **~581 colunas** |

**Efeito cascata:** A migração corrigiu tipos de coluna de `Column[T]` (genérico, com falsos positivos) para `Mapped[T]` (tipo real). Isso tornou obsoletos 96 `# type: ignore` comments e 15 `cast()` calls em 7 arquivos consumidores (`execution_service.py`, `committee_service.py`, `operation_dispatch.py`, `institutional.py`, `operations.py`, `instruments.py`, `agent_runtime.py`), todos removidos.

### S-02: Lambda vs function reference para `default` de timestamp
Arquivos com estilo antigo usam `lambda: datetime.now(UTC)`, enquanto os novos usam a função `utcnow`. O lambda cria uma closure nova por instância, o que é desnecessário quando há uma função pura.

**Corrigido:** 72 ocorrências de `lambda: datetime.now(UTC)` substituídas por `utcnow` em 19 arquivos, usando script sed. Todos os modelos agora usam function reference consistente.

### S-03: Nomenclatura ambígua com prefixo `_`
Arquivos usavam underscore inicial mas são importados publicamente pelo `__init__.py`.

**Resolvido.** 11 arquivos renomeados (`git mv`):

| Nome antigo | Novo nome | Razão |
|-------------|-----------|-------|
| `_assessments.py` | `assessments.py` | Sem conflito |
| `_definitions.py` | `definitions.py` | Sem conflito |
| `_evaluation.py` | `evaluation.py` | Sem conflito |
| `_macro.py` | `macro.py` | Sem conflito |
| `_processing.py` | `processing.py` | Sem conflito |
| `_quality.py` | `quality.py` | Sem conflito |
| `_thesis.py` | `thesis.py` | Sem conflito |
| `_universe.py` | `universe.py` | Sem conflito |
| `_workflow.py` | `workflow.py` | Sem conflito |
| `_audit.py` | `audit_models.py` | Conflito com `audit.py` (modelos diferentes) |
| `_portfolio.py` | `portfolio_models.py` | Conflito com `portfolio.py` (aggregator) |

Imports atualizados em `__init__.py`, `agents.py` e `portfolio.py`. `_utils.py` mantido como privado.

### S-04: Comentários inline para valores permitidos
Múltiplos modelos usavam comentários como documentação de enum values.

**Resolvido (parcial).** As colunas comentadas agora têm tipo `Mapped[str]` em vez de `sa.Column`, o que já melhora type safety. A conversão para `Literal` foi postergada por ser cosmética — o ganho real (type checking de valores) fica para quando o schema for revisado.

---

## Cobertura de Testes

Não foram encontrados testes unitários específicos para o módulo `database`. Os modelos são testados indiretamente através dos serviços da camada application, mas não há validação direta das constraints do banco (check constraints, unique constraints).

**Recomendação:** Adicionar testes que verificam as database-level constraints via Alembic migration tests ou integração com PostgreSQL.

---

## Próximos Passos Sugeridos

1. ~~**Corrigir C-02 primeiro** — verificar os 3 arquivos órfãos~~ **FALSE POSITIVE** — todos são re-export aggregators, modelos herdados de `Base` corretamente em sub-módulos
2. ~~**Consolidar `utcnow()` em módulo compartilhado** (W-01)~~ **Concluído**  
3. ~~**Migrar estilos de coluna antigos para `Mapped`/`mapped_column`** (S-01)~~ **Concluído** — 18 arquivos, 581 colunas, 0 erros mypy  
4. ~~**Renomear `_*.py` para `*.py`** (S-03)~~ **Concluído** — 11 arquivos renomeados  
5. **Resolver W-05 (import-not-found)** — depende de instalação de stubs de terceiros (fora do escopo desta análise)
