"use client";

import { Suspense, useCallback, useState } from "react";
import { toast } from "sonner";

import { Badge, Metric } from "@/components/domain";
import { DataStatePanel, LoadingSkeleton, StaleWarning } from "@/components/data-state-components";
import { useScheduleRuns, useSchedules, useScheduleTrigger, parseIntervalValue, type ScheduleSummary } from "@/hooks/use-schedules";
import { Pause, Play, RefreshCw, Trash2, Clock, ChevronDown, ChevronRight, Pencil, Check, X } from "lucide-react";

const CATEGORY_LABELS: Record<string, string> = {
  news: "Notícias",
  data: "Dados",
  portfolio: "Carteira",
  operations: "Operações",
  research: "Pesquisa",
  other: "Outros",
};

const CATEGORY_COLORS: Record<string, string> = {
  news: "#76b6ff",
  data: "#5ee0a4",
  portfolio: "#f4bd63",
  operations: "#ff857f",
  research: "#c4b5fd",
  other: "#8eaaa0",
};

const WORKFLOW_LABELS: Record<string, string> = {
  "news-collection-": "ExtractNewsWorkflow",
  "news-dedup-cleanup": "DispatchOperationsWorkflow",
  "outbox-dispatch-recovery": "DispatchOperationsWorkflow",
  "cvm-dfp-": "IngestCVMWorkflow",
  "paper-reconciliation-": "PaperReconciliationWorkflow",
  "paper-valuation-": "PaperValuationWorkflow",
  "paper-rebalance-": "PaperRebalanceWorkflow",
  "equity-exploration-": "ScheduledEquityExplorationWorkflow",
};

function getWorkflowLabel(scheduleId: string): string {
  for (const [prefix, label] of Object.entries(WORKFLOW_LABELS)) {
    if (scheduleId.startsWith(prefix)) return label;
  }
  return "—";
}

function IntervalEditor({
  schedule,
  onUpdateInterval,
  parseDuration,
}: {
  schedule: ScheduleSummary;
  onUpdateInterval: (scheduleId: string, value: { everyMinutes?: number; everyHours?: number; everyDays?: number }) => Promise<void>;
  parseDuration: (every: string) => string;
}) {
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [value, setValue] = useState(0);
  const [unit, setUnit] = useState("hours");

  const interval = schedule.spec?.intervals?.[0]?.every ?? "";

  const startEdit = useCallback(() => {
    const parsed = parseIntervalValue(interval);
    setValue(parsed.value);
    setUnit(parsed.unit);
    setEditing(true);
  }, [interval]);

  const save = useCallback(async () => {
    const payload =
      unit === "days" ? { everyDays: value } :
      unit === "hours" ? { everyHours: value } :
      { everyMinutes: value };
    setSaving(true);
    try {
      await onUpdateInterval(schedule.schedule_id, payload);
      setEditing(false);
    } catch {
      // Editor stays open on failure — toast already shown by handleUpdateInterval
    } finally {
      setSaving(false);
    }
  }, [unit, value, schedule.schedule_id, onUpdateInterval]);

  const cancel = useCallback(() => {
    setEditing(false);
  }, []);

  if (editing) {
    return (
      <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
        <input
          className="form-input"
          type="number"
          min={1}
          value={value}
          onChange={(e) => setValue(parseInt(e.target.value) || 1)}
          style={{ width: 60, fontSize: 12, padding: "2px 6px" }}
          onKeyDown={(e) => {
            if (e.key === "Enter") save();
            if (e.key === "Escape") cancel();
          }}
          disabled={saving}
        />
        <select
          className="form-input"
          value={unit}
          onChange={(e) => setUnit(e.target.value)}
          style={{ fontSize: 12, padding: "2px 4px", width: 70 }}
          disabled={saving}
        >
          <option value="minutes">min</option>
          <option value="hours">horas</option>
          <option value="days">dias</option>
        </select>
        <button
          className="button"
          style={{ padding: "2px 6px", fontSize: 11 }}
          onClick={save}
          disabled={saving}
          type="button"
          aria-label="Salvar"
        >
          {saving ? <RefreshCw size={12} className="animate-spin" /> : <Check size={12} />}
        </button>
        <button
          className="button"
          style={{ padding: "2px 6px", fontSize: 11 }}
          onClick={cancel}
          type="button"
          disabled={saving}
          aria-label="Cancelar"
        >
          <X size={12} />
        </button>
      </div>
    );
  }

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 4,
        cursor: "pointer",
        fontFamily: "var(--font-mono)",
        fontSize: 13,
      }}
      onClick={startEdit}
      onKeyDown={(e) => { if (e.key === "Enter") startEdit(); }}
      role="button"
      tabIndex={0}
      aria-label="Editar intervalo"
    >
      {interval ? parseDuration(interval) : "—"}
      <Pencil size={10} style={{ opacity: 0.4 }} />
    </div>
  );
}

