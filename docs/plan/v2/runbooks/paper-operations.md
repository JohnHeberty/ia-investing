# Runbook — Operação paper

## Suspensão imediata

Ative o kill switch global ou da carteira via `/api/v1/paper/kill-switches`. Isso bloqueia novos intents e submits, mas preserva leitura, reconciliação e resolução. Registre motivo e correlation ID. Não remova fills ou ledger.

## Break de reconciliação

1. Execute a reconciliação com cutoff timezone-aware.
2. Para break crítico, mantenha a carteira bloqueada e reconheça o alerta.
3. Compare order, soma de fills e `paper-fill:<event_key>` no ledger.
4. Corrija somente por lançamento compensatório ou nova versão; informe método e evidência na resolução.
5. Reexecute com o mesmo cutoff para provar idempotência e depois com novo cutoff.

## Recuperação e retomada

Valide preço/calendário, risk snapshot, approvals, worker Temporal e migrations. Um segundo operador, diferente de quem ativou, libera o kill switch. Execute uma ordem pequena paper e reconcilie antes de retomar schedules.

## Falha do worker ou replay

Não reenvie manualmente ordens. Consulte o workflow, restaure o worker `portfolio-risk` e deixe Temporal reproduzir o histórico. `submit_key`, `event_key` e `source_reference` evitam duplicação.

## Schedules diários

Configure `SCHEDULER__PAPER_PORTFOLIO_ID`, `SCHEDULER__PAPER_ORGANIZATION_ID`, `SCHEDULER__PAPER_PORTFOLIO_VERSION_ID` e `SCHEDULER__PAPER_REBALANCE_INPUT_SHA256`; execute o serviço `scheduler` uma vez para reconciliar as definições duráveis. Valuation reconcilia antes de publicar NAV; qualquer break bloqueante falha fechado. Rebalance semanal permanece em `awaiting_approval` e nunca libera ordem live.

## Verificação

Execute `pytest -q tests/unit/test_paper_execution.py`, `python scripts/verify_policy_paper_workflows.py` e `alembic check`. Confirme que OpenAPI não possui endpoint live nem dependência de broker.
