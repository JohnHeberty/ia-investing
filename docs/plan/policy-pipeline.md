# Plano: Pipeline de Política Inteligente

**Data:** 2026-08-13
**Objetivo:** Implementar pipeline completo de coleta e processamento de dados oficiais de política
**Esforço estimado:** ~40h (8 fases)

---

## Visão Geral da Arquitetura

```
FONTE OFICIAL                    FONTE NOTICIA (existente)
(Câmara, Senado, DOU, BCB)       (RSS Google News, Reuters)
        │                                    │
        ↓                                    ↓
[NOVO] OfficialPolicyClient          connectors/news/_rss.py
        │                                    │
        ↓                                    ↓
[NOVO] PolicyExtractionActivity       news_extraction.py
        │                                    │
        ↓                                    ↓
[NOVO] PolicyCollectionWorkflow       ExtractNewsWorkflow
        │                                    │
        ↓                                    ↓
[NOVO] PolicyIngestionService         news/service.py
        │                                    │
        ↓                                    ↓
[NOVO] PolicyObject + Version         detected_events
        │                                    │
        ↓                                    ↓
[NOVO] PolicyStageEvent               event_impacts → theses
        │
        ↓
[NOVO] PolicyProbabilityForecast
        │
        ↓
[NOVO] PolicyAlert (evaluation)
        │
        ↓
[EXISTENTE] PolicyEventWorkflow (review gate)
        │
        ↓
[EXISTENTE] Grafo de Política (nodes + edges)
```

---

## Fase 1: Fundação — Domain Tests + DB Model + Migration

### 1.1 Domain Tests para Código Existente

**Objetivo:** Garantir que o domain logic existente está coberto antes de adicionar novas features.

**Arquivos a criar:**

| Arquivo | Testes | Prioridade |
|---------|--------|------------|
| `tests/unit/domain/policy/test_domain_policy.py` | ~25 testes | Alta |
| `tests/unit/domain/policy/test_domain_policy_alerts.py` | ~15 testes | Alta |
| `tests/unit/domain/policy/test_domain_policy_historical.py` | ~8 testes | Média |
| `tests/unit/domain/policy/test_domain_macro.py` | ~12 testes | Média |

**Cenários de teste para `policy.py`:**
- `canonical_policy_key()` — determinismo, formato, autoridades diferentes
- `validate_policy_stage_transition()` — transições válidas/inválidas para cada tipo legal
- `text_diff()` — adições, remoções, mudanças, strings idênticas
- `base_rate()` — Jeffreys smoothing, Wilson score, edge cases (0 amostras, 100% sucesso)
- `brier_score()` — perfeição (0), pior caso (1), valores intermediários
- `propagate_impact()` — grafo acíclico, ciclos, confiança zero, confiança total
- `material_review_required()` — threshold, fatores ausentes, materialidade zero
- `detect_rectification()` — amendment, rectification, revocation, veto, suspension, sem mudança
- `compute_versioned_features()` — determinismo, campos ausentes, valores extremos

**Cenários de teste para `policy_alerts.py`:**
- `should_fire_alert()` — threshold exato, abaixo, acima, zero
- `is_duplicate()` — dentro da janela, fora da janela, primeira chamada
- `evaluate_rules()` — todas as 6 regras, regras customizadas, sem regras

**Cenários de teste para `policy_historical.py`:**
- `historical_outcomes()` — filtragem por knowledge_cutoff, contagem por tipo
- Validação dos 13 outcomes hardcoded

**Cenários de teste para `macro.py`:**
- `macro_definition_hash()` — determinismo, valores diferentes
- `validate_macro_definition()` — campos obrigatórios, frequências inválidas
- `point_in_time_macro_values()` — seleção PIT, sem dados, dados exatos
- `transform_macro_values()` — level, difference, pct_change, yoy, sem transformação
- `resample_macro_values()` — monthly, quarterly, annual, aggregation (last/sum/mean)

### 1.2 Policy Alerts DB Model

**Objetivo:** Criar persistência para alertas (atualmente são in-memory).

**Novo model em `src/database/models/policy_intelligence.py`:**

```python
class PolicyAlert(Base):
    __tablename__ = "policy_alerts"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    policy_object_id: Mapped[UUID] = mapped_column(ForeignKey("policy_objects.id"), index=True)
    alert_type: Mapped[str] = mapped_column(String(50), nullable=False)  # AlertType enum
    severity: Mapped[str] = mapped_column(String(20), nullable=False)  # AlertSeverity enum
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    details: Mapped[dict | None] = mapped_column(JSONB)
    fired_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    acknowledged_by: Mapped[str | None] = mapped_column(String(200))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_by: Mapped[str | None] = mapped_column(String(200))
    resolution_notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
```

