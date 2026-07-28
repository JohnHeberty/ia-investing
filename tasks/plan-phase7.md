# Plano: Fase 7 — DB Duplications & Schema Cleanup

**Data:** 2026-07-28 | **Contexto:** Software ainda não rodou, sem dados em produção.
**Risco real:** BAIXO (sem dados para perder, migrações são seguras)

---

## Resumo

Limpar código morto de 13 tabelas, adicionar `updated_at` em 89 modelos, converter 1 ARRAY para JSONB, e extrair config de StrategyMandate para JSONB.

---

## Mapa de Código Morto (13 tabelas)

### Tabelas 100% mortas (zero usage em app code)

| # | Modelo | Tabela | Arquivo | Motivo |
|---|--------|--------|---------|--------|
| 1 | `RebalanceProposal` | `rebalance_proposals` | `portfolio_models.py` | Substituído por `rebalance.py:RebalanceProposal` |
| 2 | `ProposedTrade` | `proposed_trades` | `portfolio_models.py` | Filho de #1, sem uso |
| 3 | `AgentDefinition` | `agent_definitions` | `definitions.py` | Substituído por `agent_runtime.py` |
| 4 | `AgentRun` | `agent_runs` | `definitions.py` | Substituído por `AgentRuntimeRun` |
| 5 | `AgentToolCall` | `agent_tool_calls` | `definitions.py` | Substituído por `AgentRuntimeToolCall` |
| 6 | `AgentAssessment` | `agent_assessments` | `assessments.py` | Zero usage |
| 7 | `EvidenceItem` | `evidence_items` | `assessments.py` | Zero usage |
| 8 | `Approval` | `approvals` | `audit_models.py` | Zero usage |
| 9 | `ExecutionReconciliation` | `execution_reconciliations` | `audit_models.py` | Zero usage |
| 10 | `EvaluationResultRecord` | `evaluation_results` | `audit_models.py` | Zero usage |
| 11 | `InvestmentThesis` | `investment_theses` | `thesis.py` | Substituído por `thesis_domain.py` |
| 12 | `ThesisVersion` | `thesis_versions` | `thesis.py` | Substituído por `ResearchThesisVersion` |
| 13 | `Recommendation` | `recommendations` | `thesis.py` | Zero usage |

### Tabela parcialmente morta

| Modelo | Tabela | Arquivo | Status |
|--------|--------|---------|--------|
| `AuditLog` | `audit_logs` | `audit_models.py` | Usado em 13+ app files — MANTER |
| `AuditLogEntry` | `audit_log_entries` | `audit.py` | Usado por audit_service — MANTER |

> **Nota sobre AuditLog vs AuditLogEntry:** São sistemas de audit diferentes. `AuditLog` é append-only operacional (13+ services). `AuditLogEntry` é cadeia hash tamper-evident (audit_service). Ambos são ativos e não duplicados.

---

## Estratégia: Por que é Seguro

1. **Sem dados:** Não precisa de data migration (INSERT INTO ... SELECT FROM ...)
2. **Sem usage:** Todas as 13 tabelas têm zero imports em código de aplicação
3. **Sem FK dependente:** Nenhuma outra tabela tem FK apontando para essas 13 tabelas
4. **Alembic:** Migração usa `DROP TABLE IF EXISTS` — idempotente

---

## Tarefas

### Tarefa 1: Remover modelos mortos de `agents.py` e imports

**Descrição:** Remover 4 classes mortas do arquivo `agents.py` e atualizar `__init__.py`.

**Classes a remover:**
- `AgentDefinition` (definitions.py:12)
- `AgentRun` (definitions.py — não confundir com AgentRuntimeRun)
- `AgentToolCall` (definitions.py:65)
- `AgentAssessment` (assessments.py:12)
- `EvidenceItem` (assessments.py:47)
- `Approval` (audit_models.py:12)
- `ExecutionReconciliation` (audit_models.py:33)
- `EvaluationResultRecord` (audit_models.py:51)
- `InvestmentThesis` (thesis.py:12)
- `ThesisVersion` (thesis.py:39)
- `Recommendation` (thesis.py:66)