function ScheduleRow({
  schedule,
  items,
  onTogglePause,
  onDelete,
  onUpdateInterval,
  parseDuration,
  isOwnMutating,
}: {
  schedule: ScheduleSummary;
  items: ScheduleSummary[];
  onTogglePause: (scheduleId: string, paused: boolean) => void;
  onDelete: (scheduleId: string) => void;
  onUpdateInterval: (scheduleId: string, value: { everyMinutes?: number; everyHours?: number; everyDays?: number }) => Promise<void>;
  parseDuration: (every: string) => string;
  isOwnMutating: boolean;
}) {
  const { trigger, phase } = useScheduleTrigger(schedule.schedule_id, schedule.description, items);
  const nextRun = schedule.next_action_time
    ? new Date(schedule.next_action_time).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" })
    : null;

  const isTriggerBusy = phase !== "idle";

  return (
    <tr>
      <td>
        <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
          <span style={{ fontWeight: 500, fontSize: 13 }}>{schedule.description || schedule.schedule_id}</span>
          <span style={{ fontSize: 11, color: "var(--muted)", fontFamily: "var(--font-mono)" }}>
            {schedule.schedule_id}
          </span>
        </div>
      </td>
      <td>
        <span style={{ fontSize: 12, fontFamily: "var(--font-mono)", color: "var(--muted)" }}>
          {getWorkflowLabel(schedule.schedule_id)}
        </span>
      </td>
      <td>
        <Badge tone={schedule.paused ? "warn" : "good"}>
          {schedule.paused ? "Pausado" : "Ativo"}
        </Badge>
      </td>
      <td>
        <IntervalEditor
          schedule={schedule}
          onUpdateInterval={onUpdateInterval}
          parseDuration={parseDuration}
        />
      </td>
      <td style={{ fontSize: 12, fontFamily: "var(--font-mono)" }}>
        {schedule.last_run_at
          ? new Date(schedule.last_run_at).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" })
          : "—"}
      </td>
      <td style={{ fontSize: 12 }}>
        {schedule.last_run_at ? (
          <span style={{ color: "var(--muted)" }}>registrado</span>
        ) : (
          <span style={{ color: "var(--muted)" }}>—</span>
        )}
      </td>
      <td style={{ fontSize: 13 }}>{nextRun ?? "—"}</td>
      <td>
        <div style={{ display: "flex", gap: 6 }}>
          <button
            className="button"
            style={{ fontSize: 11, padding: "4px 10px" }}
            onClick={() => onTogglePause(schedule.schedule_id, schedule.paused)}
            type="button"
            disabled={isOwnMutating}
            aria-label={schedule.paused ? "Retomar" : "Pausar"}
          >
            {isOwnMutating ? <RefreshCw size={12} className="animate-spin" /> : schedule.paused ? <Play size={12} /> : <Pause size={12} />}
            {schedule.paused ? "Retomar" : "Pausar"}
          </button>
          <button
            className="button"
            style={{ fontSize: 11, padding: "4px 10px" }}
            onClick={() => trigger()}
            type="button"
            disabled={isOwnMutating || isTriggerBusy}
            aria-label="Executar agora"
          >
            <RefreshCw size={12} className={isTriggerBusy ? "animate-spin" : ""} />
            {phase === "idle" ? "Executar"
              : phase === "starting" ? "Iniciando..."
              : phase === "completed" ? "Concluído!"
              : phase === "failed" ? "Falhou!"
              : "Sem resposta"}
          </button>
          {!schedule.is_default && (
            <button
              className="button"
              style={{ fontSize: 11, padding: "4px 10px", color: "var(--red)" }}
              onClick={() => onDelete(schedule.schedule_id)}
              type="button"
              disabled={isOwnMutating}
              aria-label="Excluir"
            >
              <Trash2 size={12} />
            </button>
          )}
        </div>
      </td>
    </tr>
  );
}

