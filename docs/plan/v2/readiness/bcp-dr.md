# BCP/DR — plano de exercício

## Escopo e objetivos a aprovar

Serviços críticos: Postgres, MinIO Raw Zone, Temporal, API e workers. O comitê deve definir RTO/RPO antes do exercício; valores não são inferidos neste documento.

## Restore isolado

1. Congele horário, versões, volumes e hashes; registre correlation ID.
2. Restaure backups em ambiente isolado, com credenciais distintas e sem egress de produção.
3. Execute migrations, checks de integridade, hashes da Raw Zone e contagens por agregado.
4. Reproduza workflows Temporal e reconcilie audit/outbox, orders, fills e ledger.
5. Meça RPO pelo último evento recuperado e RTO até health/E2E aprovados.

## Cenários de DR

Injetar perda de worker, source outage, Postgres indisponível, objeto ausente, schema drift, duplicate fill, reconciliation break e secret comprometido. Exercitar kill switch global/carteira e retomada four-eyes. Nenhuma falha permite fallback live ou edição manual não auditada.

## Evidência

Registre logs sanitizados, timestamps, versões, participantes por papel, RTO/RPO observado, divergências, findings e post-mortem. Um exercício não executado ou sem integridade reconciliada é blocker `no_go`.
