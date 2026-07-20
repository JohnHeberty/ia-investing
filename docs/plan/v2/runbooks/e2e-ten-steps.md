# Runbook E2E — 10 passos do Fase 1

Validação end-to-end do pipeline de dados financeiros, desde a ingestão CVM até
a publicação de evidências, cobrindo cada componente da plataforma.

## Pré-requisitos

- Stack completa levantada: `docker compose --profile dev up -d`
- Migrations aplicadas: `uv run alembic upgrade head`
- `.env` configurado com `SCHEDULER__CVM_CNPJ`, `SCHEDULER__CVM_ISSUER_ID`,
  `SCHEDULER__CVM_YEAR`
- `uv run python -m apps.scheduler.main` para criar o schedule CVM
- `uv run python -m apps.worker.main --capability data-ingestion` para o worker
- `uvicorn apps.api.main:app --reload --app-dir src` para a API

## Passo 1 — CVM Ingestion (schedule + workflow)

### Objetivo

Validar que o schedule CVM é criado de forma idempotente e que o workflow de
ingestão é disparado corretamente.

### Pré-requisitos

- Temporal Server rodando (porta 7233)
- Scheduler configurado e executado

### Comandos

```powershell
# Criar/atualizar schedule
uv run python -m apps.scheduler.main

# Listar schedules
temporal schedule list

# Descrever o schedule criado
temporal schedule describe --schedule-id cvm-dfp-<issuer_id>-<year>-DRE_con

# Forçar execução manual
temporal schedule trigger --schedule-id cvm-dfp-<issuer_id>-<year>-DRE_con
```

### Saída esperada

```
schedule=<id> result=created
```

O schedule aparece na listagem com `paused=false` e `next_action_time` definido.

### Verificação

```powershell
temporal workflow list --query "WorkflowType='IngestCVMWorkflow'"
```

O workflow deve aparecer com status `Running` ou `Completed`.

### Modo de falha

- **Schedule não cria**: verificar `SCHEDULER__CVM_CNPJ` e `SCHEDULER__CVM_ISSUER_ID`
  no `.env`
- **Workflow não dispara**: confirmar que o worker `data-ingestion` está rodando
  e escutando a fila correta

---

## Passo 2 — Raw zone hash verification em MinIO

### Objetivo

Validar que o conteúdo bruto é persistido no MinIO com hash SHA-256 imutável e
que re-ingestões do mesmo conteúdo são idempotentes.

### Pré-requisitos

- PostgreSQL e MinIO rodando
- Migrations aplicadas com a extensão `vector`

### Comandos

```powershell
uv run python scripts/verify_raw_zone.py
```

### Saída esperada

```
raw-zone-ok object=<uuid> versions=1,2 idempotent=true
```

### Verificação

O script registra um objeto, repete com o mesmo conteúdo (idempotente) e depois
registra com conteúdo alterado (nova versão). A saída confirma:

- `versions=1,2`: duas versões criadas
- `idempotent=true`: re-registro do mesmo conteúdo retorna a mesma versão

### Modo de falha

- **Erro de conexão**: verificar MinIO em `STORAGE__ENDPOINT`
- **Erro de permissão**: confirmar `STORAGE__ACCESS_KEY` e `STORAGE__SECRET_KEY`
- **SHA-256 mismatch**: conteúdo corrompido durante upload

---

## Passo 3 — Financial fact extraction sem conversão zero

### Objetivo

Validar que valores N/A, ausentes ou suprimidos são preservados como `None`
com status apropriado em vez de convertidos para zero.

### Pré-requisitos

- PostgreSQL rodando com dados do passo 2

### Comandos

```powershell
uv run python scripts/verify_point_in_time_facts.py
```

### Saída esperada

```
point-in-time-ok revisions=1,2 before=100 after=125 idempotent=true
```

### Verificação

O script cria duas revisões de um mesmo fato financeiro e valida:

- Primeira revisão: `value=100.00`
- Segunda revisão: `value=125.00`
- Consulta PIT antes da segunda revisão retorna `100.00`
- Consulta PIT depois retorna `125.00`
- Re-registro idempotente não cria terceira revisão

### Modo de falha

- **source_object_version_id não encontrado**: executar `verify_raw_zone.py` antes
- **Valor zero inesperado**: verificar `parse_value_status` em `connectors/cvm/_financials.py`

---

## Passo 4 — Metric calculation com lineage

### Objetivo

