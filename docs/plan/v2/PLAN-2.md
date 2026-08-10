# Plano: Sistema de Notícias e Classificação de Impacto

> **Versão:** 2.0 — Pós-auditoria Tech Leader + Diretor de Market
> **Nota auditoria:** 5.8/10 → Meta: 8+/10

## Visão Geral

Sistema completo de notícias com **6 pilares** (expandido de 4):
1. **Cadastro de fontes RSS** (CRUD no frontend)
2. **Extração agendada** (Temporal schedule + RSS fetch)
3. **Entity Resolution** (LLM identifica ativos na notícia) ← **NOVO**
4. **Classificação de impacto via LLM** (desmock do `run_news_analyst`)
5. **Persistência de eventos e impactos** ← **NOVO**
6. **Dashboard + Alertas** (feed, timeline, impacto por ativo, alertas) ← **EXPANDIDO**

---

## 🎯 MVP vs Versão Completa

### MVP (Fase 1-2) — Entrega mínima para validação
- RSS fetch + armazenamento no DB
- Display no frontend (feed de notícias básico)
- **Sem LLM**, **sem impacto**, **sem alertas**
- **Objetivo:** Validar se o usuário quer ver notícias no dashboard

### V1 (Fase 3-4) — Análise por LLM
- Desmock `run_news_analyst` com LLM real
- Entity resolution (notícia → ativo)
- Persistência de eventos detectados

### V2 (Fase 5-6) — Impacto e Conexão
- Impacto por ativo (materialidade × direção)
- Conexão notícia × portfólio (qual carteira é afetada)
- Timeline de eventos

### V3 (Fase 7) — Alertas e Polish
- Alertas por materialidade threshold
- Desmock de filing analysis (CVM)
- Multi-idioma
- Fontes diversificadas

---

## 🔍 Diagnóstico Atual (atualizado pós-auditoria)

| Componente | Status | Gap Identificado |
|-----------|--------|-----------------|
| Conectores RSS | ⚠️ Implementado, NÃO conectado | Nunca é chamado por nenhum workflow |
| Modelos DB (6 tabelas) | ✅ Implementado | Nenhum código cria registros nessas tabelas |
| Schema NewsAnalysis | ⚠️ Implementado | **FALTA** campo `affected_issuers` |
| Prompt news_analyst | ⚠️ Implementado | **NÃO pede** identificação de ativos |
| Workflow AnalyzeNewsWorkflow | ⚠️ Mockado | Não persiste eventos/impactos |
| Activity `run_news_analyst` | ❌ Mockado | Retorna hardcoded neutro |
| Activity `update_event_log` | ❌ Mockado | Retorna `persisted: False` |
| Activity `create_entity_links` | ❌ **NÃO EXISTE** | Nenhum código cria `NewsEntityLink` |
| Activity `persist_event` | ❌ **NÃO EXISTE** | Nenhum código cria `DetectedEvent` |
| Activity `persist_impact` | ❌ **NÃO EXISTE** | Nenhum código cria `EventImpact` |
| Frontend de notícias | ❌ Não existe | Nenhum hook, rota ou componente |
| Schedule de extração | ❌ Não existe | Nenhum schedule configurado |
| Conexão notícia × portfólio | ❌ **NÃO EXISTE** | Impacto não cruza com posições |
| Sistema de alertas | ❌ **NÃO EXISTE** | Sem notificações de alto impacto |
| Análise de filings CVM | ❌ Mockado | `run_filing_analyst` retorna hardcoded |

---

## 🧩 O que o sistema de exploração autônoma já faz

O `AutonomousEquityExplorationWorkflow` é um agente **funcional** que:

1. **Screening SQL determinístico**: Query em `Instrument`, `Listing`, `Issuer`, `MarketBar`, `MarketQuote` — filtra por volume médio 30d e spread bid-ask
2. **Avaliação LLM**: Envia top 20 candidatos para agente `research_coordinator` — gera sugestões com rationale, sinais, riscos
3. **Score blended**: `llm_score * 0.4 + quant_score * 0.6` (volume, spread, financial facts, source coverage)
4. **Persiste sugestões** com expiração de 30 dias

**Não busca notícias nem parseia documentos** — trabalha apenas com dados já existentes no DB.

---

## 🏗️ Arquitetura do Sistema Proposto (atualizada)

