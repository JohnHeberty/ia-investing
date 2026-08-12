# Plano Detalhado: Ativar e Corrigir Candidate Intelligence

**Data:** 2026-08-11
**Objetivo:** Garantir que o sistema Candidate Intelligence funcione end-to-end.
**Status:** Aguardando aprovação do usuário antes de implementar.

---

## Sumário Executivo

**8 tasks** em 3 fases, estimativa total: ~4-6h de trabalho.

| Fase | Tasks | Severidade | Escopo |
|------|-------|------------|--------|
| 1 — Críticos | 2 | CRITICAL | Frontend URLs + Temporal leak |
| 2 — Medium | 3 | MEDIUM | DB pool duplicado + assert + readiness |
| 3 — Melhorias | 3 | LOW | String matching + error handling + UI gaps |

---

## Infraestrutura Disponível

O stack de desenvolvimento está **completo e funcional**:

| Serviço | Porta | Status | Uso no Candidate Intelligence |
|---------|-------|--------|-------------------------------|
| PostgreSQL17 | 5432 | `pg_isready` health check | Banco principal (7 tabelas CI) |
| MinIO | 9000/9001 | `curl /minio/health/live` | Armazenamento de documentos brutos |
| Temporal | 7233 | `temporal operator cluster health` | Orchestration de 5 workflows |
| LiteLLM | 4000 | `curl /health/liveliness` | LLM gateway (3 virtual keys) |
| API | 8000 | `curl /api/v1/health` | 159 endpoints |
| Web | 3000 | — | Next.js frontend |
| 3 Workers | — | — | research-agents (28 activities) |

**Para testes de integração**, execute:
```bash
docker compose --profile dev up -d
# ou para testes minimizados:
docker compose -f docker/compose.yml -f docker/compose.test.yml --profile test up
```

**Ordem de startup** (respeitada pelo compose):
```
postgres → minio-init, temporal, migrate, litellm → api → web, workers
```

---

## Fase 1: Bugs Críticos

### Task CI-1: Corrigir URL mismatch no frontend (CRITICAL)

**Problema:** O frontend chama paths errados para promote/dismiss de exploration suggestions, resultando em 404.

**Backend real (correto):**
```
POST /api/v1/exploration-runs/suggestions/{id}/promotion
POST /api/v1/exploration-runs/suggestions/{id}/dismissal
```

**Frontend atual (errado):**
```
POST /api/v1/exploration-suggestions/{id}/promote
POST /api/v1/exploration-suggestions/{id}/dismiss
```

**Arquivo:** `web/src/lib/candidate-api.ts`

**Mudanças necessárias:**

1. **Função `promoteExplorationSuggestion`** (linha ~85):
   - De: `api(\`/exploration-suggestions/${id}/promote\`, ...)`
   - Para: `api(\`/exploration-runs/suggestions/${id}/promotion\`, ...)`

2. **Função `dismissExplorationSuggestion`** (linha ~92):
   - De: `api(\`/exploration-suggestions/${id}/dismiss\`, { method: "POST", body: JSON.stringify({ reason }) })`
   - Para: `api(\`/exploration-runs/suggestions/${id}/dismissal\`, { method: "POST", body: JSON.stringify({ reason }) })`

**Acceptance Criteria:**
- [ ] Paths no frontend batem com paths do backend
- [ ] `cd web && npm run build` passa sem erros
- [ ] Testes unitários do frontend passam

**Verificação:**
```bash
cd web && npm run build
cd web && npm test
```

**Escopo:** XS (1 arquivo, 2 linhas alteradas)
**Risco:** Baixo — mudança de string literal

---

### Task CI-2: Fechar Temporal client (CRITICAL)

**Problema:** `create_exploration_schedule` cria um `Client` Temporal via `await Client.connect(...)` mas nunca chama `client.close()`, causando leak de canais gRPC.

**Arquivo:** `src/apps/api/routes/investment_candidates.py`

**Código atual (linhas 636-656):**
```python
client = await Client.connect(settings.temporal.address)
# ... usa client ...
# nunca fecha
```

**Mudança necessária:**
```python
client = await Client.connect(settings.temporal.address)
try:
    # ... código existente ...
finally:
    await client.close()
```

**Acceptance Criteria:**
- [ ] `client.close()` é chamado em finally block
- [ ] Não há leak de conexões em chamadas repetidas
- [ ] Testes passam

**Verificação:**
```bash
uv run pytest tests/unit/test_rebalance_routes.py -q
```

**Escopo:** Small (1 arquivo, ~5 linhas adicionadas)
**Risco:** Baixo — pattern padrão de resource management

---

## Fase 2: Bugs Medium