Validar que métricas financeiras (ex: current_ratio) são calculadas corretamente
a partir dos fatos e que a lineage (rastro) dos fatos componentes é preservada.

### Pré-requisitos

- Passos 2 e 3 executados com sucesso
- PostgreSQL com dados de teste

### Comandos

```powershell
uv run python scripts/verify_metric_lineage.py
```

### Saída esperada

```
metric-lineage-ok metric=current_ratio value=2.5 facts=2 idempotent=true
```

### Verificação

O script:

- Insere fatos `current_assets=10` e `current_liabilities=4`
- Calcula `current_ratio = 10/4 = 2.50`
- Verifica `coverage_ratio=1.0` (todos os componentes presentes)
- Verifica `lineage_ids` contém 2 IDs (rastro dos fatos)
- Recalcula idempotente: mesmo `observation_id`

### Modo de falha

- **LookupError na métrica**: verificar se o nome `current_ratio` está registrado
  no engine de métricas
- **Lineage vazia**: confirmar que os `taxonomy_account_id` estão corretos

---

## Passo 5 — Mocked provider execution

### Objetivo

Validar que o runtime de agentes AI executa com provider mock, produzindo
resultado estruturado e preservando a versão do agente.

### Pré-requisitos

- PostgreSQL rodando
- Prompts carregados em `prompts/`

### Comandos

```powershell
uv run python scripts/verify_agent_runtime.py
```

### Saída esperada

```
agent-runtime-ok capabilities=<n> artifacts=<n> idempotent=true four_eyes=true version_pinned=true structured_output=true duplicate_decision_blocked=true
```

### Verificação

O script valida:

- Sincronização idempotente do registry (mesmos IDs)
- Capability `filing` com versão ativa
- Criação de run com versão fixada
- Tool call com aprovação four-eyes
- Decisão duplicada bloqueada
- Execução com mock provider produz `status=succeeded`

### Modo de falha

- **AI__PROVIDER não é mock**: definir `AI__PROVIDER=mock` no `.env`
- **Prompts não encontrados**: verificar diretório `prompts/`

---

## Passo 6 — API persistence e query

### Objetivo

Validar que a API persiste e recupera dados corretamente via endpoints
REST com autenticação.

### Pré-requisitos

- API rodando: `uvicorn apps.api.main:app --reload --app-dir src`
- Banco com migrations aplicadas

### Comandos

```powershell
# Health check
curl http://localhost:8000/api/v1/health

# Verificar readiness (requer auth)
curl -H "Authorization: Bearer <token>" http://localhost:8000/api/v1/readiness/evidence
```

### Saída esperada

Health check retorna:

```json
{"status": "healthy", "checks": {"database": "ok", "s3": "ok"}}
```

### Verificação

- `status=healthy` confirma que PostgreSQL e MinIO estão acessíveis
- Endpoints de schedules listam os schedules criados no passo 1

### Modo de falha

- **database=error**: verificar `DATABASE__URL` e se o PostgreSQL está rodando
- **s3=error**: verificar `STORAGE__ENDPOINT` e se o MinIO está rodando

---

## Passo 7 — Trace correlation across components

### Objetivo

Validar que traces OpenTelemetry são propagados entre API, Temporal worker e
atividades, permitindo correlação de requests跨componentes.

### Pré-requisitos

- Telemetry habilitada: `TELEMETRY__ENABLED=true`
- Collector OTLP rodando (opcional: Jaeger para visualização)

### Comandos

```powershell
# Verificar spans via logs do worker
# Na prática, observar logs estruturados com trace_id

# Replay de histórico Temporal para verificar determinismo
uv run python scripts/verify_temporal_approval.py
```

### Saída esperada

```
temporal-approval-ok decision=approved version_pinned=true input_pinned=true cancel=true expiry=true replay=true
```

### Verificação

O script:

- Executa workflow de aprovação com signal/cancel/expiry
- Verifica replay do histórico (determinismo do workflow)
- `replay=true` confirma que o histórico é reproduzível

### Modo de falha

- **Replay falha**: workflow não é determinístico (evitar I/O direto no workflow)
- **Trace não propagado**: verificar `TracingInterceptor` no worker e scheduler

---

## Passo 8 — End-to-end idempotency proof

### Objetivo

Validar que toda a pipeline é idempotente: re-execuções não criam duplicatas
nem corrompem estado.

### Pré-requisitos

- Todos os passos anteriores executados com sucesso

### Comandos

```powershell
uv run python scripts/verify_e2e_idempotency.py
```

### Saída esperada