### 1.3 Migration

**Arquivo:** `migrations/versions/YYYYMMDD_01_policy_alerts.py`

```python
def upgrade():
    op.create_table(
        "policy_alerts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("policy_object_id", sa.Uuid(), sa.ForeignKey("policy_objects.id"), nullable=False, index=True),
        sa.Column("alert_type", sa.String(50), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("details", postgresql.JSONB()),
        sa.Column("fired_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True)),
        sa.Column("acknowledged_by", sa.String(200)),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.Column("resolved_by", sa.String(200)),
        sa.Column("resolution_notes", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_policy_alerts_policy_object_id", "policy_alerts", ["policy_object_id"])
    op.create_index("ix_policy_alerts_fired_at", "policy_alerts", ["fired_at"])

    # Índices faltantes em tabelas existentes
    op.create_index("ix_policy_stage_events_stage", "policy_stage_events", ["policy_object_id", "stage"])
    op.create_index("ix_regulatory_actions_authority", "regulatory_actions", ["authority"])
    op.create_index("ix_regulatory_actions_action_type", "regulatory_actions", ["action_type"])
```

---

## Fase 2: Application Services

### 2.1 RegulatoryAction Ingestion Service

**Extensão em `src/ia_investing/application/policy_intelligence.py`:**

```python
class RegulatoryActionService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def ingest(
        self,
        *,
        policy_object_id: UUID,
        action_type: str,
        title: str,
        issued_at: datetime,
        rectifies: UUID | None = None,
        authority: str,
        source_object_version_id: UUID,
        actor_subject: str,
        permissions: frozenset[str],
    ) -> RegulatoryAction:
        # 1. Verificar permissão policy:write
        # 2. Verificar que policy_object existe
        # 3. Criar RegulatoryAction
        # 4. Criar PolicyStageEvent se applicable
        # 5. Retornar RegulatoryAction
```

### 2.2 Probability Forecast Service

```python
class ProbabilityForecastService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_forecast(
        self,
        *,
        policy_object_id: UUID,
        target_outcome: str,
        probability: Decimal,
        interval_low: Decimal | None = None,
        interval_high: Decimal | None = None,
        factors: dict | None = None,
    ) -> PolicyProbabilityForecast:
        # 1. Validar probability [0, 1]
        # 2. Criar forecast
        # 3. Avaliar alertas de probability_shift
```

### 2.3 Alert Evaluation Service

```python
class PolicyAlertService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def evaluate_and_fire(
        self,
        *,
        policy_object_id: UUID,
        policy_object: dict,
        latest_version: dict,
        stage_events: list[dict],
        forecasts: list[dict],
    ) -> list[PolicyAlert]:
        # 1. Carregar regras de alerta
        # 2. Avaliar cada regra contra o estado atual
        # 3. Verificar deduplicação
        # 4. Persistir alertas novos
        # 5. Retornar alertas disparados

    async def acknowledge(self, alert_id: UUID, actor: str) -> PolicyAlert: ...
    async def resolve(self, alert_id: UUID, actor: str, notes: str) -> PolicyAlert: ...
    async def list_alerts(self, policy_object_id: UUID | None = None, status: str = "active") -> list[PolicyAlert]: ...
```

---

## Fase 3: Connector Pipeline

### 3.1 Novo conector BCB SGS

**Arquivo:** `src/connectors/policy/_bcb_sgs.py`

```python
class BCBSGSClient:
    """Banco Central do Brasil — Sistema Gerenciador de Séries Temporais."""

    BASE_URL = "https://api.bcb.gov.br/dados/serie/bcdata"

    async def fetch_series(
        self,
        *,
        series_code: str,
        start_date: date,
        end_date: date,
    ) -> list[dict]:
        # GET /dados/serie/bcdata.{series_code}/dados?formato=json&dataInicial=...&dataFinal=...
```

### 3.2 Novo conector IBGE SIDRA

**Arquivo:** `src/connectors/policy/_ibge_sidra.py`

```python
class IBGESIDRAClient:
    """IBGE — Sistema de Recuperação de Dados Agregados."""

    BASE_URL = "https://apisidra.ibge.gov.br"

    async def fetch_table(
        self,
        *,
        table_id: int,
        variables: list[int],
        territorial_level: int = 1,
        period: str | None = None,
    ) -> list[dict]:
        # GET /tabelas/{table_id}/dados/nulos/{territorial_level}/d{period}
```

