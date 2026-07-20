# ADR-002: Temporal para Execução Durável e Schedules

**Status:** Aceito
**Data:** 2026-07-18
**Decisor:** John Heberty de Freitas

## Contexto

O sistema precisa orquestrar fluxos de longa duração (ingestão de dados CVM, análise de documentos, análise de notícias, descoberta de ações) com tolerância a falhas, retry, visibilidade e auditabilidade. Atualmente o scheduler usa asyncio.sleep loop, que é frágil e não persiste estado.

## Decisão

Usar Temporal como motor de orquestração para workflows:

- 13 workflows definidos em `src/workflows/`: paper_rebalance, paper_reconciliation, paper_valuation, approval_gate, portfolio_construction, portfolio_optimization, run_agent, policy_event e outros
- Task queue: `stock-intelligence`
- Worker registrado em `apps/worker/main.py`
- Scheduling futuro via Temporal cron ou `TemporalSchedule`, não asyncio loop

## Alternativas Consideradas

1. **Celery + Redis** — Rejeitado: sem suporte nativo a workflows duráveis, sem versionamento de código, sem replay de execuções.

2. **APScheduler** — Rejeitado: adequado para cron simples, não para workflows multi-step com state.

3. **Airflow** — Rejeitado: overkill para este caso, DAG-oriented não se encaixa bem com agentes IA.

4. **asyncio loop (atual)** — Mantido temporariamente para scheduler, mas será substituído por Temporal schedules na Fase 1.

## Consequências

- **Positivas:** Retry automático, visibilidade via UI, versionamento de workflows, auditabilidade, state persistence.
- **Negativas:** Complexidade operacional (mais um serviço), learning curve, dependência de infrastructure.
- **Mitigações:** Temporal já está no docker-compose, worker já registrado, migração incremental.

## Referências

- `src/workflows/` — 13 workflows Temporal
- `src/apps/worker/main.py` — worker registration
- `src/apps/scheduler/main.py` — scheduler atual (será substituído)
- `docker-compose.yml` — serviços temporal e temporal-ui
