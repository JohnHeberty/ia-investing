# Plano de Análise Code Quality

## Módulos a Analisar (13)

| # | Módulo | Arquivos .py | Prioridade | Status |
|---|--------|-------------|------------|--------|
| 1 | `ia_investing` | 98 | Alta — núcleo do domínio, AI, app layer | Concluído |
| 2 | `database` | 45 | Alta — ORM models, migrations, access layer | Concluído |
| 3 | `apps` (api/scheduler/worker) | 44 | Alta — entry points, rotas, segurança | Concluído |
| 4 | `connectors` (b3/cvm/news/macro/policy/investor_relations) | 22 | Média — fetchers de dados externos | Concluído |
| 5 | `workflows` | 17 | Média — Temporal workflows | Concluído |
| 6 | `metrics` | 9 | Baixa — indicadores, cálculos financeiros | Concluído |
| 7 | `data_quality` | 8 | Baixa — validação de dados | Concluído |
| 8 | `schemas` | 7 | Baixa — Pydantic schemas | Concluído |
| 9 | `backtesting` | 5 | Baixa — walk-forward, simulação | Concluído |
| 10 | `normalization` | 5 | Baixa — normalização de dados | Concluído |
| 11 | `portfolio` | 4 | Baixa — gestão de portfólio | Concluído |
| 12 | `parsers` | 3 | Baixa — parsing de documentos | Concluído |
| 13 | `evaluation` + `observability` | 7 | Baixa — eval pipeline, tracing | Concluído |

## Critérios por Módulo

Cada análise verificará:
- **SOLID**: SRP, OCP, LSP, ISP, DIP
- **Clean Code**: nomes significativos, funções pequenas, sem duplicação
- **Error Handling**: exceptions customizadas vs genéricas, tratamento adequado
- **Type Safety**: annotations completos, uso de `typing` correto
- **Testing Coverage**: testes existentes para o módulo
- **Imports**: circular dependencies, imports desnecessários

## Saída

Relatórios em `QUALITY/<modulo>.md`, um por módulo.