### Task CI-3: Remover DatabaseRuntime.create() duplicado

**Problema:** `sync_pipeline.py` chama `DatabaseRuntime.create()` duas vezes consecutivas (linhas 146-152), criando 2 pools de conexão. A primeira chamada é imediatamente descartada.

**Arquivo:** `src/ia_investing/candidate_intelligence/sync_pipeline.py`

**Código atual (linhas 146-152):**
```python
db = DatabaseRuntime.create(settings.database.url)  # linhas 146-148
# ...
db = DatabaseRuntime.create(settings.database.url)  # linhas 150-152 (duplicado)
```

**Mudança:** Remover a primeira chamada duplicada (linhas 146-148 ou 150-152, dependendo do contexto).

**Acceptance Criteria:**
- [ ] Apenas uma chamada `DatabaseRuntime.create()` existe na função
- [ ] Pipeline funciona corretamente
- [ ] Testes passam

**Verificação:**
```bash
uv run pytest tests/unit/ -q
```

**Escopo:** XS (1 arquivo, remover 3 linhas)
**Risco:** Baixo — remoção de código morto

---

### Task CI-4: Substituir assert por LookupError

**Problema:** `promote_exploration_suggestion` usa `assert existing is not None` (linha 666) que crasha com `AssertionError` se o candidato foi deletado após a promoção.

**Arquivo:** `src/apps/api/routes/investment_candidates.py`

**Código atual (linha 666):**
```python
assert existing is not None
```

**Mudança:**
```python
if existing is None:
    raise LookupError("promoted candidate not found")
```

**Acceptance Criteria:**
- [ ] `assert` substituído por `if ... raise LookupError`
- [ ] Teste de margem para candidato deletado
- [ ] Testes passam

**Verificação:**
```bash
uv run pytest tests/unit/ -q
```

**Escopo:** XS (1 arquivo, 3 linhas)
**Risco:** Baixo — correção de crash

---

### Task CI-5: Unificar readiness computation

**Problema:** A rota `get_candidate` calcula readiness inline (linhas 286-350) enquanto o domain `ReadinessEvaluator` faz o mesmo de forma diferente. Isso gera scores inconsistentes.

**Arquivos:**
- `src/apps/api/routes/investment_candidates.py` (linhas 286-350)
- `src/ia_investing/candidate_intelligence/readiness.py` (`ReadinessEvaluator.evaluate()`)

**Análise comparativa:**

| Aspecto | Rota (inline) | Domain (ReadinessEvaluator) |
|---------|---------------|----------------------------|
| Source requirements | `DEFAULT_SOURCE_REQUIREMENTS` weights | 8 dimensões com pesos |
| Gap blockers | Não inclui | Inclui gap-based blockers |
| Stage ranking | Simples | Mais completo |
| Score range | 0-100 | 0-100 |

**Mudança:** Substituir o cálculo inline da rota por uma chamada ao `ReadinessEvaluator`:

```python
from ia_investing.candidate_intelligence.readiness import ReadinessEvaluator

evaluator = ReadinessEvaluator()
readiness = evaluator.evaluate(
    sources=detail.sources,
    gaps=detail.gaps,
    runs=detail.runs,
)
```

**Acceptance Criteria:**
- [ ] Rota usa `ReadinessEvaluator` do domain
- [ ] Score é consistente entre API e domain
- [ ] Testes passam

**Verificação:**
```bash
uv run pytest tests/unit/ -q
```

**Escopo:** Small (2 arquivos)
**Risco:** Médio — score pode mudar, verificar se frontend tolera

---

## Fase 3: Melhorias Low

### Task CI-6: Typed exception para schedule duplicado

**Problema:** Detecção de schedule duplicado usa string matching frágil (linhas 661-663):
```python
if "already" in exc_str or "schedule already" in exc_str:
```

**Arquivo:** `src/apps/api/routes/investment_candidates.py`

**Mudança:** Usar `temporalio.exceptions.RPCError` com status `ALREADY_EXISTS`:
```python
from temporalio.exceptions import RPCError

try:
    await client.create_schedule(schedule_id, schedule)
except RPCError as exc:
    if exc.status == "ALREADY_EXISTS":
        raise HTTPException(status_code=409, detail="exploration schedule already exists") from exc
    raise HTTPException(status_code=503, detail="could not create Temporal exploration schedule") from exc
```

**Acceptance Criteria:**
- [ ] Exceção tipada do Temporal é capturada
- [ ] Não depende de mensagem de erro
- [ ] Testes passam

**Verificação:**
```bash
uv run pytest tests/unit/ -q
```

**Escopo:** Small (1 arquivo)
**Risco:** Baixo — exception type já é usado em outros places do codebase

