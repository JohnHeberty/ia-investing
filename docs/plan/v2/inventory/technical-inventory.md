# Inventário Técnico — F0-PR02

**Baseline tag:** `baseline/f19bbc8`
**Data:** 2026-07-18

---

## 1. Schemas Pydantic (8 modelos)

Todos em `src/schemas/`. Nenhum é importado externamente — consumidos via `importlib` pelo `AgentRunner`.

| Modelo | Arquivo | Campos-chave | Consumidor |
|--------|---------|--------------|------------|
| `Claim` | `_filing.py` | text, status, source_location, evidence_strength | Sub-modelo de `FilingReviewVerdict` |
| `Risk` | `_filing.py` | description, severity, probability, mitigation | Sub-modelo de `FilingReviewVerdict` e `RiskAssessment` |
| `FilingReviewVerdict` | `_filing.py` | verdict, confidence, summary_pt, materiality_score, claims, risks, data_gaps | `filing_analyst` agent |
| `NewsAnalysis` | `_news.py` | verdict, confidence, summary_pt, event_type, affected_metrics | `news_analyst` agent |
| `RiskAssessment` | `_risk.py` | overall_risk, risk_score, top_risks, stress_test_results | `risk_director` agent |
| `ThesisVerdict` | `_thesis.py` | action, confidence, target_price, reasoning_pt | `fundamentalist_analyst` agent |
| `DiscoveryBrief` | `_discovery.py` | ticker, issuer_name, sector, market_cap, anomaly_type | `research_coordinator` agent |
| `CommitteeDecision` | `_committee.py` | decision, confidence, reasoning_pt, conditions | `investment_committee` agent |

**Observação:** Todos herdam de `pydantic.BaseModel`. Sem versão explícita. Usam `Field()` com `ge`/`le`.

---

## 2. Modelos/Tabelas SQLAlchemy (51 tabelas)

### 2.1 Catálogo (6 tabelas)

| Classe | Tabela | JSONB | Indexes |
|--------|--------|-------|---------|
| `Sector` | `sectors` | — | — |
| `Industry` | `industries` | — | FK → sectors |
| `Issuer` | `issuers` | — | ix_cnpj, ix_cvm_code |
| `Ticker` | `tickers` | — | ix_delisting_date, UNIQUE(symbol, issuer_id) |
| `MarketPrice` | `market_prices` | — | ix_ticker_id, ix_close_price, UNIQUE(ticker_id, trade_date) |
| `Embedding` | `embeddings` | — | ix_entity_id |

### 2.2 Documentos (6 tabelas)

| Classe | Tabela | JSONB | FKs |
|--------|--------|-------|-----|
| `RawDocument` | `raw_documents` | — | → issuers |
| `DocumentMetadata` | `document_metadata` | parsed_data, extraction_errors | → raw_documents, issuers |
| `Document` | `documents` | canonical_data | → raw_documents, issuers |
| `DocumentProcessingLog` | `document_processing_log` | — | → raw_documents |
| `DocumentDuplicate` | `document_duplicates` | — | → raw_documents ×2 |
| `DocumentEvent` | `document_events` | payload | → raw_documents |

### 2.3 Financeiros (4 tabelas)

| Classe | Tabela | JSONB |
|--------|--------|-------|
| `FinancialStatement` | `financial_statements` | line_items, raw_data |
| `FinancialMetric` | `financial_metrics` | calculation_method |
| `Dividend` | `dividends` | — |
| `ShareStatistics` | `share_statistics` | — |

### 2.4 Notícias (5 tabelas)

| Classe | Tabela | JSONB |
|--------|--------|-------|
| `NewsSource` | `news_sources` | — |
| `NewsItem` | `news_items` | raw_data |
| `NewsEntityLink` | `news_entity_links` | — |
| `DetectedEvent` | `detected_events` | affected_metrics |
| `EventImpact` | `event_impacts` | — |
| `EventDuplicate` | `event_duplicates` | — |

### 2.5 Agentes/Auditoria (9 tabelas)

