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
  restaurada e permissões concedidas. Head atual: `20260813_03`.
- Bootstrap Compose agora roda seed idempotente; bugs do seed corrigidos.
- Ruff, format Python, Mypy, unit+architecture, frontend lint/typecheck/unit/build/format passaram.
- Storybook: 60 testes passaram em Chromium.

### Limitação conhecida

- `tests/integration` ainda tem 17 falhas quando executada contra o banco dev persistente: fixtures fazem commit usando
  tickers/URIs/hashes fixos e reexecuções colidem com o estado anterior. Não apagar o banco. Próximo passo seguro: banco e
  bucket efêmeros por run e atualização dos contratos residuais de Candidate Intelligence.
