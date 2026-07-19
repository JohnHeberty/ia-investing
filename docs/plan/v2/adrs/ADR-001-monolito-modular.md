# ADR-001: Monólito Modular com Deployables Separados

**Status:** Aceito
**Data:** 2026-07-18
**Decisor:** John Heberty de Freitas

## Contexto

O repositório contém uma plataforma de pesquisa financeira com IA para o mercado brasileiro. Atualmente é um monólito Python com 17 subpacotes em `src/`, 3 entrypoints (API, worker, scheduler) e 6 serviços de infraestrutura (PostgreSQL, MinIO, Temporal, MLflow, OTel, Temporal UI).

## Decisão

Manter como monólito modular com deployables separados:

- **API** (`apps/api/`) — FastAPI, expõe REST endpoints
- **Worker** (`apps/worker/`) — Temporal worker, executa workflows
- **Scheduler** (`apps/scheduler/`) — Agendamento de tarefas periódicas

Os três compartilham o mesmo `pyproject.toml`, mesma imagem Docker (com CMD diferente), e mesmo package `src/`. Deploy via docker-compose com profiles ou Kubernetes com containers separados.

## Alternativas Consideradas

1. **Microserviços** — Separar conectores, normalização, agentes em serviços independentes. Rejeitado: complexidade operacional excessiva para equipe pequena, latência inter-service desnecessária.

2. **Serverless (Lambda/Cloud Functions)** — Rejeitado: workflows Temporal precisam de processo persistente, stateful orchestration.

3. **Monólito único com entrypoint** — Rejeitado: API e worker têm ciclos de vida e escalabilidade diferentes.

## Consequências

- **Positivas:** Deploy simples, compartilhamento de código, debug fácil, testes integrados.
- **Negativas:** Acoplamento de dependências, scaling granular limitado,Image Docker única.
- **Mitigações:** Profiles de docker-compose para dev, Kubernetes com HPA para worker, versionamento semântico.

## Referências

- `src/apps/api/main.py`, `src/apps/worker/main.py`, `src/apps/scheduler/main.py`
- `Dockerfile` (multi-stage, CMD variável)
- `docker-compose.yml` (6 serviços)