| Classe | Tabela | JSONB |
|--------|--------|-------|
| `AgentDefinition` | `agent_definitions` | model_config |
| `AgentRun` | `agent_runs` | input_data, output_data |
| `AgentToolCall` | `agent_tool_calls` | input_params, output_result |
| `AgentAssessment` | `agent_assessments` | claims, risks, assumptions, data_gaps, invalidation_triggers |
| `EvidenceItem` | `evidence_items` | metric_ids |
| `InvestmentThesis` | `investment_theses` | key_drivers, risks, invalidation_criteria |
| `ThesisVersion` | `thesis_versions` | key_drivers, risks, invalidation_criteria |
| `Recommendation` | `recommendations` | supporting_assessments, opposing_arguments, invalidation_triggers |
| `AuditLog` | `audit_logs` | details |

### 2.6 Portfolio (7 tabelas)

| Classe | Tabela | JSONB |
|--------|--------|-------|
| `Portfolio` | `portfolios` | — |
| `Position` | `positions` | — |
| `Transaction` | `transactions` | — |
| `PortfolioConstraint` | `portfolio_constraints` | — |
| `RiskSnapshot` | `risk_snapshots` | sector_concentration, top_risks |
| `RebalanceProposal` | `rebalance_proposals` | current_allocation, proposed_allocation, risk_impact |
| `ProposedTrade` | `proposed_trades` | — |

### 2.7 Workflow/Avaliação (6 tabelas)

| Classe | Tabela | JSONB |
|--------|--------|-------|
| `WorkflowRun` | `workflow_runs` | — |
| `PromptVersion` | `prompt_versions` | — |
| `StructuredOutputSchema` | `structured_output_schemas` | json_schema |
| `Scorecard` | `scorecards` | veto_conditions_triggered |
| `BacktestResult` | `backtest_results` | details |
| `EvaluationResultRecord` | `evaluation_results` | — |

### 2.8 Outros (4 tabelas)

| Classe | Tabela | JSONB |
|--------|--------|-------|
| `MacroIndicator` | `macro_indicators` | — |
| `DataQualityCheck` | `data_quality_checks` | details |
| `DataRefreshLog` | `data_refresh_log` | — |
| `UniverseFilter` | `universe_filters` | criteria |
| `UniverseMembership` | `universe_memberships` | — |
| `Approval` | `approvals` | — |
| `ExecutionReconciliation` | `execution_reconciliations` | — |

### 2.9 Relacionamentos ORM

Apenas `Sector ↔ Industry` e `Issuer ↔ Ticker` possuem `relationship()`. Demais FKs são sem relationships explícitos.

---

## 3. Workflows Temporal (4)

| Workflow | Input | Output | Atividades | Task Queue |
|----------|-------|--------|------------|------------|
| `IngestCVMWorkflow` | `IngestCVMInput` | `IngestCVMOutput` | download → parse → validate → store → publish (5) | stock-intelligence |
| `AnalyzeFilingWorkflow` | `FilingData` | `FilingReviewVerdict` (dataclass) | metrics → analyst → critic → thesis → publish (5) | stock-intelligence |
| `AnalyzeNewsWorkflow` | `NewsArticle` | `NewsAnalysis` (dataclass) | analyst → compare → update → publish (4) | stock-intelligence |
| `DiscoverStocksWorkflow` | `ScreenFilters` | `list[DiscoveryBrief]` (dataclass) | universe → filter → metrics → anomalies → briefs → publish (6) | stock-intelligence |

**Observação:** Nenhum workflow define `@workflow.signal` ou `@workflow.query`. Scheduling é feito pelo scheduler asyncio interno, não pelo Temporal cron.

---

## 4. Agents (7 configs)

| Agente | Modelo | Temp | Max Tokens | Prompt Existe? | Output Schema |
|--------|--------|------|------------|----------------|---------------|
| `filing_analyst` | gpt-4o | 0.2 | 4096 | ✅ | `FilingReviewVerdict` |
| `news_analyst` | gpt-4o | 0.3 | 2048 | ✅ | `NewsAnalysis` |
| `fundamentalist_analyst` | gpt-4o | 0.2 | 4096 | ❌ | `ThesisVerdict` |
| `critic_agent` | o3-mini | 0.5 | 3072 | ✅ | None |
| `risk_director` | gpt-4o | 0.1 | 3072 | ❌ | `RiskAssessment` |
| `investment_committee` | o3-mini | 0.1 | 2048 | ✅ | `CommitteeDecision` |
| `research_coordinator` | gpt-4o | 0.4 | 2048 | ❌ | `DiscoveryBrief` |