```
┌─────────────────────────────────────────────────────────────┐
│                    FRONTEND (Next.js)                        │
│  ┌──────────┐  ┌──────────────┐  ┌────────────────────┐    │
│  │ /news    │  │ /news/sources│  │ /news/impact       │    │
│  │ Feed     │  │ Cadastro     │  │ Dashboard          │    │
│  │ de       │  │ de fontes    │  │ de impacto         │    │
│  │ notícias │  │ RSS          │  │ + Portfolio view   │    │
│  └──────────┘  └──────────────┘  └────────────────────┘    │
│         │              │                    │                │
│         └──────────────┼────────────────────┘                │
│                        │ bffFetch                            │
├────────────────────────┼────────────────────────────────────┤
│                    BACKEND (FastAPI)                          │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ /api/v1/news/*                                      │    │
│  │ sources CRUD · items list · events · impacts        │    │
│  │ stats · portfolio-impacts (NOVO)                    │    │
│  └──────────────────────┬──────────────────────────────┘    │
│                         │                                    │
│  ┌──────────────────────┴──────────────────────────────┐    │
│  │ NewsService                                         │    │
│  │ CRUD fontes · extração · entity resolution          │    │
│  │ persistência events/impacts · portfolio impact      │    │
│  └──────────────────────┬──────────────────────────────┘    │
│                         │                                    │
│  ┌──────────────────────┴──────────────────────────────┐    │
│  │ Temporal Workflows                                  │    │
│  │ ExtractAndAnalyzeNewsWorkflow                       │    │
│  │   ├── fetch_rss_feeds (activity)                    │    │
│  │   ├── run_news_analyst (LLM real)                   │    │
│  │   ├── create_entity_links (NOVO)                    │    │
│  │   ├── compare_with_active_theses                    │    │
│  │   ├── persist_event (NOVO)                          │    │
│  │   ├── persist_impact (NOVO)                         │    │
│  │   └── check_alert_threshold (NOVO)                  │    │
│  │                                                     │    │
│  │ AnalyzeFilingWorkflow (desmock)                     │    │
│  │   ├── run_filing_analyst (LLM real)                 │    │
│  │   └── update_filing_analysis                        │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ Temporal Schedules                                  │    │
│  │ news_extraction (configurable, default 2h)          │    │
│  └─────────────────────────────────────────────────────┘    │
├─────────────────────────────────────────────────────────────┤
│                    DATABASE (PostgreSQL)                      │
│  news_sources · news_items · news_entity_links              │
│  detected_events · event_impacts · event_duplicates         │
├─────────────────────────────────────────────────────────────┤
│                    CONECTORES                                 │
│  RSS: fetch_google_news_rss · fetch_reuters_rss             │
│  CVM: get_dfp · fca · cad (já funcionais)                  │
└─────────────────────────────────────────────────────────────┘
```

---

## 🔧 Backend — 10 Componentes (expandido de 7)

### 1. Serviço de Notícias (`src/ia_investing/application/news_service.py`) — NOVO

```python
class NewsService:
    def __init__(self, session: AsyncSession, organization_id: UUID): ...

    # Fontes
    async def list_sources(self, is_active: bool | None = None) -> list[NewsSource]
    async def create_source(self, name, url_pattern, source_type, trust_level) -> NewsSource
    async def update_source(self, source_id, **fields) -> NewsSource
    async def delete_source(self, source_id) -> None
    async def test_source(self, source_id) -> list[NewsArticle]

    # Itens
    async def list_items(self, source_id=None, sentiment=None, limit=50, offset=0) -> tuple[list[NewsItem], int]
    async def get_item(self, item_id) -> dict  # item + events + impacts + entity_links
    async def mark_processed(self, item_id) -> None

    # Entity Resolution (NOVO)
    async def create_entity_links(self, news_item_id, issuer_ids: list[str], relevance_scores: list[float]) -> list[NewsEntityLink]
    async def get_entity_links(self, news_item_id) -> list[NewsEntityLink]

    # Eventos e Impactos
    async def list_events(self, issuer_id=None, limit=50) -> list[DetectedEvent]
    async def get_event(self, event_id) -> dict  # event + impacts
    async def list_impacts(self, event_id=None, limit=50) -> list[EventImpact]
    async def persist_event(self, news_item_id, event_type, description, materiality_score, direction_hint, time_horizon, affected_metrics, issuer_ids) -> DetectedEvent
    async def persist_impact(self, event_id, thesis_id, impact_score, confidence, reasoning, thesis_effect) -> EventImpact

    # Portfolio Impact (NOVO)
    async def get_portfolio_impacts(self, limit=50) -> list[dict]:
        """Cruza impactos com posições dos portfólios."""
        # 1. Busca eventos recentes (últimos 7 dias)
        # 2. Para cada evento, busca issuer_id via news_entity_links
        # 3. Para cada issuer, busca posições nos portfólios
        # 4. Retorna: [{event, issuer, portfolio, position_weight, impact_score}]

    # Extração
    async def extract_news(self, source_ids: list[UUID] | None = None) -> int

    # Alertas (NOVO)
    async def check_alert_threshold(self, event: DetectedEvent, threshold: float = 0.5) -> bool:
        """Verifica se evento excede threshold de alerta."""
        return abs(event.materiality_score or 0) >= threshold

    # Stats
    async def get_stats(self) -> dict
```