### 3.3 Extensão Senado batch

**Extensão em `src/connectors/policy/_official.py`:**

```python
async def senado_matters_batch(
    self,
    *,
    matter_type: str | None = None,
    since: date | None = None,
    limit: int = 100,
) -> list[OfficialPolicyRecord]:
    """Fetch multiple matters from Senado API."""
    # GET /materias/{tipo}/{caminho} with pagination
```

### 3.4 Extensão DOU scheduled

**Extensão em `src/connectors/policy/_official.py`:**

```python
async def dou_acts_since(
    self,
    *,
    since: date,
    section: str | None = None,
) -> list[FetchedOfficialPayload]:
    """Fetch DOU acts since a given date."""
    # Parse DOU XML feed with date filter
```

---

## Fase 4: Temporal Pipeline

### 4.1 Policy Extraction Activities

**Novo arquivo:** `src/ia_investing/orchestration/activities/policy_extraction.py`

```python
@activity.defn(name="fetch_policy_objects")
async def fetch_policy_objects(params: dict) -> dict:
    """Fetch policy objects from government APIs."""
    authority = params["authority"]
    since = params.get("since")

    if authority == "camara":
        records = await OfficialPolicyClient().camara_proposals(since=since)
    elif authority == "senado":
        records = await OfficialPolicyClient().senado_matters_batch(since=since)
    elif authority == "dou":
        records = await OfficialPolicyClient().dou_acts_since(since=since)
    # ...

    return {"count": len(records), "records": [r.model_dump() for r in records]}

@activity.defn(name="ingest_policy_objects")
async def ingest_policy_objects(params: dict) -> dict:
    """Ingest fetched policy objects into the database."""
    async with session_scope() as session:
        service = PolicyIngestionService(session)
        ingested = 0
        for record in params["records"]:
            await service.ingest(...)
            ingested += 1
        await session.commit()
    return {"ingested": ingested}

@activity.defn(name="process_policy_events")
async def process_policy_events(params: dict) -> dict:
    """Run political agent on ingested policy objects."""
    # Chamar agent "political" via AgentExecutionService
    # Processar output e criar PolicyStageEvent
```

### 4.2 Policy Collection Workflow

**Extensão em `src/workflows/_policy_event.py`:**

```python
@workflow.defn(name="PolicyCollectionWorkflow")
class PolicyCollectionWorkflow:
    @workflow.run
    async def run(self, input: PolicyCollectionInput) -> PolicyCollectionResult:
        # 1. fetch_policy_objects (por autoridade)
        # 2. ingest_policy_objects
        # 3. process_policy_events (agent political)
        # 4. evaluate_alerts
        # 5. Retornar resultado
```

### 4.3 Schedule Definition

**Extensão em `src/apps/scheduler/temporal_schedules.py`:**

```python
def policy_collection_schedule_definition(
    *,
    authority: str,
    every: timedelta = timedelta(hours=6),
    task_queue: str = "research-agents",
) -> ScheduleDefinition:
    schedule_id = f"policy-collection-{authority}"
    return ScheduleDefinition(
        schedule_id=schedule_id,
        schedule=Schedule(
            action=ScheduleActionStartWorkflow(
                PolicyCollectionWorkflow.run,
                PolicyCollectionInput(authority=authority),
                id=schedule_id,
                task_queue=task_queue,
            ),
            spec=ScheduleSpec(intervals=[ScheduleIntervalSpec(every=every)]),
            policy=SchedulePolicy(
                overlap=ScheduleOverlapPolicy.SKIP,
                catchup_window=timedelta(hours=2),
                pause_on_failure=True,
            ),
        ),
    )
```

### 4.4 Registry Update

**Extensão em `src/ia_investing/orchestration/registry.py`:**

```python
POLICY_ACTIVITIES = (
    fetch_policy_objects,
    ingest_policy_objects,
    process_policy_events,
)

# Adicionar ao research-agents capability:
"research-agents": CapabilityDefinition(
    task_queue="research-agents",
    workflows=(..., PolicyCollectionWorkflow, PolicyEventWorkflow),
    activities=(..., POLICY_ACTIVITIES),
),
```

---

## Fase 5: API Layer

### 5.1 Novos Endpoints

**Extensão em `src/apps/api/routes/policy.py`:**