---

### Task CI-7: Adicionar error handling ao pipeline endpoint

**Problema:** `run_candidate_pipeline_endpoint` não trata falhas de infraestrutura, propagando 500 raw.

**Arquivo:** `src/apps/api/routes/investment_candidates.py`

**Mudança:** Adicionar try/except para falhas de infra:
```python
try:
    result = await run_candidate_pipeline(candidate_id=candidate_id, ...)
except ConnectionError as exc:
    raise HTTPException(status_code=503, detail=f"infrastructure error: {exc}") from exc
except Exception as exc:
    logger.exception("pipeline failed for candidate %s", candidate_id)
    raise HTTPException(status_code=422, detail=f"pipeline execution failed: {exc}") from exc
```

**Acceptance Criteria:**
- [ ] Falhas de infra retornam 503 com mensagem clara
- [ ] Falhas de pipeline retornam 422 com detalhes
- [ ] Logs de erro são gerados
- [ ] Testes passam

**Verificação:**
```bash
uv run pytest tests/unit/ -q
```

**Escopo:** Small (1 arquivo)
**Risco:** Baixo — error handling aditivo

---

### Task CI-8: UI de gap resolution (inline expandable card)

**Problema:** Backend suporta `POST /{id}/gaps/{gap_id}/resolution` mas frontend não tem formulário para resolver gaps.

**Decisão de Design: Inline (não modal)**

**Justificativa:**
1. **Contexto preservado** — usuário vê título, descrição, nível e ação solicitada enquanto escreve notas
2. **Padrão existente** — `PositionsTab.tsx` já usa inline editing para posições
3. **Formulário simples** — apenas 1 campo obrigatório (`notes`, 3-4000 chars)
4. **UX fluida** — resolve um gap, vê o próximo imediatamente
5. **Toast feedback** — `sonner` já instalado para notificações

**Arquivos a modificar:**

#### 1. `web/src/lib/candidate-api.ts`
Adicionar interface enriquecida e função de resolve:

```typescript
// Expandir CandidateGap
export interface CandidateGap {
  id: string;
  title: string;
  description: string;
  level: string;
  status: string;
  source_kind: string | null;
  requested_user_action: string;
  // NOVOS CAMPOS:
  code: string;
  created_at: string;
  resolved_at: string | null;
  resolved_by: string | null;
  resolution_notes: string | null;
}

// Nova função
export function resolveCandidateGap(
  candidateId: string,
  gapId: string,
  etag: string,
  notes: string,
): Promise<CandidateGap> {
  return api<CandidateGap>(
    `/investment-candidates/${candidateId}/gaps/${gapId}/resolution`,
    {
      method: "POST",
      headers: { "If-Match": etag },
      body: JSON.stringify({ notes }),
    }
  );
}
```

#### 2. `web/src/app/opportunities/candidates/[id]/page.tsx`
Modificar a tab de gaps (linha ~166) para:

1. Adicionar state `editingGapId: string | null`
2. Em cada gap card, adicionar botão "Resolver" (apenas se `status === "open"`)
3. Ao clicar, expandir card com textarea + Save/Cancel
4. Save chama `resolveCandidateGap()`, mostra toast, recarrega detail
5. Para gaps resolvidos, mostrar `resolution_notes` + `resolved_by` + `resolved_at`

**Estrutura JSX proposta:**
```tsx
{detail.gaps.map((gap) => (
  <article key={gap.id} className={`${styles.gap} ${gap.status === "open" && gap.level === "blocking" ? styles.blocker : ""}`}>
    <div className={styles.gapHeader}>
      <strong>{gap.title}</strong>
      <span className="badge" data-tone={...}>{gap.status} · {gap.level}</span>
    </div>
    <p className="subtitle">{gap.description}</p>
    <p className="subtitle"><strong>Ação:</strong> {gap.requested_user_action}</p>

    {/* NOVO: Botão resolver */}
    {gap.status === "open" && editingGapId !== gap.id && (
      <button className="button" onClick={() => setEditingGapId(gap.id)}>
        Resolver
      </button>
    )}

    {/* NOVO: Formulário inline */}
    {editingGapId === gap.id && (
      <form onSubmit={handleResolve} className={styles.resolveForm}>
        <textarea
          className="form-input"
          value={resolveNotes}
          onChange={(e) => setResolveNotes(e.target.value)}
          placeholder="Notas de resolução (mínimo 3 caracteres)..."
          aria-required="true"
        />
        <div className={styles.resolveActions}>
          <button type="submit" className="button" disabled={resolveNotes.length < 3}>
            Salvar
          </button>
          <button type="button" className="button secondary" onClick={() => setEditingGapId(null)}>
            Cancelar
          </button>
        </div>
      </form>
    )}

    {/* NOVO: Info de resolução */}
    {gap.status === "resolved" && gap.resolution_notes && (
      <div className={styles.resolvedInfo}>
        <p className="subtitle"><strong>Resolvido por:</strong> {gap.resolved_by}</p>
        <p className="subtitle"><strong>Em:</strong> {gap.resolved_at}</p>
        <p className="subtitle"><strong>Notas:</strong> {gap.resolution_notes}</p>
      </div>
    )}
  </article>
))}
```