### 2. Rotas API (`src/apps/api/routes/news.py`) — NOVO (~250 linhas)

| Método | Rota | Permissão | Descrição |
|--------|------|-----------|-----------|
| `GET` | `/api/v1/news/sources` | `news:read` | Lista fontes RSS |
| `POST` | `/api/v1/news/sources` | `news:manage` | Cria fonte |
| `PUT` | `/api/v1/news/sources/{id}` | `news:manage` | Atualiza fonte |
| `DELETE` | `/api/v1/news/sources/{id}` | `news:manage` | Remove fonte |
| `POST` | `/api/v1/news/sources/{id}/test` | `news:read` | Testa fonte (busca amostra) |
| `GET` | `/api/v1/news/items` | `news:read` | Lista notícias (filtros) |
| `GET` | `/api/v1/news/items/{id}` | `news:read` | Detalhe + evento + impacto + entity_links |
| `POST` | `/api/v1/news/extract` | `news:manage` | Dispara extração manual |
| `GET` | `/api/v1/news/events` | `news:read` | Lista eventos detectados |
| `GET` | `/api/v1/news/events/{id}` | `news:read` | Detalhe do evento + impactos |
| `GET` | `/api/v1/news/impacts` | `news:read` | Lista impactos |
| `GET` | `/api/v1/news/portfolio-impacts` | `news:read` | **NOVO** — Impacto × Portfólio |
| `GET` | `/api/v1/news/stats` | `news:read` | Métricas agregadas |

### 3. Activity de Extração RSS (`src/ia_investing/orchestration/activities/news_extraction.py`) — NOVO

```python
@activity.defn
async def fetch_rss_feeds(source_ids: list[str] | None = None) -> int:
    """Busca RSS de todas as fontes ativas, deduplica, salva no DB."""
    # 1. Query NewsSource where is_active=True (ou filtrar por source_ids)
    # 2. Para cada fonte: fetch_google_news_rss(url_pattern) ou fetch_reuters_rss(url_pattern)
    # 3. Deduplica por URL normalizada + title similarity
    # 4. Insere em news_items com is_processed=False
    # 5. Retorna count de itens novos

@activity.defn
async def get_unprocessed_items() -> list[dict]:
    """Retorna itens não processados para análise."""
    # Query NewsItem where is_processed=False ORDER BY retrieved_at
    # Retorna max 50 itens por ciclo
```

### 4. Activity de Entity Resolution (`news_extraction.py` adicional) — NOVO

```python
@activity.defn
async def create_entity_links(news_item_id: str, title: str, body: str) -> list[dict]:
    """Identifica ativos mencionados na notícia e cria vínculos."""
    # 1. Extrair tickers/cnpjs do texto (regex + LLM fallback)
    # 2. Buscar issuers no DB por ticker ou nome
    # 3. Calcular relevance_score (baseado em menções)
    # 4. Inserir em news_entity_links
    # 5. Retorna lista de {issuer_id, relevance_score}
```

### 5. Activity de Persistência (`news_extraction.py` adicional) — NOVO