**Arquivos tocados:**
- `src/database/models/agents.py` — remover imports e re-exports
- `src/database/models/__init__.py` — remover da seção `agents` import
- `src/database/models/definitions.py` — deletar classes
- `src/database/models/assessments.py` — deletar classes
- `src/database/models/audit_models.py` — remover 3 classes (manter AuditLog)
- `src/database/models/thesis.py` — deletar arquivo inteiro

**Aceite:**
- [ ] `ruff check src/database/models/` passa
- [ ] Nenhum import quebrado em `src/` ou `tests/`
- [ ] `python3 -c "from database.models import Base"` funciona

---

### Tarefa 2: Remover RebalanceProposal/ProposedTrade de `portfolio_models.py`

**Descrição:** Remover as 2 classes mortas e atualizar re-exports.

**Arquivos tocados:**
- `src/database/models/portfolio_models.py` — remover classes `RebalanceProposal` e `ProposedTrade`
- `src/database/models/portfolio.py` — remover do re-export
- `src/database/models/__init__.py` — remover `ProposedTrade` e `RebalanceProposal` do import `portfolio`

**Aceite:**
- [ ] `ruff check` passa
- [ ] `from database.models.portfolio import Portfolio, Position` funciona

---

### Tarefa 3: Criar migration para DROP 13 tabelas mortas

**Descrição:** Criar migration Alembic que dropa as 13 tabelas.

**Migration:** `migrations/versions/20260728_04_drop_dead_tables.py`

```python
def upgrade() -> None:
    op.drop_table("rebalance_proposals")        # portfolio_models.py
    op.drop_table("proposed_trades")             # portfolio_models.py
    op.drop_table("agent_definitions")           # definitions.py
    op.drop_table("agent_runs")                  # definitions.py
    op.drop_table("agent_tool_calls")            # definitions.py
    op.drop_table("agent_assessments")           # assessments.py
    op.drop_table("evidence_items")              # assessments.py
    op.drop_table("approvals")                   # audit_models.py
    op.drop_table("execution_reconciliations")   # audit_models.py
    op.drop_table("evaluation_results")          # audit_models.py
    op.drop_table("investment_theses")           # thesis.py
    op.drop_table("thesis_versions")             # thesis.py
    op.drop_table("recommendations")             # thesis.py

def downgrade() -> None:
    # Criar tabelas vazias (estrutura apenas) para rollback
    ...
```

**Aceite:**
- [ ] `alembic upgrade head` roda sem erro
- [ ] `alembic downgrade -1` roda sem erro

---

### Tarefa 4: Migration para adicionar `updated_at` em 89 modelos

**Descrição:** Criar migration que adiciona coluna `updated_at` em todas as tabelas que têm `created_at` mas não `updated_at`.

**Migration:** `migrations/versions/20260728_05_add_updated_at.py`

**Abordagem:** Usar `op.add_column()` para cada tabela. Para tabelas sem dados, default `now()` é suficiente. Para tabelas que possam ter dados no futuro, backfill `updated_at = created_at`.

```python
TABLES = [
    "data_sources", "source_objects",
    "scorecards", "backtest_results",
    "raw_documents", "document_metadata", "documents",
    "macro_indicators",
    "claim_contradictions",
    "prompt_versions", "structured_output_schemas",
    "institutional_portfolio_versions", "portfolio_ledger_entries", "nav_publications",
    "policy_objects", "regulatory_actions",
    "agent_definitions", "agent_tool_calls",   # já dropados na migration anterior — REMOVER
    "valuation_runs",
    "data_quality_checks",
    "audit_log_entries",
    "legal_entities", "instruments", "listings",
    "portfolios", "positions", "transactions",
    "portfolio_constraints", "risk_snapshots",
    # ... (lista completa no código)
]

def upgrade() -> None:
    for table in TABLES:
        op.add_column(table, sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()))
```

