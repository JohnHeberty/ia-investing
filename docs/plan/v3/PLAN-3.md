# PLAN-3 — Correção do Sistema de Schedules

**Data:** 2026-08-03
**Status:** ✅ CONCLUÍDO

---

## Contexto

O PLAN-3 original (39 itens) resolveu backend, validação e gravação de histórico (~90% feito). Esta fase 2 aborda os problemas de integração frontend-backend, lifecycle dos schedules, e UX que foram identificados na revisão completa.

---

## P0 — Crítico (quebra funcional)

### 1. Reconcile DELETA schedules de equity-exploration ✅

- **Onde:** `src/apps/scheduler/temporal_schedules.py:271-283` (`reconcile_schedules()`)
- **Problema:** `reconcile_schedules()` cria lista `known_ids` apenas com definitions locais. Depois lista TODOS os schedules no Temporal e deleta qualquer um não presente. Schedules `equity-exploration-*` são criados via API mas NÃO estão nas definitions → toda reconcile os deleta.
- **Correção:** Adicionar `preserve_prefixes: list[str] = ["equity-exploration-"]` ao `reconcile_schedules()`. Antes de deletar, verificar se o schedule começa com algum prefixo preservado.

### 2. Botão "Configurar schedules padrão" some após primeira execução ✅

- **Onde:** `web/src/app/schedules/page.tsx:590-610`
- **Problema:** Botão de reconcile só renderiza quando `count === 0`. Depois que existem schedules, desaparece. Impossível re-executar reconcile da UI.
- **Correção:** Adicionar botão "Reconciliar" na toolbar da página (visível sempre que há schedules). Usar `handleReconcile` já existente. Mostrar resultado em banner.

### 3. Botão de DELETE nunca aparece ✅

- **Onde:** `src/apps/api/routes/schedules.py:56` + `web/src/app/schedules/page.tsx:228`
- **Problema:** `_enrich_schedule()` marca `is_default=True` para qualquer schedule cujo ID começa com prefixo de `SCHEDULE_META`. TODOS os schedules conhecidos têm esses prefixos → `is_default` sempre `True` → `{!schedule.is_default && <Trash2/>}` NUNCA renderiza.
- **Correção:** Inverter a lógica: mostrar DELETE para TODOS os schedules. O reconcile recria schedules deletados. Quem criou via API pode deletar.

---

## P1 — Importante (falta funcionalidade)

### 4. Não mostra workflow nem task queue ✅

- **Onde:** `web/src/app/schedules/page.tsx` (ScheduleRow)
- **Problema:** Usuário vê "Coleta de noticias RSS" mas não sabe que é `ExtractNewsWorkflow` na fila `research-agents`.
- **Correção:** Adicionar coluna "Workflow" na tabela. Buscar `action.workflow` do detail endpoint ou mapear via `SCHEDULE_META`.

### 5. Não mostra última execução ✅

- **Onde:** `web/src/app/schedules/page.tsx` (ScheduleRow)
- **Problema:** Mostra "Próxima execução" mas não "Última execução".
- **Correção:** Adicionar coluna "Última execução" buscando do `schedule_run_history` (endpoint já existe).

### 6. Não mostra taxa de sucesso/falha ✅

- **Onde:** `web/src/app/schedules/page.tsx` (ScheduleRow/RunsPanel)
- **Problema:** Sem visão geral de "quantos schedules estão falhando".
- **Correção:** Badge indicativo na linha: "✓ 12 execuções" ou "✗ 3 falhas" usando dados do `schedule_run_history`.

### 7. Se DB cai durante reconcile, schedules de news-collection são deletados ✅

- **Onde:** `src/apps/scheduler/temporal_schedules.py:333-334`
- **Problema:** `except Exception` captura falha da query de issuers. Schedules de news-collection ficam fora de `definitions` → deletados como "stale".
- **Correção:** Tratar erro de DB como fatal (levantar exceção) OU em caso de falha, NÃO executar limpeza de stale.

---

## P2 — Polish

### 8. Sem confirmação para ações destrutivas ✅

- **Onde:** `web/src/app/schedules/page.tsx:502-504`
- **Problema:** Delete executa sem confirmação.
- **Correção:** Usar `window.confirm()` antes de deletar (padrão do codebase).

### 9. `parseDuration` e `parseIntervalValue` são duplicados ✅