```python
@activity.defn
async def persist_detected_event(
    news_item_id: str,
    event_type: str,
    description: str,
    materiality_score: float,
    direction_hint: str,
    time_horizon: str,
    affected_metrics: dict,
    issuer_ids: list[str],
) -> dict:
    """Persiste evento detectado no DB."""
    # 1. Inserir em detected_events
    # 2. Para cada issuer_id, atualizar news_entity_links se necessário
    # 3. Retorna {event_id: str, persisted: True}

@activity.defn
async def persist_event_impact(
    event_id: str,
    thesis_id: str | None,
    impact_score: float,
    confidence: float,
    reasoning: str,
    thesis_effect: str,
) -> dict:
    """Persiste impacto do evento no DB."""
    # 1. Inserir em event_impacts
    # 2. Retorna {impact_id: str, persisted: True}

@activity.defn
async def check_and_notify_alert(event_id: str, threshold: float = 0.5) -> bool:
    """Verifica threshold e dispara notificação se exceder."""
    # 1. Buscar detected_events por event_id
    # 2. Se abs(materiality_score) >= threshold:
    #    - Criar notificação via NotificationService
    #    - Log de alerta
    # 3. Retorna True se alerta disparado
```

### 6. Desmock `run_news_analyst` (`research_mock.py`) — ALTERAR

```python
@activity.defn(name="run_news_analyst")
async def run_news_analyst(news_item_id, title, body, url) -> NewsAnalysisV1:
    # 1. Carregar prompt de prompts/news_analyst/system.md
    # 2. Montar input: {title, body, url}
    # 3. Executar via AgentExecutionService.execute(
    #        agent_name="news_analyst",
    #        prompt_text=prompt,
    #        user_input=json.dumps({"title": title, "body": body, "url": url}),
    #        output_schema=NewsAnalysis,
    #    )
    # 4. Mapear output para NewsAnalysisV1 com affected_issuers
    # 5. Retornar NewsAnalysisV1 com dados reais
```

### 7. Desmock `compare_with_active_theses` (`research_mock.py`) — ALTERAR

```python
@activity.defn(name="compare_with_active_theses")
async def compare_with_active_theses(analyst_output: dict, issuer_ids: list[str]) -> list[dict]:
    """Compara análise com teses ativas dos emissores."""
    # 1. Para cada issuer_id, buscar investment_theses ativas
    # 2. Para cada tese, comparar com analyst_output (event_type, direction)
    # 3. Calcular thesis_effect: strengthen/weaken/no_change
    # 4. Retornar [{issuer_id, thesis_id, thesis_effect, reasoning}]
```

### 8. Desmock `update_event_log` (`research_mock.py`) — ALTERAR

```python
@activity.defn(name="update_event_log")
async def update_event_log(event_data: dict) -> dict:
    """Persiste log do evento analisado."""
    # 1. Usar persist_detected_event activity
    # 2. Retornar {event_id, persisted: True}
```

### 9. Workflow de Extração (`src/workflows/_extract_news.py`) — NOVO