| Método | Path | Descrição |
|--------|------|-----------|
| `GET` | `/api/v1/policy/alerts` | Listar alertas (filtrável por policy_object_id, status) |
| `POST` | `/api/v1/policy/alerts/{id}/acknowledge` | Reconhecer alerta |
| `POST` | `/api/v1/policy/alerts/{id}/resolve` | Resolver alerta |
| `GET` | `/api/v1/policy/forecasts` | Listar previsões de probabilidade |
| `GET` | `/api/v1/policy/stages/{id}` | Timeline de estágios |
| `GET` | `/api/v1/policy/regulatory-actions` | Listar ações regulatórias |
| `POST` | `/api/v1/policy/votes` | Registrar voto |

### 5.2 Pydantic Models

```python
class PolicyAlertV1(BaseModel):
    id: UUID
    policy_object_id: UUID
    alert_type: str
    severity: str
    title: str
    description: str | None
    fired_at: datetime
    acknowledged_at: datetime | None
    resolved_at: datetime | None

class PolicyAlertResolveRequest(BaseModel):
    notes: str = Field(min_length=3, max_length=4000)

class PolicyForecastV1(BaseModel):
    id: UUID
    policy_object_id: UUID
    target_outcome: str
    probability: Decimal
    interval_low: Decimal | None
    interval_high: Decimal | None
    factors: dict | None

class PolicyStageEventV1(BaseModel):
    id: UUID
    policy_object_id: UUID
    stage: str
    occurred_at: datetime
    knowledge_at: datetime
```

---

## Fase 6: Frontend

### 6.1 use-policy.ts Rewrite

**Padrão:** Provider pattern (como use-news.ts)

```typescript
interface PolicyDataContext {
  events: PolicyEvent[];
  alerts: PolicyAlert[];
  forecasts: PolicyForecast[];
  stages: PolicyStageEvent[];
  graph: PolicyGraph;
  regulatoryActions: RegulatoryAction[];
  isLoading: boolean;
  error: Error | null;
}
```

### 6.2 Policy Page Rewrite

**Nova estrutura de tabs:**

| Tab | Componente | Dados |
|-----|------------|-------|
| **Tracker** | LegislativeTracker | PolicyObject + stages + probability |
| **Alertas** | AlertList | PolicyAlert |
| **Previsões** | ForecastTable | PolicyProbabilityForecast |
| **Grafo** | ExposureGraph | PolicyGraph nodes + edges |
| **Ações Regulatórias** | RegulatoryActions | RegulatoryAction |
| **Fontes** | SourcesTable | Policy sources (Câmara, Senado, DOU, BCB) |

### 6.3 Páginas Novas

| Página | Rota | Descrição |
|--------|------|-----------|
| `web/src/app/policy/alerts/page.tsx` | `/policy/alerts` | Gestão de alertas |
| `web/src/app/policy/graph/page.tsx` | `/policy/graph` | Visualização do grafo |
| `web/src/app/policy/sources/page.tsx` | `/policy/sources` | Cadastro de fontes |

### 6.4 API Client Updates

**Adicionar em `web/src/lib/api-client.ts`:**

```typescript
// Query keys
policyAlerts: ["policyAlerts"] as const,
policyForecasts: ["policyForecasts"] as const,
policyGraph: ["policyGraph"] as const,
policyStages: ["policyStages"] as const,
policyRegulatoryActions: ["policyRegulatoryActions"] as const,

// API functions
export const policyApi = {
  listAlerts: (params?: AlertParams) => api<PolicyAlert[]>("/policy/alerts", { params }),
  acknowledgeAlert: (id: string) => api<void>(`/policy/alerts/${id}/acknowledge`, { method: "POST" }),
  resolveAlert: (id: string, notes: string) => api<void>(`/policy/alerts/${id}/resolve`, { method: "POST", body: JSON.stringify({ notes }) }),
  listForecasts: (params?: ForecastParams) => api<PolicyForecast[]>("/policy/forecasts", { params }),
  listRegulatoryActions: (params?: ActionParams) => api<RegulatoryAction[]>("/policy/regulatory-actions", { params }),
  getStages: (id: string) => api<PolicyStageEvent[]>(`/policy/stages/${id}`),
};
```

### 6.5 Navegação

**Atualizar `web/src/components/app-shell.tsx`:**

```typescript
// Adicionar sub-itens sob "Política"
{ label: "Tracker", href: "/policy" },
{ label: "Alertas", href: "/policy/alerts" },
{ label: "Fontes", href: "/policy/sources" },
{ label: "Grafo", href: "/policy/graph" },
```

---

## Fase 7: Remoção de Código Morto

### 7.1 check_alert_threshold

**Arquivo:** `src/ia_investing/orchestration/activities/news_extraction.py`

