# Pendências Não-MVP

**Data:** 2026-08-13 (atualizado)
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

## Cobertura de Testes (72% → 80%)

**Status atual:** 72% coverage (~2.100 testes)
**Meta:** 80% coverage
**Gap:** ~1.000 linhas em módulos complexos

### Módulos que faltam testar (por ordem de impacto)

| Módulo | Linhas faltando | Cobertura atual | Tipo | Esforço |
|--------|-----------------|-----------------|------|---------|
| `production_runtime.py` | 568 | 13% | Temporal workflow factory | Alto |
| `news/service.py` | 235 | 12% | News processing pipeline | Médio |
| `market_data.py` | 179 | 12% | Market data service | Médio |
| API routes (combinado) | 500+ | ~40% | FastAPI endpoints | Alto |
| `agent_runtime.py` | 75 | 30% | Temporal activities | Médio |

### Estratégia para chegar a 80%

1. **Testar API routes com mocked FastAPI dependencies** (~200 linhas)
2. **Testar orchestration activities com mocked services** (~150 linhas)
3. **Testar market_data e news/service com HTTP mocks** (~400 linhas)
4. **Testar production_runtime com mock de Temporal** (~250 linhas)

**Esforço estimado:** ~8-10 horas de trabalho

---

## Concluído nesta Sessão

| Item | Status | Commit |
|------|--------|--------|
| FIX.md (53 findings) | ✅ | `c3dc299` |
| Candidate Intelligence (7 bugs) | ✅ | `4968ff7` |
| Segurança (14 fixes) | ✅ | `231c084` |
| Erros Lógicos (36 fixes) | ✅ | `cde22dc` |
| Deep Audit (25 fixes) | ✅ | `c2c6e03` |
| Acessibilidade (24 páginas) | ✅ | `4c0bcf4` |
| UI/UX (inline styles, botões) | ✅ | `33b6d71` |
| Testes (65% → 72%) | ✅ | `051426b` |
| CSP unsafe-eval dev | ✅ | `71a9f99` |
| Schedule history (PaperRebalance) | ✅ | `dc23d67` |
| RPCStatusCode enum | ✅ | `3253d8b` |
| Asserts → Exceptions | ✅ | `c9863f7` |
| Wildcard imports → Explícitos | ✅ | `c9863f7` |

---

## Próximos Passos (Pós-MVP)

1. **Coverage 80%** — Testar módulos complexos (production_runtime, news/service, market_data)
2. **Security tests** — Testes de penetração para auth e tenant isolation
3. **Integration tests** — Testes end-to-end com infra Docker
4. **Documentation** — Atualizar README com arquitetura e guia de setup