```python
@workflow.defn
class ExtractAndAnalyzeNewsWorkflow:
    @workflow.run
    async def run(self, source_ids: list[str] | None = None) -> dict:
        # 1. Buscar RSS feeds
        count = await workflow.execute_activity(
            "fetch_rss_feeds", source_ids,
            start_to_close_timeout=timedelta(minutes=5),
        )

        # 2. Buscar itens não processados
        unprocessed = await workflow.execute_activity(
            "get_unprocessed_items",
            start_to_close_timeout=timedelta(seconds=30),
        )

        # 3. Para cada notícia, analisar com LLM
        analyzed = 0
        events_created = 0
        alerts_triggered = 0

        for item in unprocessed:
            try:
                # 3a. Análise LLM
                analyst_output = await workflow.execute_activity(
                    "run_news_analyst",
                    item["news_item_id"], item["title"], item["body"], item["url"],
                    start_to_close_timeout=timedelta(seconds=120),
                )

                # 3b. Entity Resolution
                entity_links = await workflow.execute_activity(
                    "create_entity_links",
                    item["news_item_id"], item["title"], item["body"],
                    start_to_close_timeout=timedelta(seconds=30),
                )

                # 3c. Comparar com teses
                issuer_ids = [link["issuer_id"] for link in entity_links]
                thesis_comparisons = await workflow.execute_activity(
                    "compare_with_active_theses",
                    analyst_output, issuer_ids,
                    start_to_close_timeout=timedelta(seconds=60),
                )

                # 3d. Persistir evento
                event = await workflow.execute_activity(
                    "persist_detected_event",
                    item["news_item_id"],
                    analyst_output["event_type"],
                    analyst_output["description"],
                    analyst_output["materiality_score"],
                    analyst_output["direction_hint"],
                    analyst_output["time_horizon"],
                    analyst_output["affected_metrics"],
                    issuer_ids,
                    start_to_close_timeout=timedelta(seconds=30),
                )

                # 3e. Persistir impactos
                for comparison in thesis_comparisons:
                    await workflow.execute_activity(
                        "persist_event_impact",
                        event["event_id"],
                        comparison.get("thesis_id"),
                        analyst_output["materiality_score"],
                        analyst_output.get("confidence", 0.5),
                        comparison.get("reasoning", ""),
                        comparison["thesis_effect"],
                        start_to_close_timeout=timedelta(seconds=30),
                    )

                # 3f. Verificar alertas
                alert = await workflow.execute_activity(
                    "check_and_notify_alert",
                    event["event_id"],
                    0.5,  # threshold
                    start_to_close_timeout=timedelta(seconds=10),
                )

                analyzed += 1
                events_created += 1
                if alert:
                    alerts_triggered += 1

            except Exception:
                # 3g. Log erro e continua (não falha o ciclo todo)
                continue

        return {
            "new_items": count,
            "analyzed": analyzed,
            "events_created": events_created,
            "alerts_triggered": alerts_triggered,
        }
```

### 10. Schedule no Temporal (`temporal_schedules.py`) — ALTERAR

```python
def news_extraction_schedule_definition(
    interval_minutes: int = 120,
) -> ScheduleDefinition:
    return ScheduleDefinition(
        schedule_id="news-extraction",
        schedule=Schedule(
            spec=ScheduleSpec(
                intervals=[ScheduleIntervalSpec(
                    every=timedelta(minutes=interval_minutes),
                )],
            ),
            action=ScheduleActionStartWorkflow(
                workflow_type=ExtractAndAnalyzeNewsWorkflow,
                task_queue="research-agents",
            ),
            state=ScheduleState(paused=False),
        ),
    )
```

### 11. Registro (`app_factory.py` + `activities/__init__.py`) — ALTERAR

- Adicionar `news.router` ao `_AUTH_ROUTERS`
- Criar `NEWS_ACTIVITIES` tuple com todas as activities de news
- Adicionar `NEWS_ACTIVITIES` ao registro de activities
- Re-export `ExtractAndAnalyzeNewsWorkflow` em `orchestration/workflows.py`

### 12. Atualizar Schema `NewsAnalysis` (`schemas/_news.py`) — ALTERAR

```python
class NewsAnalysis(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    verdict: Literal["positive", "negative", "neutral", "mixed"]
    confidence: float = Field(ge=0.0, le=1.0)
    summary_pt: str
    materiality_score: float = Field(ge=-1.0, le=1.0)
    thesis_effect: Literal["strengthen", "weaken", "no_change"]
    event_type: str
    affected_metrics: list[str]
    time_horizon: str
    key_claims: list[str]
    affected_issuers: list[str] = Field(default_factory=list)  # NOVO
```

### 13. Atualizar Prompt `news_analyst/system.md` — ALTERAR

Adicionar seção "Identificação de Emissores":
```
## Identificação de Emissores
Identifique todas as empresas/ativos mencionados na notícia.
Para cada um, extraia:
- Ticker (ex: PETR4, VALE3)
- Nome da empresa
- CNPJ (se mencionado)
Retorne no campo `affected_issuers` usando o formato: ["TICKER1", "TICKER2"]
```

---

## 🎨 Frontend — 3 Páginas + 1 Hook + Navegação

### 1. Hook `use-news.ts` — NOVO (~200 linhas)

