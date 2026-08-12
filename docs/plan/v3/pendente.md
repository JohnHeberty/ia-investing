# Pendências Não-MVP

**Data:** 2026-08-12 (atualizado)
**Status:** Itens identificados mas NÃO bloqueantes para MVP

---

## Itens Aceitos por Design (Sem Fix Necessário)

### O1 — CSRF middleware não enforce para bearer token auth
- **Arquivo:** `src/apps/api/app_factory.py`
- **Motivo:** Bearer tokens não são vulneráveis a CSRF da mesma forma que cookies.
- **Decisão:** Design correto. Documentar.

### O8 — StartVotingRequest.proposals limitado a exatamente 1
- **Arquivo:** `src/apps/api/routes/committee.py`
- **Motivo:** Cada proposta recebe seu próprio ciclo de votação independente.
- **Decisão:** Intencional. Não alterar.

---

## Itens Cosméticos (Não Críticos)

### R5-33 — Naming inconsistente de migrations (5 séries)
- **Problema:** 5 convenções diferentes.
- **Solução:** Adotar `YYYYMMDD_NN` como padrão. Não alterar existentes.
- **Status:** Policy apenas, não requer código.

---

## Itens de Infra Dev (Não Críticos)

### R9-9 — MLflow password em plaintext no compose.yml
- **Realidade:** Usa interpolação de env var. Default é senha dev-only.
- **Status:** Aceitável para dev.

---

## Concluído nesta Sessão

| Item | Status | Commit |
|------|--------|--------|
| R5-29: financial_facts partitioning | ✅ | `91cf1e1` |
| R5-30: market_bars partitioning | ✅ | `91cf1e1` |
| R8: Test coverage (58% → 73%) | ✅ | `91cf1e1` |
| R5-16: Audit consolidation | ✅ | `91cf1e1` |
| Performance tests (23 benchmarks) | ✅ | `91cf1e1` |
| CI bugs (7 fixes) | ✅ | `4968ff7` |
| FIX.md (53 findings) | ✅ | `c3dc299` |

---

## Próximos Passos (Pós-MVP)

1. **Security tests** — Testes de penetração para auth e tenant isolation
2. **Integration tests** — Testes end-to-end com infra Docker
3. **Documentation** — Atualizar README com arquitetura e guia de setup