```
e2e-idempotency-ok raw_zone=true facts=true metrics=true quality_gate=true
```

### Verificação

O script re-executa operações críticas e verifica:

- Raw zone: mesmo conteúdo retorna mesmo `version_id`
- Facts: mesma revisão retorna `created=false`
- Metrics: mesmo cálculo retorna mesmo `observation_id`
- Quality gate: mesmo incidente retorna mesmo `incident_id`

### Modo de falha

- **Qualquer assert falhou**: há estado mutável não idempotente
- **Verificar**: constraints de banco, unique indexes, lógica de upsert

---

## Passo 9 — Schedule status monitoring

### Objetivo

Validar que o status dos schedules pode ser monitordado via API e CLI,
incluindo pausa, retomada e trigger manual.

### Pré-requisitos

- Schedule CVM criado (passo 1)
- API rodando com auth configurado

### Comandos

```powershell
# Via API
curl -H "Authorization: Bearer <token>" http://localhost:8000/api/v1/schedules

# Via CLI Temporal
temporal schedule list
temporal schedule describe --schedule-id cvm-dfp-<issuer_id>-<year>-DRE_con

# Pausar
temporal schedule pause --schedule-id cvm-dfp-<issuer_id>-<year>-DRE_con --reason "incident"

# Despausar
temporal schedule unpause --schedule-id cvm-dfp-<issuer_id>-<year>-DRE_con --reason "recovered"

# Trigger manual
temporal schedule trigger --schedule-id cvm-dfp-<issuer_id>-<year>-DRE_con
```

### Saída esperada

A API retorna lista de schedules com `schedule_id`, `status`, `paused`,
`next_action_time` e `spec`.

### Verificação

- `paused=false` durante operação normal
- Após pausa: `paused=true`
- Após trigger: workflow `IngestCVMWorkflow` é iniciado

### Modo de falha

- **API retorna 404**: schedule não foi criado no passo 1
- **Pausa não funciona**: verificar permissões `schedules:manage`

---

## Passo 10 — Full cycle evidence publication

### Objetivo

Validar que evidências de readiness são publicadas, verificadas e integradas
ao decision pack com votação e decisão.

### Pré-requisitos

- API rodando com autenticação e autorização
- Banco com migrations aplicadas

### Comandos

```powershell
# Registrar evidência
curl -X POST http://localhost:8000/api/v1/readiness/evidence \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: evidence-e2e-cycle-001" \
  -H "X-Correlation-ID: <uuid>" \
  -d '{
    "evidence_type": "e2e_verification",
    "title": "Full cycle evidence publication test",
    "artifact_uri": "fixture://e2e/evidence/cycle-001",
    "content_sha256": "a" * 64,
    "issued_by": "e2e-automation",
    "independent": true,
    "issued_at": "2026-07-18T12:00:00Z"
  }'

# Verificar evidência
curl -X POST http://localhost:8000/api/v1/readiness/evidence/<id>/verification \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: verify-e2e-cycle-001" \
  -d '{"accepted": true}'

# Congelar decision pack
curl -X POST http://localhost:8000/api/v1/readiness/decision-packs \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: pack-e2e-cycle-001" \
  -d '{
    "manifest": {"evidence_ids": ["<evidence_id>"], "cycle": "e2e"},
    "expires_at": "2026-12-31T23:59:59Z"
  }'

# Votar no pack
curl -X POST http://localhost:8000/api/v1/readiness/decision-packs/<pack_id>/votes \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: vote-e2e-cycle-001" \
  -d '{
    "role": "portfolio_manager",
    "vote": "go",
    "rationale": "E2E full cycle verified",
    "conflicts": []
  }'

# Decidir
curl -X POST http://localhost:8000/api/v1/readiness/decision-packs/<pack_id>/decision \
  -H "Authorization: Bearer <token>" \
  -H "Idempotency-Key: decide-e2e-cycle-001"
```

### Saída esperada

- Evidência criada com `status=pending`
- Verificação altera para `status=verified`
- Decision pack criado com `version=1`
- Voto registrado com `vote=go`
- Decisão registrada com `result=approved`

### Verificação

- Cada operação retorna o registro persistido
- Idempotency keys evitam duplicatas
- Correlation ID permite rastreamento跨requests

### Modo de falha

- **403 Forbidden**: verificar permissões do token JWT
- **409 Conflict**: idempotency key já utilizada (reutilizar ou gerar nova)
- **Evidência não verificada**: verificar `independent=true` para verificação independente