```typescript
// Queries
useNewsSources()                    // GET /api/v1/news/sources
useNewsItems(params)                // GET /api/v1/news/items?source_id=&sentiment=&limit=&offset=
useNewsItem(id)                     // GET /api/v1/news/items/{id}
useNewsEvents(params)               // GET /api/v1/news/events?issuer_id=&limit=
useNewsImpacts(params)              // GET /api/v1/news/impacts?event_id=&limit=
useNewsPortfolioImpacts()           // GET /api/v1/news/portfolio-impacts (NOVO)
useNewsStats()                      // GET /api/v1/news/stats

// Mutations
useCreateNewsSource()               // POST /api/v1/news/sources
useUpdateNewsSource()               // PUT /api/v1/news/sources/{id}
useDeleteNewsSource()               // DELETE /api/v1/news/sources/{id}
useTestNewsSource()                 // POST /api/v1/news/sources/{id}/test
useTriggerExtraction()              // POST /api/v1/news/extract
```

### 2. Página: Feed de Notícias (`/news/page.tsx`) — NOVO

```
┌─────────────────────────────────────────────────────┐
│ Notícias  [Filtros: Fonte ▼ | Sentimento ▼ | Data ▼]│
├─────────────────────────────────────────────────────┤
│ 📊 127 notícias · 23 eventos · 8 impactos · 2 alertas│
├─────────────────────────────────────────────────────┤
│ [🔴 ALERTA] Petrobras anuncia dividendos...          │
│   Google News · há 2h · Materialidade: +0.8         │
│   Afeta: PETR4 (peso 12% na Long Only)              │
│ [badge: NEGATIVO] Vale enfrenta multa ambiental...   │
│   Reuters · há 3h · Materialidade: -0.4             │
│ [badge: NEUTRO] Banco Central mantém Selic...        │
│   Google News · há 4h · Materialidade: 0.0          │
├─────────────────────────────────────────────────────┤
│ [Carregar mais]                                       │
└─────────────────────────────────────────────────────┘
```

**Componentes:**
- `page-head`: título "Notícias" + botão "Extrair agora"
- Filtros: select de fonte, select de sentimento, date range
- Métricas: 4 cards `grid-4` (total, eventos, impactos, **alertas**)
- Tabela: badge sentimento (com ícone de alerta se materialidade > threshold), título, fonte, data, status
- Drawer/modal ao clicar: corpo da notícia, evento detectado, impacto, **ativos afetados com peso no portfólio**

### 3. Página: Cadastro de Fontes (`/news/sources/page.tsx`) — NOVO

```
┌─────────────────────────────────────────────────────┐
│ Fontes de Notícias                    [ + Adicionar ]│
├─────────────────────────────────────────────────────┤
│ Nome          | Tipo      | Confiança | Status | Ações│
│───────────────┼───────────┼───────────┼────────┼─────│
│ Google News   | RSS       | ★★★★☆    | Ativo  | ✏️ 🗑️│
│ Reuters       | RSS       | ★★★★★    | Ativo  | ✏️ 🗑️│
│ BCB           | RSS       | ★★★★★    | Ativo  | ✏️ 🗑️│
│ Portal XYZ    | RSS       | ★★☆☆☆    | Ativo  | ✏️ 🗑️│
├─────────────────────────────────────────────────────┤
│ Última extração: há 2h · 47 itens novos              │
│ Intervalo: [2h ▼] · [Extrair agora]                  │
└─────────────────────────────────────────────────────┘
```

**Componentes:**
- `page-head`: título "Fontes de Notícias" + botão "+ Adicionar"
- Tabela com: nome, tipo RSS, nível de confiança (estrelas), status (toggle), ações (editar, excluir, testar)
- Modal de cadastro: nome, URL pattern, tipo (Google News/Reuters/Custom), confiança (1-5)
- Botão "Testar" que busca amostra e mostra preview em modal
- Footer: intervalo configurável + "Extrair agora"

### 4. Página: Dashboard de Impacto (`/news/impact/page.tsx`) — NOVO

```
┌─────────────────────────────────────────────────────┐
│ Impacto de Notícias                                   │
├──────────┬──────────┬──────────┬──────────┤          │
│ 127      │ 23       │ 8        │ 3        │          │
│ Notícias │ Eventos  │ Impactos │ Portfólios│          │
│          │          │          │ Afetados  │          │
├──────────┴──────────┴──────────┴──────────┤          │
│ Timeline de Eventos Recentes                           │
│ ● 10:30  Petrobras — resultado financeiro (+0.7)      │
│   Afeta: Long Only (12%), Paper (8%)                  │
│ ● 09:15  Vale — multa ambiental (-0.4)                │
│   Afeta: Long Only (5%)                               │
│ ● 08:00  BC — Selic mantida (0.0)                     │
│   Sem impacto em posições atuais                      │
├─────────────────────────────────────────────────────┤
│ Impacto por Ativo (com peso no portfólio)              │
│ PETR4  ████████████ +0.5  (Long Only: 12%, Paper: 8%)│
│ VALE3  ██████░░░░░░ -0.2  (Long Only: 5%)             │
│ ITUB4  ████░░░░░░░░ +0.1  (Long Only: 8%)             │
├─────────────────────────────────────────────────────┤
│ [Ver detalhes de cada ativo →]                         │
└─────────────────────────────────────────────────────┘
```