**Ação:** Remover a função `check_alert_threshold` e removê-la de `NEWS_EXTRACTION_ACTIVITIES`.

### 7.2 Verificação de imports não usados

**Arquivos:** `src/ia_investing/news/service.py`, `src/ia_investing/orchestration/activities/news_extraction.py`

**Ação:** Remover imports não utilizados após remoção do código morto.

---

## Fase 8: Integração e Testes

### 8.1 Testes de Integração

**Arquivo:** `tests/integration/test_policy_pipeline.py`

**Cenários:**
1. Criar fonte → Buscar objetos → Ingerir → Verificar PolicyObject criado
2. Processar evento → Verificar PolicyStageEvent criado
3. Criar forecast → Verificar alerta disparado
4. Reconhecer alerta → Verificar status atualizado

### 8.2 Verificação Docker

```bash
docker compose --profile dev up -d
# Verificar que:
# - Policy schedules aparecem no Temporal UI
# - Frontend carrega sem erros
# - API endpoints respondem corretamente
```

### 8.3 Verificação de Migração

```bash
alembic upgrade head
# Verificar que:
# - policy_alerts table existe
# - Índices foram criados
# - Dados existentes não foram afetados
```

---

## Resumo de Entregáveis

| Fase | Arquivos Novos | Arquivos Modificados | Testes |
|------|---------------|---------------------|--------|
| 1 | 4 test files | 1 model, 1 migration | ~60 |
| 2 | 0 | 1 service | ~20 |
| 3 | 2 connectors | 1 connector | ~15 |
| 4 | 1 activity file | 2 workflows, 1 registry | ~15 |
| 5 | 0 | 1 route file | ~20 |
| 6 | 3 pages, 1 hook | 2 files | ~10 |
| 7 | 0 | 2 files | 0 |
| 8 | 1 integration test | 0 | ~10 |
| **Total** | **10** | **12** | **~135** |

---

## Ordem de Execução Recomendada

```
Fase 1 (Fundação) ──────────────────────────────────┐
  1a. Domain tests                                   │
  1b. PolicyAlert model + migration                  │
  1c. API client keys                                │
                                                    ├─→ Fase 2 (Services)
Fase 2 (Services) ──────────────────────────────────┤
  2a. RegulatoryAction service                       │
  2b. Forecast service                               │
  2c. Alert service                                  │
  2d. Service tests                                  │
                                                    ├─→ Fase 3 (Connectors)
Fase 3 (Connectors) ────────────────────────────────┤
  3a. BCB SGS                                        │
  3b. IBGE SIDRA                                     │
  3c. Senado batch                                   │
  3d. DOU scheduled                                  │
  3e. Connector tests                                │
                                                    ├─→ Fase 4 (Temporal)
Fase 4 (Temporal) ──────────────────────────────────┤
  4a. Activities                                     │
  4b. Workflow                                       │
  4c. Schedule + registry                            │
  4d. Settings                                       │
  4e. Workflow tests                                 │
                                                    ├─→ Fase 5 (API)
Fase 5 (API) ───────────────────────────────────────┤
  5a. Novos endpoints                                │
  5b. API tests                                      │
                                                    ├─→ Fase 6 (Frontend)
Fase 6 (Frontend) ──────────────────────────────────┤
  6a. use-policy.ts rewrite                          │
  6b. Policy page tabs                               │
  6c. Alerts page                                    │
  6d. Graph page                                     │
  6e. Sources page                                   │
                                                    ├─→ Fase 7 (Cleanup)
Fase 7 (Cleanup) ───────────────────────────────────┤
  7a. Remover código morto                           │
  7b. Remover imports não usados                     │
                                                    ├─→ Fase 8 (Integration)
Fase 8 (Integration) ───────────────────────────────┘
  8a. Testes de integração
  8b. Verificação Docker
  8c. Verificação migração
```

---

## Checkpoints

### Checkpoint 1: Após Fase 1
- [ ] Todos os domain tests passam
- [ ] Migration aplica sem erros
- [ ] Model PolicyAlert criado

### Checkpoint 2: Após Fase 4
- [ ] Activities registadas no worker
- [ ] Workflow registrado no registry
- [ ] Schedule definido

### Checkpoint 3: Após Fase 6
- [ ] Frontend builda sem erros
- [ ] Todas as tabs funcionam
- [ ] Sources page funcional

### Checkpoint 4: Após Fase 8
- [ ] Testes de integração passam
- [ ] Docker compose funciona
- [ ] Fluxo completo testado