- **Onde:** `web/src/hooks/use-schedules.ts:43-67` + `web/src/app/schedules/page.tsx:28-50`
- **Problema:** Lógica similar em dois arquivos.
- **Correção:** Mover `parseIntervalValue` para o hook e exportar.

### 10. Runs não mostra result_summary ✅

- **Onde:** `web/src/app/schedules/page.tsx:272-318`
- **Problema:** Tabela de histórico tem "Erro" mas não mostra dados de sucesso.
- **Correção:** Adicionar coluna "Resultado" exibindo `result_summary` de forma legível.

### 11. Sem auto-refresh enquanto schedule está rodando ✅

- **Onde:** `web/src/hooks/use-schedules.ts:77`
- **Problema:** `staleTime: 15_000` — dados só atualizam a cada 15s.
- **Correção:** Adicionar `refetchInterval: 5_000` quando há schedules ativos.

### 12. Validação de intervalo sem limite ✅

- **Onde:** `src/apps/api/routes/schedules.py:107-110`
- **Problema:** Sem `ge`/`le` nos campos. Usuário pode colocar 1 segundo.
- **Correção:** Adicionar `Field(ge=1, le=10080)` para minutes, `Field(ge=1, le=720)` para hours, `Field(ge=1, le=365)` para days.

---

## Itens pendentes do PLAN-3 original (não bloqueantes)

### 13. POST endpoint para criar schedules avulsos ✅

- **Correção:** `POST /api/v1/schedules` com `CreateScheduleRequestV1` (schedule_id, workflow_type, task_queue, input_data, interval, paused). Validação de workflow e intervalo. Audit trail.

### 14. list_schedules com limite de memória ✅

- **Correção:** `limit` (default 100, max 500) e `offset` (default 0) como query params. Sorting por category + schedule_id.

### 15. Audit trail ✅

- **Correção:** Função `_log_schedule_audit()` chamada em pause, resume, trigger, delete, update-interval e create. Grava na tabela `audit_log_entries` com tenant_id, actor_id, action, schedule_id, e meta_data.

### 16. useScheduleRuns sem AbortController ✅

- **Correção:** `queryFn` agora passa `signal` do React Query para `bffFetch`. Fetches são cancelados em desmonte.

### 17. _parse_schedule_description usa getattr chains frágeis ✅

- **Correção:** Funções helper `_safe_get()` e `_safe_str()` encapsulam getattr com fallback seguro. `_parse_schedule_description()` refatorada para usar helpers. Complexidade reduzida de 13 para dentro do limite do ruff.

---

## Ordem de Implementação

1. **#1** — Proteger equity-exploration do delete (1h)
2. **#3** — Inverter lógica de `is_default` para mostrar DELETE (30min)
3. **#8** — Adicionar `confirm()` antes de delete (15min)
4. **#7** — Tratar falha de DB como fatal no reconcile (30min)
5. **#2** — Adicionar botão "Reconciliar" sempre visível (1h)
6. **#4** — Adicionar coluna "Workflow" na tabela (1h)
7. **#5** — Adicionar "Última execução" na tabela (1h)
8. **#6** — Badge de sucesso/falha por schedule (1h)
9. **#9** — Deduplicar parseDuration/parseIntervalValue (30min)
10. **#12** — Adicionar validação de limites (15min)
11. **#10** — Mostrar result_summary no RunsPanel (1h)
12. **#11** — Auto-refresh condicional (1h)

---

## Orçamento Estimado

| Fase | Itens | Esforço estimado |
|------|-------|-----------------|
| P0 (crítico) | #1, #2, #3, #7, #8 | ~2h |
| P1 (importante) | #4, #5, #6 | ~3h |
| P2 (polish) | #9, #10, #11, #12 | ~2h |
| Pendentes | #13, #14, #15, #16, #17 | ~2h |
| **Total** | **17 itens** | **~9h** |

**Status: 17/17 implementados ✅**

---

## Verificação

Após cada fase, rodar:
- `ruff check src/apps/scheduler/ src/apps/api/routes/schedules.py`
- `cd web && npx tsc --noEmit`
- `pytest tests/unit/ -q`
- Teste manual: criar schedule equity-exploration → reconcile → verificar que NÃO foi deletado
- Teste manual: clicar "Reconciliar" → verificar feedback
- Teste manual: clicar DELETE → verificar confirmação → verificar que schedule some
- Teste manual: expandir histórico → verificar resultado e não só erro
- Teste manual: mudar intervalo para 1s → verificar que API rejeita com 422