**Componentes:**
- `page-head`: título "Impacto de Notícias"
- Métricas: 4 cards `grid-4` (notícias, eventos, impactos, **portfólios afetados**)
- Timeline: lista cronológica de eventos com badge de direção + **portfólios afetados**
- Barras de impacto por ativo: `.exposure-bar` com cor por sentimento + **peso no portfólio**

### 5. Navegação (`app-shell.tsx`) — ALTERAR

Adicionar grupo "Notícias" na sidebar:

```typescript
const news: NavItem[] = [
  ["/news", "Feed", Newspaper, "news:read"],
  ["/news/sources", "Fontes", Rss, "news:read"],
  ["/news/impact", "Impacto", TrendingUp, "news:read"],
];
```

---

## 📁 Arquivos a Criar/Alterar

### Novos (9 arquivos)

| Arquivo | Linhas | Descrição |
|---------|--------|-----------|
| `src/ia_investing/application/news_service.py` | ~350 | Service CRUD + entity resolution + persistência + portfolio impact |
| `src/apps/api/routes/news.py` | ~250 | 12 endpoints |
| `src/ia_investing/orchestration/activities/news_extraction.py` | ~150 | Activities: fetch_rss, get_unprocessed, create_entity_links, persist_event, persist_impact, check_alert |
| `src/workflows/_extract_news.py` | ~120 | Workflow extração+análise+persistência+alertas |
| `web/src/hooks/use-news.ts` | ~200 | 11 hooks |
| `web/src/app/news/page.tsx` | ~200 | Feed de notícias |
| `web/src/app/news/sources/page.tsx` | ~180 | Cadastro de fontes |
| `web/src/app/news/impact/page.tsx` | ~200 | Dashboard de impacto |
| `tests/unit/test_news_service.py` | ~250 | Testes do service |

### Alterados (9 arquivos)

| Arquivo | Mudança |
|---------|---------|
| `src/ia_investing/orchestration/activities/research_mock.py` | Desmock `run_news_analyst`, `compare_with_active_theses`, `update_event_log` (~80 linhas) |
| `src/schemas/_news.py` | Adicionar `affected_issuers` ao schema (~5 linhas) |
| `prompts/news_analyst/system.md` | Adicionar seção "Identificação de Emissores" (~15 linhas) |
| `src/apps/scheduler/temporal_schedules.py` | Adicionar `news_extraction_schedule_definition` (~30 linhas) |
| `src/apps/api/app_factory.py` | Registrar `news.router` (~2 linhas) |
| `src/components/app-shell.tsx` | Adicionar nav items (~10 linhas) |
| `src/ia_investing/orchestration/activities/__init__.py` | Criar `NEWS_ACTIVITIES` tuple (~5 linhas) |
| `src/ia_investing/orchestration/workflows.py` | Re-export workflow (~2 linhas) |
| `tests/unit/test_news_routes.py` | ~150 linhas |

---

## 📊 Estimativas (atualizadas)