#### 3. `web/src/components/candidates/candidate-intelligence.module.css`
Adicionar estilos:
```css
.resolveForm {
  margin-top: 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.resolveActions {
  display: flex;
  gap: 8px;
}

.resolvedInfo {
  margin-top: 8px;
  padding: 8px;
  border-radius: 6px;
  background: var(--surface-1);
  opacity: 0.8;
}
```

**Acceptance Criteria:**
- [ ] Botão "Resolver" aparece em gaps com status "open"
- [ ] Formulário inline expande com textarea + Save/Cancel
- [ ] Save chama `resolveCandidateGap()` com ETag
- [ ] Toast de sucesso aparece após resolução
- [ ] Gaps resolvidos mostram notas, autor e data
- [ ] `cd web && npm run build` passa
- [ ] Acessibilidade: `aria-required`, `role="alert"` para erros

**Verificação:**
```bash
cd web && npm run build
# Teste manual: abrir candidato com gaps → resolver um gap → verificar status
```

**Escopo:** Medium (3 arquivos)
**Risco:** Médio — precisa de teste manual com infra rodando

---

## Checkpoints

### Checkpoint 1: Após Fase 1 (Críticos)
```bash
# Backend
uv run pytest tests/unit/ -q
uv run ruff check src/apps/api/routes/investment_candidates.py

# Frontend
cd web && npm run build
cd web && npm test
```
- [ ] 1271 testes passam
- [ ] Frontend builda sem erros
- [ ] URLs de promote/dismiss estão corretas
- [ ] Temporal client é fechado

### Checkpoint 2: Após Fase 2 (Medium)
```bash
uv run pytest tests/unit/ -q
```
- [ ] DatabaseRuntime.create() aparece apenas 1 vez
- [ ] Assert substituído por LookupError
- [ ] Readiness score usa ReadinessEvaluator

### Checkpoint 3: Após Fase 3 (Low)
```bash
uv run pytest tests/unit/ -q
cd web && npm run build
```
- [ ] RPCError usado para schedule duplicado
- [ ] Pipeline endpoint tem error handling
- [ ] Gap resolution UI funcional

### Checkpoint 4: Validação End-to-End (requer infra)
```bash
docker compose --profile dev up -d
# Aguardar todos os serviços ficarem healthy
# Testar fluxo completo:
# 1. Criar candidato via UI
# 2. Adicionar source
# 3. Resolver gaps
# 4. Rodar pipeline
# 5. Verificar decisão do committee
```

---

## Riscos e Mitigações

| Risco | Impacto | Probabilidade | Mitigação |
|-------|---------|---------------|-----------|
| Frontend build quebra após mudança de URL | Alto | Baixa | Testar `npm run build` após cada mudança |
| Readiness score muda após unificação | Médio | Alta | Comparar scores antes/depois; frontend já tolera variações |
| Temporal exception type pode variar | Baixo | Baixa | `RPCError` é estável desde temporalio 1.25 |
| Gap resolution precisa de ETag válido | Médio | Média | Garantir que `get_candidate` retorna ETag |
| Inline form quebra layout em gaps longos | Baixo | Baixa | Usar CSS existente de `.resolveForm` |

---

## Ordem de Implementação Recomendada

1. **CI-1** (URL mismatch) — desbloqueia promote/dismiss imediatamente
2. **CI-2** (Temporal leak) — previne leak em produção
3. **CI-3** (DB pool duplicado) — limpeza simples
4. **CI-4** (assert → LookupError) — previne crash
5. **CI-6** (typed exception) — melhoria de robustez
6. **CI-7** (error handling) — melhoria de UX
7. **CI-5** (readiness unification) — requer cuidado
8. **CI-8** (gap resolution UI) — maior esforço, fazer por último

**Total estimado:** ~4-6h de trabalho

---

## Perguntas para o Usuário

1. **Infra:** O stack Docker está rodando? Precisa que eu suba?
2. **Prioridade:** Quer que eu comece pelos críticos (CI-1, CI-2) ou faz tudo de uma vez?
3. **Testes:** Quer que eu crie testes unitários novos para os bugs corrigidos?
