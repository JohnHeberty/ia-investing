# Pendencias — IA Investing

> Gerado em 2026-07-24. Itens nao resolvidos.

---

## Backend — Bugs de codigo

### 1. `source_registry.py` — TOCTOU register_source + license creation
- **Severidade:** HIGH
- **Arquivo:** `src/ia_investing/application/source_registry.py`
- **Issue:** `register_source()` faz SELECT sem FOR UPDATE. Duas requests concorrentes podem criar source duplicado. License creation tambem sem IntegrityError tratado — causa 500 em vez de idempotencia.

### 2. `portfolio_ranking_materializer.py` — UPSERT + validacao
- **Severidade:** HIGH
- **Arquivo:** `src/ia_investing/application/portfolio_ranking_materializer.py`
- **Issue:** UPSERT com `WHERE` suprime `RETURNING` ( PostgreSQL ignora RETURNING em upserts com condicional ). Validacao `[0,1]` mascara bugs — `None` passa silenciosamente.

### 3. `research.py` — DoS + pagination
- **Severidade:** MEDIUM
- **Arquivo:** `src/ia_investing/application/research.py`
- **Issue:** `list_cases` sem `limit` max — aceita `limit=999999` e retorna tudo (DoS). UUIDv4 na pagination e non-deterministica (ordem aleatoria entre paginas).

### 4. `research_mock.py` — float(None) crash
- **Severidade:** MEDIUM
- **Arquivo:** `src/ia_investing/orchestration/activities/research_mock.py`
- **Issue:** `float(None)` na linha 114 causa TypeError. Dados mock podem ter `None` em campos numericos.

---

## Backend — Design / Seguranca

### 5. `portfolio_models.py` — Sem tenant isolation
- **Severidade:** HIGH
- **Arquivo:** `src/database/models/portfolio_optimization.py` (ou `portfolio_domain.py`)
- **Issue:** `ModelPortfolio` nao tem `organization_id`. Todos os portfolios sao visiveis por qualquer tenant. Falta FK + constraint + migration.

---

## Frontend

### 6. `hooks/use-risk-assessments.ts` — Dados sinteticos
- **Severidade:** MEDIUM
- **Arquivo:** `web/src/hooks/use-risk-assessments.ts`
- **Issue:** Retorna dados sinteticos hardcodados. O nome do hook sugere riscos reais mas entrega dados ficticios. Confunde quem usa.

---

## Features nao implementadas

### 7. Evals source discovery — DB seeding
- **Status:** Dataset JSON + seed script + testes criados. Falta rodar `seed_eval_datasets.py` no DB.
- **Arquivos:** `evals/agents/capabilities/company_source_discovery.json`, `scripts/seed_eval_datasets.py`, `tests/unit/test_source_discovery_dataset.py`

### 8. Observabilidade — dashboards
- **Status:** Nenhum dashboard implementado. OpenTelemetry configurado mas sem visualizacao.
- **Pendente:** Grafana/MLflow dashboards, metricas de negocio, alertas.

### 9. Conectores avancados
- **Status:** Sitemap/RSS/institutional site resolvers nao existem.
- **Impacto:** Dados de mercado limitados aos conectores CVM atuais.

---

## Melhorias de infra/qualidade

### 10. Testes de integracao OIDC
- **Cobertura:** Zero.
- **Pendente:** Mocks do OIDC provider, fluxo PKCE, refresh token, logout.

### 11. Testes unitarios frontend (vitest)
- **Cobertura:** 5 testes apenas.
- **Pendente:** Testes para hooks (useUrlState, usePermissions, useCommittee, etc.), componentes (Can, AppShell), pages.

### 12. docker-compose MinIO 9001 sem auth
- **Risco:** Console MinIO acessivel sem senha na porta 9001.
- **Fix:** Adicionar MINIO_ROOT_USER/PASSWORD ou desabilitar console em dev.

### 13. Migration env.py fragil
- **Arquivo:** `migrations/env.py`
- **Issue:** `sys.path.insert(0, ...)` para importar models. Fragil — quebra se a estrutura de diretorios mudar.

### 14. web/AGENTS.md duplicado
- **Arquivos:** `AGENTS.md` (raiz) + `web/AGENTS.md`
- **Issue:** Conteudo diferente nos dois. Cria confusao sobre qual seguir.