| Componente | Linhas | Prioridade | Fase |
|-----------|--------|-----------|------|
| **MVP** | | | |
| `news_service.py` (CRUD básico) | ~150 | 🔴 Alta | 1 |
| `routes/news.py` (CRUD + items) | ~150 | 🔴 Alta | 1 |
| `news_extraction.py` (fetch_rss + get_unprocessed) | ~80 | 🔴 Alta | 1 |
| `_extract_news.py` (workflow básico) | ~60 | 🔴 Alta | 1 |
| `use-news.ts` (queries básicas) | ~100 | 🟡 Média | 1 |
| `/news/page.tsx` (feed básico) | ~150 | 🟡 Média | 1 |
| `/news/sources/page.tsx` | ~180 | 🟡 Média | 1 |
| **V1** | | | |
| Desmock `run_news_analyst` | ~40 | 🔴 Alta | 2 |
| Desmock `compare_with_active_theses` | ~30 | 🔴 Alta | 2 |
| `create_entity_links` activity | ~60 | 🔴 Alta | 2 |
| `persist_event` + `persist_impact` activities | ~80 | 🔴 Alta | 2 |
| Schema + prompt update | ~20 | 🟡 Média | 2 |
| **V2** | | | |
| `persist_event` + `persist_impact` workflow steps | ~40 | 🔴 Alta | 3 |
| `/news/impact/page.tsx` (dashboard completo) | ~200 | 🟡 Média | 3 |
| `get_portfolio_impacts` service method | ~50 | 🟡 Média | 3 |
| `portfolio-impacts` endpoint | ~30 | 🟡 Média | 3 |
| **V3** | | | |
| Alertas (`check_and_notify_alert`) | ~40 | 🟡 Média | 4 |
| Desmock `run_filing_analyst` | ~40 | 🟡 Média | 4 |
| `temporal_schedules.py` | ~30 | 🟢 Baixa | 4 |
| `app-shell.tsx` nav | ~10 | 🟢 Baixa | 4 |
| Testes | ~400 | 🟡 Média | 4 |
| **Total** | **~2,100** | | |

---

## 🚀 Ordem de Implementação (reordenada)

### Fase 1 — MVP (Validação rápida)
1. `news_service.py` — CRUD básico (fontes + itens)
2. `routes/news.py` — CRUD endpoints + list items
3. `news_extraction.py` — `fetch_rss_feeds` + `get_unprocessed_items`
4. `_extract_news.py` — Workflow básico (fetch + mark processed)
5. `use-news.ts` — Queries básicas
6. `/news/sources/page.tsx` — Cadastro de fontes
7. `/news/page.tsx` — Feed de notícias básico
8. `activities/__init__.py` + `workflows.py` — Registro
9. `app_factory.py` — Registro de rota
10. **Validar com usuário**

### Fase 2 — Entity Resolution + LLM
11. Desmock `run_news_analyst` (LLM real)
12. Desmock `compare_with_active_theses`
13. `create_entity_links` activity
14. Schema update (`affected_issuers`)
15. Prompt update (identificação de emissores)
16. `test_news_service.py`

### Fase 3 — Persistência + Impacto
17. `persist_event` + `persist_impact` activities
18. Workflow update (adicionar steps de persistência)
19. `/news/impact/page.tsx` — Dashboard completo
20. `get_portfolio_impacts` service method
21. `portfolio-impacts` endpoint

### Fase 4 — Alertas + Polish
22. `check_and_notify_alert` activity
23. Desmock `run_filing_analyst` (CVM)
24. `temporal_schedules.py` — Schedule
25. `app-shell.tsx` — Navegação
26. `test_news_routes.py`
27. Commit + push

---

## 🎯 Critérios de Aceite (atualizados)

### MVP
- [ ] Fontes RSS podem ser cadastradas, editadas e removidas pelo frontend
- [ ] Extração RSS pode ser disparada manualmente
- [ ] Notícias são extraídas, deduplicadas e salvas no DB
- [ ] Feed de notícias mostra lista com filtros básicos
- [ ] Todas as páginas existentes continuam funcionando

### V1
- [ ] Cada notícia nova é analisada por LLM (classificação de evento, materialidade, direção)
- [ ] Ativos mencionados na notícia são identificados (entity resolution)
- [ ] Eventos detectados são vinculados a ativos (issuers)
- [ ] Análise é comparada com teses ativas

### V2
- [ ] Eventos e impactos são persistidos no DB
- [ ] Dashboard de impacto mostra timeline e barras por ativo
- [ ] Impacto é cruzado com posições dos portfólios
- [ ] Investor vê "Este ativo está em X carteiras com peso Y%"

### V3
- [ ] Alertas são disparados quando materialidade > threshold
- [ ] Filings da CVM são analisados por LLM (desmock)
- [ ] Schedule de extração roda automaticamente
- [ ] Navegação inclui grupo "Notícias" na sidebar
- [ ] Todos os testes passam (pytest + tsc)
- [ ] `prefers-reduced-motion` funciona nas animações