**Aceite:**
- [ ] `alembic upgrade head` roda sem erro
- [ ] Todas as tabelas têm coluna `updated_at`
- [ ] `alembic downgrade -1` remove as colunas

**Nota:** As tabelas dropadas na Tarefa 3 NÃO devem estar nesta lista.

---

### Tarefa 5: Atualizar ORM models com `updated_at`

**Descrição:** Adicionar `updated_at: Mapped[datetime]` em todos os 89 modelos.

**Abordagem:** Usar `onupdate=utcnow` no ORM para auto-update. Cada modelo ganha:

```python
updated_at: Mapped[datetime] = mapped_column(
    sa.DateTime(timezone=True), default=utcnow, onupdate=utcnow
)
```

**Arquivos tocados:** 27 arquivos (listados acima no mapeamento).

**Aceite:**
- [ ] `ruff check src/database/models/` passa
- [ ] `python3 -c "from database.models import Base; print(len(Base.metadata.tables))"` retorna número correto

---

### Tarefa 6: Converter ARRAY para JSONB (R5-21)

**Descrição:** Converter `section_path: list[str]` de `ARRAY(Text)` para `JSONB` em `evidence.py`.

**Arquivo:** `src/database/models/evidence.py:27`

**Migration:** `migrations/versions/20260728_06_array_to_jsonb.py`

```python
def upgrade() -> None:
    op.alter_column(
        "document_chunks", "section_path",
        type_=postgresql.JSONB,
        postgresql_using="section_path::jsonb",
    )
```

**Aceite:**
- [ ] Migration roda sem erro
- [ ] Queries existentes funcionam (JSONB suporta operadores de array)

---

### Tarefa 7: Extrair StrategyMandate config para JSONB (R5-22)

**Descrição:** StrategyMandate tem 28 colunas (11 JSONB). Extrair colunas de configuração em um JSONB `config`.

**Abordagem:** Criar novo campo `config: Mapped[dict] = mapped_column(JSONB)` e mover 15 colunas de configuração para lá:

- **Manter como colunas diretas (13):** id, portfolio_id, version, status, created_at, updated_at, effective_from, effective_to, created_by, approved_by, approval_notes, mandate_type, mandate_hash
- **Mover para `config` (15):** target_return, max_tracking_error, max_concentration_pct, max_sector_pct, min_cash_pct, rebalance_threshold, rebalance_frequency, max_turnover, allowed_asset_classes, restricted_tickers, restricted_sectors, restricted_countries, benchmark_index, risk_budget, leverage_limit

**Migration:** `migrations/versions/20260728_07_mandate_config.py`

```python
def upgrade() -> None:
    op.add_column("strategy_mandates", sa.Column("config", postgresql.JSONB, server_default="{}"))
    # Migrar dados: ler cada row, mover colunas para config JSON, NULLificar colunas antigas
    # Depois: op.drop_column() das 15 colunas antigas
```

**Arquivos tocados:**
- `src/database/models/portfolio_mandates.py` — refatorar modelo
- `src/ia_investing/application/institutional_portfolio/_mandate.py` — adaptar queries
- `src/ia_investing/application/institutional_portfolio/_portfolio.py` — adaptar queries
- `src/apps/api/routes/institutional_portfolios.py` — adaptar response schema

**Aceite:**
- [ ] Migration roda sem erro
- [ ] Todos os tests passam
- [ ] Response schema da API não muda (mesmos campos visíveis)

**⚠️ Nota:** Esta tarefa é a mais complexa. Se quiser simplificar, podemos pular e deixar as 28 colunas como estão — o modelo funciona, só não é elegante.

---

### Tarefa 8: Atualizar `__init__.py` e verificar imports

**Descrição:** Limpar todos os imports mortos e garantir que `database.models` importa corretamente.

**Arquivo:** `src/database/models/__init__.py`

