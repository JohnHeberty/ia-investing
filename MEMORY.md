# Session Log — IA Investing

## 2026-08-13 — Cron/schedules e auditoria geral

### Concluído

- Scheduler Temporal consolidado em `src/apps/scheduler/temporal_schedules.py`.
- Reconcile declarativo, seletivo e fail-fast; templates protegidos e endpoint arbitrário removido.
- Mapeamento de erros Temporal, validações de builders, outbox único a cada minuto e perfis Compose corrigidos.
- Deduplicação real de notícias em lote/idempotente; análise isolada por emissor.
- Histórico completo `running -> completed|failed` aplicado aos workflows agendáveis e Candidate Intelligence.
- UI de schedules e polling do trigger corrigidos.
- Auditoria backend/banco/workflows/frontend/infra executada; inventário em `docs/bug-audit-2026-08-13.md`.
- Migrations corrigidas: particionamento aplicável, consolidação de audit preserva logs globais, `restatement_logs`
  restaurada e permissões concedidas. Head atual: `20260813_04`.
- Bootstrap Compose agora roda seed idempotente; bugs do seed corrigidos.
- Ruff, format Python, Mypy, unit+architecture, frontend lint/typecheck/unit/build/format passaram.
- Storybook: 60 testes passaram em Chromium.

### Incidente RSS confirmado e corrigido

- O aviso `Execução pode não ter sido processada` escondia uma execução Temporal pendente desde 04/08, sem worker.
- Trigger agora rejeita run concorrente (409) e fila sem poller (503); frontend usa timestamp anterior ao trigger.
- `schedule_run_history` recebeu grants para `app`; execução real confirmou `running -> failed/completed` e `finished_at`.
- Dependência de produção `defusedxml` adicionada; era a causa raiz da falha no parser RSS.
- Consulta da análise por emissor trocada de `DISTINCT + ORDER BY` inválido por `EXISTS` issuer-scoped.
- Cadeia de causas Temporal agora é preservada no histórico, incluindo o erro raiz da activity.
- Docker build corrigido (`README.md` no contexto e `src/` antes do build); healthcheck de API desativado nos workers.
- Execução real `...-2026-08-13T15:38:07Z` concluiu: `fetched_count=1`, `analyzed_count=10`, emissor
  `00000000-0000-0000-0000-000000000002`. Worker `research-agents` permanece ativo.

### Limitação conhecida

- `tests/integration` ainda tem 17 falhas quando executada contra o banco dev persistente: fixtures fazem commit usando
  tickers/URIs/hashes fixos e reexecuções colidem com o estado anterior. Não apagar o banco. Próximo passo seguro: banco e
  bucket efêmeros por run e atualização dos contratos residuais de Candidate Intelligence.
- O gateway LLM respondeu `Bad request` na análise real; itens foram marcados como `llm_unavailable`, sem falhar a coleta.
- Ruff/Mypy globais têm erros nas rotas `risk_overview.py`, `portfolio_recommendations.py` e `news.py` introduzidas no
  commit concorrente `583d409`; os arquivos de cron/RSS modificados passam Ruff/Mypy.
