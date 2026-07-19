# Convenções de Domínio

**Status:** Aceito
**Data:** 2026-07-18

---

## 1. IDs

- **Tipo:** `UUID v4` (gerado via `gen_random_uuid()`)
- **Coluna:** Sempre `id = sa.Column(UUID(as_uuid=True), primary_key=True)`
- **FKs:** `sa.Column(UUID(as_uuid=True), sa.ForeignKey("tabela.id", ondelete="CASCADE"))`
- **Naming:** `id`, `{entidade}_id` para FKs

## 2. Nomes

- **Classes ORM:** `PascalCase` (ex: `FinancialStatement`, `AgentRun`)
- **Tabelas:** `snake_case` plural (ex: `financial_statements`, `agent_runs`)
- **Colunas:** `snake_case` (ex: `reporting_period_end`, `is_active`)
- **Módulos:** `snake_case` com prefixo `_` para privados (ex: `_cotahist.py`, `_parser.py`)
- **Constantes:** `UPPER_SNAKE_CASE` (ex: `DEFAULT_TIMEOUT`, `BPS_DIVISOR`)
- **Enums de BD:** `VARCHAR` com valores em `UPPER_SNAKE_CASE` (ex: `"BALANCE_SHEET"`, `"APPROVED"`)

## 3. Datas e Horários

- **Date:** `sa.Date` para períodos (ex: `reporting_period_end`)
- **DateTime com timezone:** `sa.DateTime(timezone=True)` para timestamps (ex: `created_at`, `published_at`)
- **Default:** `lambda: datetime.now(UTC)` para `created_at`
- **Formato ISO:** `2026-07-18` para datas, `2026-07-18T21:18:20-03:00` para datetime
- **Point-in-time:** `published_at` = quando o dado ficou disponível publicamente
- **Period:** `reporting_period_start` / `reporting_period_end` = período contábil

## 4. Dinheiro e Valores Financeiros

- **Moeda:** `currency_code = sa.Column(sa.String(3))` (ISO 4217: "BRL", "USD")
- **Valores:** `sa.Column(sa.Numeric(20, 10))` para métricas, `sa.Column(sa.Numeric(14, 6))` para preços
- **Escalas:** `scale_factor` (1 = unidades, 1000 = milhares, 1_000_000 = milhões)
- **BPS:** Divisor `10_000.0` para basis points
- **Percentuais:** Decimais (0.1 = 10%), não inteiros

## 5. Enums

- **BD:** `VARCHAR` com validação na aplicação, não `sa.Enum`
- **Python:** `StrEnum` ou `Literal` para Pydantic schemas
- **Valores:** `UPPER_SNAKE_CASE` para BD, `lowercase` para Python (decidido: manter consistência com BD)
- **Exemplos:**
  - `statement_type`: "BALANCE_SHEET", "INCOME_STATEMENT", "CASH_FLOW"
  - `status`: "PENDING", "COMPLETED", "FAILED"
  - `verdict`: "POSITIVE", "NEGATIVE", "NEUTRAL"

## 6. Erros

- **Connector errors:** `warn + return empty list` (padrão atual)
- **Validation errors:** `ValidationResult` com `passed: bool`, `check_name: str`, `details: dict`
- **Agent errors:** `AgentRun.status = "failed"` com `error_message`
- **Workflow errors:** Temporal retry policy com exponential backoff
- **Exceptions:** Usar exception hierarchy própria se necessário (Fase 1)

## 7. Eventos de Domínio

- **Formato:** `{entidade}.{acao}` (ex: `cvm.ingested`, `filing.analyzed`, `news.analyzed`)
- **Publicação:** Via `publish_event` activity nos workflows
- **Armazenamento:** `DetectedEvent` + `EventImpact` para rastreamento
- **Deduplicação:** `EventDuplicate` com similarity score

## 8. Temporalidade

- **Point-in-time:** Dados vinculados a `published_at` para queries históricas
- **Snapshot:** `as_of_date` para estado em um ponto no tempo
- **Versionamento:** `version_number` para prompts, teses, schemas
- **Review deadline:** `review_deadline` para teses e recomendações

## 9. Contratos de API

- **Formato:** JSON com Pydantic models
- **Nomenclatura:** `snake_case` para campos
- **Datas:** ISO 8601 strings
- **IDs:** UUID strings
- **Paginação:** Offset/limit para listas (a ser implementado)
- **Erros:** HTTP status codes + body com detalhes
