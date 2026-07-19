# Runbook de Temporal Schedules

O reconciliador substitui o loop em memória. Configure
`SCHEDULER__CVM_CNPJ`, `SCHEDULER__CVM_ISSUER_ID` e
`SCHEDULER__CVM_YEAR`; depois execute:

```powershell
uv run python -m apps.scheduler.main
```

A execução é idempotente: cria o schedule ausente ou atualiza sua definição.
IDs seguem `cvm-dfp-<issuer>-<year>-<statement>`, overlap usa `SKIP`, a janela
de catch-up é uma hora e falha pausa o schedule.

## Operação e recuperação

```powershell
temporal schedule describe --schedule-id <id>
temporal schedule pause --schedule-id <id> --reason "incident"
temporal schedule unpause --schedule-id <id> --reason "recovered"
temporal schedule trigger --schedule-id <id>
```

Use a Temporal UI para confirmar última/próxima execução e histórico. Antes de
backfill, valide o intervalo e a idempotência do workflow; preserve o schedule
pausado durante a investigação e registre o motivo de pausa/despausa.
