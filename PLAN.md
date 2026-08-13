# Plano: Reorganização dos Testes Unitários

**Data:** 2026-08-13
**Objetivo:** Transformar `tests/unit/` de pasta flat bagunçada para estrutura organizada por domínio

---

## Problema Atual

| Métrica | Valor |
|---------|-------|
| **Total de arquivos** | 178 test files |
| **Estrutura** | Flat (todos na mesma pasta) |
| **Naming** | `test_` prefix (redundante em pasta de teste) |
| **Fixtures** | Espalhadas, poucas compartilhadas |
| **Mocks** | Duplicados em 20+ arquivos |
| **Arquivos grandes** | 9 arquivos >20KB |

---

## Solução: 5 Fases

### Fase 1: Criar Estrutura de Diretórios

```
tests/unit/
├── candidate/          (13 arquivos)
├── workflow/           (11 arquivos)
├── portfolio/          (9 arquivos)
├── paper/              (6 arquivos)
├── connectors/         (12 arquivos)
│   ├── b3/
│   └── cvm/
├── services/           (15 arquivos)
├── api/                (8 arquivos)
├── domain/             (10 arquivos)
├── infrastructure/     (8 arquivos)
├── helpers/            (novo)
├── conftest.py
└── __init__.py
```

### Fase 2: Mover Arquivos + Remover Prefix `test_`

| Antes | Depois |
|-------|--------|
| `test_candidate_services.py` | `candidate/services.py` |
| `test_candidate_models.py` | `candidate/models.py` |
| `test_workflow_extract_news.py` | `workflow/extract_news.py` |
| `test_portfolio_optimizer.py` | `portfolio/optimizer.py` |
| `test_paper_execution.py` | `paper/execution.py` |
| `test_connector_rss.py` | `connectors/rss.py` |
| `test_auth_routes.py` | `api/auth_routes.py` |
| `test_valuation.py` | `domain/valuation.py` |
| `test_security.py` | `infrastructure/security.py` |

### Fase 3: Consolidação de Duplicados

| Grupo | Arquivos | Ação |
|-------|----------|------|
| Rebalance | `rebalance_service.py` + `rebalance_service_v2.py` | Consolidar em `services/rebalance.py` |
| Optimizer | `portfolio_optimizer.py` + `portfolio_optimizer_extended.py` | Consolidar em `portfolio/optimizer.py` |
| B3 Parser | `b3_parser.py` + `b3_parser_extended.py` | Consolidar em `connectors/b3/parser.py` |
| Valuation | `valuation.py` + `valuations.py` + `valuation_application.py` | Separar: `domain/valuation.py` + `services/valuations.py` |

### Fase 4: Extrair Fixtures Compartilhadas

Criar `tests/unit/helpers/`:
- `mock_session.py` — Factory para AsyncSession mock
- `mock_fixtures.py` — Fixtures compartilhadas
- `dummy_candidate_runtime.py` — Movido de `tests/unit/`

### Fase 5: Verificar

- Todos os testes passam
- Imports atualizados
- conftest.py atualizado

---

## Ordem de Execução

1. Criar diretórios (30min)
2. Mover arquivos com `git mv` (2h)
3. Atualizar imports (1h)
4. Consolidação (4h)
5. Extrair fixtures (2h)
6. Verificação (1h)

**Total: ~11h**
