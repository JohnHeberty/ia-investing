# Pendências Não-MVP

**Data:** 2026-08-10
**Status:** Itens identificados mas NÃO bloqueantes para MVP

---

## Itens Aceitos por Design (Sem Fix Necessário)

### O1 — CSRF middleware não enforce para bearer token auth
- **Arquivo:** `src/apps/api/app_factory.py`
- **Motivo:** Bearer tokens não são vulneráveis a CSRF da mesma forma que cookies. O middleware só valida CSRF quando `session_id` é truthy (session-based auth). Bearer tokens são enviados explicitamente pelo client via `Authorization` header.
- **Decisão:** Design correto. Documentar.

### O8 — StartVotingRequest.proposals limitado a exatamente 1
- **Arquivo:** `src/apps/api/routes/committee.py`
- **Motivo:** Cada proposta recebe seu próprio ciclo de votação independente com decision pack e decision record. Agrupar múltiplas propostas em uma única votação complicaria a lógica de quorum e decisão.
- **Decisão:** Intencional. Não alterar.

---

## Itens de Performance (Deferred — Requer Migração)

### R5-29 — financial_facts sem partitioning
- **Arquivo:** `src/database/models/financial_facts.py`
- **Problema:** ~500 issuers × 4 quarters × 50+ accounts = ~100k rows/ano. Após vários anos, milhões de linhas.
- **Solução:** Range partitioning por `knowledge_at`.
- **Esforço:** Médio (requer Alembic migration + refactor de queries)
- **Impacto:** Performance em consultas PIT

### R5-30 — MarketBar sem partitioning
- **Arquivo:** `src/database/models/market_data.py`
- **Problema:** ~500 instruments × 252 trading days/year × múltiplos intervals.
- **Solução:** Range partitioning por `bar_at`.
- **Esforço:** Médio (requer Alembic migration)
- **Impacto:** Performance em consultas temporais

---

## Itens Cosméticos (Não Críticos)

### R5-33 — Naming inconsistente de migrations (5 séries)
- **Problema:** 5 convenções diferentes: hex `f7a`, `a2f`, `b4c`, date-based `YYYYMMDD_NN`, auto-generated hash.
- **Solução:** Adotar `YYYYMMDD_NN` como padrão. Não alterar existentes.
- **Esforço:** Baixo (policy apenas)
- **Impacto:** Manutenibilidade

---

## Itens de Infra Dev (Não Críticos)

### R9-9 — MLflow password em plaintext no compose.yml
- **Arquivo:** `docker/compose.yml:341`
- **Realidade:** Usa interpolação de env var (`${POSTGRES_PASSWORD:-postgres-local-only}`). Default é senha dev-only.
- **Status:** Aceitável para dev. Produção usa `.env`.

---

## Próximos Passos (Pós-MVP)

1. **Partitioning** — Implementar quando volume de dados justificar
2. **R8: Test coverage** — Expandir testes para institutional_portfolio, nav, risk services
3. **R5-16: Audit consolidation** — Consolidar `AuditLogEntry` e `AuditLog` em um único sistema
4. **Performance tests** — Adicionar testes de carga para endpoints críticos
5. **Security tests** — Adicionar testes de penetração para auth e tenant isolation