**Mudanças:**
- Remover seção `from .agents import (...)` — arquivo será deletado
- Remover seção `from .definitions import (...)` — arquivo será deletado  
- Remover seção `from .assessments import (...)` — arquivo será deletado
- Remover seção `from .thesis import (...)` — arquivo será deletado
- Atualizar `from .portfolio import (...)` — remover ProposedTrade, RebalanceProposal
- Manter seção `from .audit import AuditLogEntry`

**Aceite:**
- [ ] `python3 -c "from database.models import Base, AuditLogEntry, RebalanceProposal, ResearchThesis"` funciona
- [ ] Nenhum `ImportError` em toda a codebase

---

### Tarefa 9: Verificação final

**Descrição:** Rodar bateria completa de verificações.

**Comandos:**
```bash
ruff check src/database/models/
ruff format --check src/database/models/
python3 -c "from database.models import Base; print(f'{len(Base.metadata.tables)} tables')"
alembic upgrade head
alembic downgrade -1
alembic upgrade head
pytest tests/ -q --tb=short
```

**Aceite:**
- [ ] Todos os comandos passam
- [ ] Nenhum `ImportError` ou `AttributeError`
- [ ] Schema está consistente (todas as tabelas ativas têm `updated_at`)

---

## Checkpoints

### Checkpoint: Após Tarefa 2 (código morto removido)
- [ ] `ruff check` passa
- [ ] Nenhum import quebrado
- [ ] Modelos mortos não existem mais no código

### Checkpoint: Após Tarefa 4 (migration criada)
- [ ] `alembic upgrade head` roda
- [ ] `alembic downgrade -1` roda
- [ ] Tabelas dropadas desapareceram

### Checkpoint: Após Tarefa 7 (updated_at + JSONB)
- [ ] Todas as tabelas ativas têm `updated_at`
- [ ] `section_path` é JSONB
- [ ] Response schema não muda

### Checkpoint: Final (Tarefa 9)
- [ ] Todos os testes passam
- [ ] Schema consistente
- [ ] Pronto para commit

---

## Ordem de Execução

```
Tarefa 1  → Remover modelos mortos (agents.py, definitions, assessments, thesis, audit_models)
Tarefa 2  → Remover RebalanceProposal/ProposedTrade (portfolio_models.py)
Tarefa 3  → Migration DROP 13 tabelas
Tarefa 4  → Migration ADD updated_at em 89 tabelas
Tarefa 5  → Atualizar ORM models com updated_at
Tarefa 6  → ARRAY → JSONB (evidence.py)
Tarefa 7  → StrategyMandate config extraction (OPCIONAL — pular se complexo demais)
Tarefa 8  → Limpar __init__.py
Tarefa 9  → Verificação final + commit
```

**Tempo estimado:** 2-3h (sem Tarefa 7) ou 3-4h (com Tarefa 7)

---

## Riscos e Mitigações

| Risco | Impacto | Mitigação |
|-------|---------|-----------|
| Migration DROP falha por FK dependente | Alto | Verificar com `\d+ table_name` antes de dropar |
| updated_at default quebra inserts existentes | Médio | Usar `server_default=func.now()` — não afeta ORM |
| StrategyMandate migration perde dados | Alto | **Pular Tarefa 7** se incerto — modelo funciona como está |
| Import quebrado após limpeza | Médio | Rodar `python3 -c "from database.models import Base"` após cada tarefa |

---

## Decisões Pendentes

1. **Tarefa 7 (StrategyMandate):** Fazer ou pular? Modelo funciona com 28 colunas, mas não é elegante.
2. **AuditLog vs AuditLogEntry:** Manter ambos (servem propósitos diferentes) ou consolidar?

---

## Pergunta ao Usuário

Antes de executar, preciso saber:

1. **StrategyMandate (Tarefa 7):** Quer que eu extraia as 15 colunas de config para JSONB, ou deixo como está? (Funciona, só não é elegante)

2. **AuditLog:** Quer que eu mantenha os dois sistemas de audit (append-only operacional + hash chain), ou consolidar em um?