function RunsPanel({ scheduleId }: { scheduleId: string }) {
  const { runs, isLoading, isError, error } = useScheduleRuns(scheduleId);
  const [page, setPage] = useState(0);
  const PAGE_SIZE = 20;

  const displayedRuns = runs.slice(0, (page + 1) * PAGE_SIZE);
  const hasMore = runs.length > (page + 1) * PAGE_SIZE;

  if (isLoading) return <LoadingSkeleton lines={3} />;

  if (isError) {
    return (
      <div style={{ padding: 16, fontSize: 13, color: "var(--red)" }}>
        Erro ao carregar execuções: {error?.message ?? "desconhecido"}
      </div>
    );
  }

  if (runs.length === 0) {
    return (
      <div style={{ padding: 16, fontSize: 13, color: "var(--muted)" }}>
        Nenhuma execução registrada
      </div>
    );
  }

  return (
    <div style={{ maxHeight: 300, overflowY: "auto" }}>
      <div className="table-wrap">
        <table className="table" style={{ width: "100%" }}>
          <thead>
            <tr>
              <th>Status</th>
              <th>Início</th>
              <th>Fim</th>
              <th>Resultado</th>
              <th>Erro</th>
            </tr>
          </thead>
          <tbody>
            {displayedRuns.map((run) => (
              <tr key={run.id}>
                <td>
                  <Badge tone={run.status === "completed" ? "good" : run.status === "failed" ? "bad" : "warn"}>
                    {run.status}
                  </Badge>
                </td>
                <td style={{ fontSize: 12, fontFamily: "var(--font-mono)" }}>
                  {new Date(run.started_at).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" })}
                </td>
                <td style={{ fontSize: 12, fontFamily: "var(--font-mono)" }}>
                  {run.finished_at
                    ? new Date(run.finished_at).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" })
                    : "—"}
                </td>
                <td style={{ fontSize: 12, fontFamily: "var(--font-mono)", maxWidth: 200, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {run.result_summary
                    ? typeof run.result_summary === "object"
                      ? Object.entries(run.result_summary as Record<string, unknown>)
                          .slice(0, 3)
                          .map(([k, v]) => `${k}: ${typeof v === "object" ? JSON.stringify(v) : String(v)}`)
                          .join(", ")
                      : String(run.result_summary)
                    : "—"}
                </td>
                <td style={{ fontSize: 12, color: run.error_message ? "var(--red)" : "var(--muted)" }}>
                  {run.error_message ?? "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {hasMore && (
        <button
          className="button"
          style={{ fontSize: 12, padding: "6px 12px", marginTop: 8, width: "100%" }}
          onClick={() => setPage((p) => p + 1)}
          type="button"
        >
          Carregar mais ({runs.length - displayedRuns.length} restantes)
        </button>
      )}
    </div>
  );
}

function CategoryGroup({
  category,
  schedules,
  items,
  expandedCategories,
  toggleCategory,
  onTogglePause,
  onDelete,
  onUpdateInterval,
  parseDuration,
  mutatingId,
}: {
  category: string;
  schedules: ScheduleSummary[];
  items: ScheduleSummary[];
  expandedCategories: Set<string>;
  toggleCategory: (cat: string) => void;
  onTogglePause: (scheduleId: string, paused: boolean) => void;
  onDelete: (scheduleId: string) => void;
  onUpdateInterval: (scheduleId: string, value: { everyMinutes?: number; everyHours?: number; everyDays?: number }) => Promise<void>;
  parseDuration: (every: string) => string;
  mutatingId: string | null;
}) {
  const [expandedRuns, setExpandedRuns] = useState<Set<string>>(new Set());
  const isExpanded = expandedCategories.has(category);
  const activeCount = schedules.filter((s) => !s.paused).length;

  const toggleRunsPanel = (sid: string) => {
    setExpandedRuns((prev) => {
      const next = new Set(prev);
      if (next.has(sid)) next.delete(sid);
      else next.add(sid);
      return next;
    });
  };

  return (
    <div className="card card-pad section-gap" style={{ overflow: "hidden" }}>
      <button
        type="button"
        onClick={() => toggleCategory(category)}
        style={{
          display: "flex",
          alignItems: "center",
          gap: 10,
          width: "100%",
          border: "none",
          background: "none",
          cursor: "pointer",
          padding: 0,
          textAlign: "left",
        }}
      >
        {isExpanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
        <div
          style={{
            width: 8,
            height: 8,
            borderRadius: "50%",
            background: CATEGORY_COLORS[category] ?? "#8eaaa0",
          }}
        />
        <span style={{ fontWeight: 600, fontSize: 15 }}>
          {CATEGORY_LABELS[category] ?? category}
        </span>
        <Badge tone="neutral">{schedules.length}</Badge>
        <span style={{ fontSize: 12, color: "var(--muted)", marginLeft: "auto" }}>
          {activeCount} ativo{activeCount !== 1 ? "s" : ""}
        </span>
      </button>

      {isExpanded && (
        <div style={{ marginTop: 16 }}>
          <div className="table-wrap">
            <table className="table" style={{ width: "100%" }}>
              <thead>
                <tr>
                  <th>Agendamento</th>
                  <th>Workflow</th>
                  <th>Status</th>
                  <th>Intervalo</th>
                  <th>Última execução</th>
                  <th>Execuções</th>
                  <th>Próxima execução</th>
                  <th>Ações</th>
                </tr>
              </thead>
              <tbody>
                {schedules.map((s) => (
                  <ScheduleRow
                    key={s.schedule_id}
                    schedule={s}
                    items={items}
                    onTogglePause={onTogglePause}
                    onDelete={onDelete}
                    onUpdateInterval={onUpdateInterval}
                    parseDuration={parseDuration}
                    isOwnMutating={mutatingId === s.schedule_id}
                  />
                ))}
              </tbody>
            </table>
          </div>

          <div style={{ marginTop: 8 }}>
            {schedules.filter((s) => s.last_run_at).map((s) => (
              <div key={`runs-${s.schedule_id}`}>
                <button
                  type="button"
                  onClick={() => toggleRunsPanel(s.schedule_id)}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 6,
                    border: "none",
                    background: "none",
                    cursor: "pointer",
                    padding: "6px 0",
                    fontSize: 12,
                    color: "var(--muted)",
                  }}
                >
                  <Clock size={12} />
                  Histórico de execuções — {s.description || s.schedule_id}
                  {expandedRuns.has(s.schedule_id) ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
                </button>
                {expandedRuns.has(s.schedule_id) && <RunsPanel scheduleId={s.schedule_id} />}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default function SchedulesPage() {
  const {
    items,
    grouped,
    activeCount,
    pausedCount,
    isLoading,
    isError,
    error,
    dataState,
    refetch,
    count,
    pause,
    resume,
    deleteSchedule,
    updateInterval,
    reconcile,
    reconcileResult,
    isMutating,
    isReconciling,
    parseDuration,
  } = useSchedules();

  const [expandedCategories, setExpandedCategories] = useState<Set<string>>(new Set(["news", "portfolio", "data", "operations", "research", "other"]));
  const [reconcileMsg, setReconcileMsg] = useState<string | null>(null);
  const [mutatingId, setMutatingId] = useState<string | null>(null);

  const toggleCategory = useCallback((cat: string) => {
    setExpandedCategories((prev) => {
      const next = new Set(prev);
      if (next.has(cat)) next.delete(cat);
      else next.add(cat);
      return next;
    });
  }, []);

  const handleTogglePause = useCallback(async (scheduleId: string, paused: boolean) => {
    setMutatingId(scheduleId);
    try {
      if (paused) await resume(scheduleId);
      else await pause(scheduleId);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Erro desconhecido";
      toast.error(`Falha ao ${paused ? "retomar" : "pausar"} agendamento: ${msg}`);
    } finally {
      setMutatingId(null);
    }
  }, [pause, resume]);

  const handleDelete = useCallback(async (scheduleId: string) => {
    if (!window.confirm("Tem certeza que deseja excluir este agendamento?")) return;
    setMutatingId(scheduleId);
    try {
      await deleteSchedule(scheduleId);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Erro desconhecido";
      toast.error(`Falha ao excluir agendamento: ${msg}`);
    } finally {
      setMutatingId(null);
    }
  }, [deleteSchedule]);

  const handleUpdateInterval = useCallback(async (scheduleId: string, value: { everyMinutes?: number; everyHours?: number; everyDays?: number }) => {
    try {
      await updateInterval({ scheduleId, ...value });
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Erro desconhecido";
      toast.error(`Falha ao atualizar intervalo: ${msg}`);
      throw err;
    }
  }, [updateInterval]);

  const handleReconcile = useCallback(async () => {
    setReconcileMsg(null);
    try {
      const result = await reconcile();
      if (result) {
        const parts: string[] = [];
        if (result.created.length > 0) parts.push(`${result.created.length} criado(s)`);
        if (result.updated.length > 0) parts.push(`${result.updated.length} atualizado(s)`);
        if (result.deleted.length > 0) parts.push(`${result.deleted.length} removido(s)`);
        setReconcileMsg(parts.length > 0 ? parts.join(", ") : "Nenhuma alteração");
      }
    } catch {
      setReconcileMsg("Erro ao reconciliar");
    }
  }, [reconcile]);

  if (isLoading) {
    return (
      <>
        <div className="page-head">
          <div>
            <div className="eyebrow">Infraestrutura</div>
            <h1>Agendamentos</h1>
            <p className="subtitle">Gerenciar cron jobs e periodicidades do sistema.</p>
          </div>
        </div>
        <section className="grid grid-4 section-gap">
          <div className="card metric"><LoadingSkeleton lines={4} /></div>
          <div className="card metric"><LoadingSkeleton lines={4} /></div>
          <div className="card metric"><LoadingSkeleton lines={4} /></div>
          <div className="card metric"><LoadingSkeleton lines={4} /></div>
        </section>
      </>
    );
  }

  if (isError) {
    return (
      <>
        <div className="page-head">
          <div>
            <div className="eyebrow">Infraestrutura</div>
            <h1>Agendamentos</h1>
          </div>
        </div>
        <DataStatePanel
          state="error"
          title="Erro ao carregar agendamentos"
          detail={error?.message ?? "Não foi possível acessar os schedules do Temporal."}
          action={
            <button className="button" onClick={() => refetch()} type="button">
              Tentar novamente
            </button>
          }
        />
      </>
    );
  }

  return (
    <Suspense fallback={<LoadingSkeleton lines={4} />}>
      <div className="page-head">
        <div>
          <div className="eyebrow">Infraestrutura</div>
          <h1>Agendamentos</h1>
          <p className="subtitle">
            Cron jobs e periodicidades gerenciados pelo Temporal.
          </p>
        </div>
      </div>

      {dataState === "stale" && <StaleWarning />}

      <section className="grid grid-4 section-gap">
        <Metric label="Total" value={String(count)} note="schedules" />
        <Metric label="Ativos" value={String(activeCount)} note="rodando" />
        <Metric label="Pausados" value={String(pausedCount)} note="pausados" />
        <Metric label="Categorias" value={String(Object.keys(grouped).length)} note="grupos" />
      </section>

      <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: 16 }}>
        <button
          className="button"
          onClick={handleReconcile}
          type="button"
          disabled={isReconciling}
          style={{ fontSize: 12, padding: "6px 14px" }}
        >
          <RefreshCw size={12} style={{ marginRight: 4 }} />
          {isReconciling ? "Reconciliando..." : "Reconciliar"}
        </button>
      </div>
      {reconcileMsg && (
        <div style={{ fontSize: 12, color: "var(--accent)", marginBottom: 16, textAlign: "right" }}>
          {reconcileMsg}
        </div>
      )}

      {count === 0 ? (
        <DataStatePanel
          state="empty"
          title="Nenhum agendamento encontrado"
          detail="Clique em 'Reconciliar' acima para criar os agendamentos padrão do sistema."
        />
      ) : (
        <div>
          {Object.entries(grouped).map(([category, schedules]) => (
            <CategoryGroup
              key={category}
              category={category}
              schedules={schedules}
              items={items}
              expandedCategories={expandedCategories}
              toggleCategory={toggleCategory}
              onTogglePause={handleTogglePause}
              onDelete={handleDelete}
              onUpdateInterval={handleUpdateInterval}
              parseDuration={parseDuration}
              mutatingId={mutatingId}
            />
          ))}
        </div>
      )}
    </Suspense>
  );
}