**3 prompts ausentes:** `fundamentalist/`, `risk_director/`, `coordinator/`

---

## 5. Conectores/Fontes (5 fontes)

| Fonte | URL Base | Auth | Rate Limit | Formato | Licença |
|-------|----------|------|------------|---------|---------|
| B3 COTAHIST | bvmf.bmfbovespa.com.br | Nenhuma | Nenhum | ZIP→TXT 245 bytes/linha | Dados públicos |
| CVM Dados | dados.cvm.gov.br | Nenhuma | Nenhum | ZIP→CSV | Dados públicos governamentais |
| BCB Séries | api.bcb.gov.br | Nenhuma | Nenhum | JSON | Dados públicos |
| IBGE SIDRA | apisidra.ibge.gov.br | Nenhuma | Nenhum | JSON | Dados públicos |
| Google News / Reuters | news.google.com, reuters.com | Nenhuma | Nenhum | RSS/XML | Dados públicos |

**Classe base:** `HttpClient` — httpx async com retry exponencial (3 retries, backoff 1s/2s/4s), timeout 30s.

---

## 6. Variáveis de Ambiente por Serviço

| Variável | API | Worker | Scheduler | Alembic | Observável |
|----------|-----|--------|-----------|---------|------------|
| `DATABASE_URL` | ✅ | ✅ | ✅ | ✅ | — |
| `STORAGE_*` (4 vars) | ✅ | ✅ | — | — | — |
| `OPENAI_API_KEY` | — | ✅ | — | — | — |
| `OPENAI_BASE_URL` | — | ✅ | — | — | — |
| `LITELLM_GATEWAY_URL` | — | ✅ | — | — | — |
| `TEMPORAL_*` (3 vars) | — | ✅ | — | — | — |
| `OTLP_ENDPOINT` | — | — | — | — | ✅ |
| `ENABLE_OTEL` | — | — | — | — | ✅ |
| `MLFLOW_TRACKING_URI` | — | — | — | — | ✅ |
| `APP_ENV` | ✅ | ✅ | ✅ | — | — |
| `LOG_LEVEL` | ✅ | ✅ | ✅ | — | — |
| `DB_POOL_SIZE/MAX_OVERFLOW` | ✅ | ✅ | — | — | — |

---

## 7. Colisões e Órfãos

### 7.1 Colisões Críticas

| Colisão | Severidade | Detalhe |
|---------|------------|---------|
| `DiscoveryBrief` (Pydantic vs dataclass) | **ALTA** | Schema Pydantic e dataclass em workflow têm nomes iguais, campos diferentes |
| `FilingReviewVerdict` (Pydantic vs dataclass) | **ALTA** | Mesmo conflito |
| `NewsAnalysis` (Pydantic vs dataclass) | **ALTA** | Mesmo conflito |
| `EvaluationResult` import bug | **CRÍTICA** | `__init__.py` importa `EvaluationResult` de `.agents` mas só existe `EvaluationResultRecord` — **corrigido neste PR** |

### 7.2 Modelos Órfãos (não usados fora de `database/models/`)

`PromptVersion`, `WorkflowRun`, `StructuredOutputSchema`, `DataQualityCheck`, `DataRefreshLog`, `DocumentProcessingLog`, `DocumentDuplicate`, `DocumentEvent`, `EventDuplicate`, `UniverseFilter`, `UniverseMembership`, `Scorecard`, `BacktestResult`, `MacroIndicator`, `PortfolioConstraint`, `RiskSnapshot`, `RebalanceProposal`, `ProposedTrade`, `Approval`, `ExecutionReconciliation`, `EvaluationResultRecord`, `AgentToolCall`, `AgentAssessment`, `EvidenceItem`

### 7.3 Código Morto

- `scheduler/_run_ingest_cvm()` — instancia workflow sem executar
- `scheduler/_run_fetch_news()` — stub vazio

### 7.4 Fix Applied

- `src/database/models/__init__.py:15` — `EvaluationResult` → `EvaluationResultRecord` (bug de import corrigido)
