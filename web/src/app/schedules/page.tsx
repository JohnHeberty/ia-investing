"use client";

import { Suspense, useCallback, useState } from "react";
import { toast } from "sonner";

import { Badge, Metric } from "@/components/domain";
import { DataStatePanel, LoadingSkeleton, StaleWarning } from "@/components/data-state-components";
import {
  useScheduleRuns,
  useSchedules,
  useScheduleTrigger,
  parseIntervalValue,
  type ScheduleSummary,
} from "@/hooks/use-schedules";
import {
  Pause,
  Play,
  RefreshCw,
  Trash2,
  Clock,
  ChevronDown,
  ChevronRight,
  Pencil,
  Check,
  X,
} from "lucide-react";

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
  "news-dedup-cleanup": "NewsDedupWorkflow",
  "operation-outbox-dispatch": "DispatchOperationsWorkflow",
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
  onUpdateInterval: (
    scheduleId: string,
    value: { everyMinutes?: number; everyHours?: number; everyDays?: number },
  ) => Promise<void>;
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
      unit === "days"
        ? { everyDays: value }
        : unit === "hours"
          ? { everyHours: value }
          : { everyMinutes: value };
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

  if (schedule.is_default) {
    return (
      <span style={{ fontFamily: "var(--font-mono)", fontSize: 13 }}>
        {interval ? parseDuration(interval) : "—"}
      </span>
    );
  }

  if (editing) {
    return (
      <div className="flex items-center gap-4">
        <input
          className="form-input interval-input"
          type="number"
          min={1}
          value={value}
          onChange={(e) => setValue(parseInt(e.target.value) || 1)}
          onKeyDown={(e) => {
            if (e.key === "Enter") save();
            if (e.key === "Escape") cancel();
          }}
          disabled={saving}
        />
        <select
          className="form-input interval-select"
          value={unit}
          onChange={(e) => setUnit(e.target.value)}
          disabled={saving}
        >
          <option value="minutes">min</option>
          <option value="hours">horas</option>
          <option value="days">dias</option>
        </select>
        <button
          className="button xs"
          onClick={save}
          disabled={saving}
          type="button"
          aria-label="Salvar"
        >
          {saving ? <RefreshCw size={12} className="animate-spin" /> : <Check size={12} />}
        </button>
        <button
          className="button xs"
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
      className="flex items-center gap-4 cursor-pointer"
      style={{ fontFamily: "var(--font-mono)", fontSize: 13 }}
      onClick={startEdit}
      onKeyDown={(e) => {
        if (e.key === "Enter") startEdit();
      }}
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
  onTogglePause,
  onDelete,
  onUpdateInterval,
  parseDuration,
  isOwnMutating,
}: {
  schedule: ScheduleSummary;
  onTogglePause: (scheduleId: string, paused: boolean) => void;
  onDelete: (scheduleId: string) => void;
  onUpdateInterval: (
    scheduleId: string,
    value: { everyMinutes?: number; everyHours?: number; everyDays?: number },
  ) => Promise<void>;
  parseDuration: (every: string) => string;
  isOwnMutating: boolean;
}) {
  const { trigger, phase } = useScheduleTrigger(schedule.schedule_id, schedule.description);
  const nextRun = schedule.next_action_time
    ? new Date(schedule.next_action_time).toLocaleString("pt-BR", {
        dateStyle: "short",
        timeStyle: "short",
      })
    : null;

  const isTriggerBusy = phase !== "idle";

  return (
    <tr>
      <td>
        <div className="flex-col gap-4">
          <span className="fw-500" style={{ fontSize: 13 }}>
            {schedule.description || schedule.schedule_id}
          </span>
          <span className="text-xs muted mono">{schedule.schedule_id}</span>
        </div>
      </td>
      <td>
        <span className="text-sm muted mono">{getWorkflowLabel(schedule.schedule_id)}</span>
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
      <td className="text-sm mono">
        {schedule.last_run_at
          ? new Date(schedule.last_run_at).toLocaleString("pt-BR", {
              dateStyle: "short",
              timeStyle: "short",
            })
          : "—"}
      </td>
      <td className="text-sm">
        {schedule.last_run_at ? (
          <span className="text-muted">registrado</span>
        ) : (
          <span className="text-muted">—</span>
        )}
      </td>
      <td style={{ fontSize: 13 }}>{nextRun ?? "—"}</td>
      <td>
        <div className="flex gap-8">
          <button
            className="button sm"
            onClick={() => onTogglePause(schedule.schedule_id, schedule.paused)}
            type="button"
            disabled={isOwnMutating}
            aria-label={schedule.paused ? "Retomar" : "Pausar"}
          >
            {isOwnMutating ? (
              <RefreshCw size={16} className="animate-spin" />
            ) : schedule.paused ? (
              <Play size={16} />
            ) : (
              <Pause size={16} />
            )}
          </button>
          <button
            className="button sm"
            onClick={() => trigger()}
            type="button"
            disabled={isOwnMutating || isTriggerBusy}
            aria-label="Executar agora"
          >
            {isTriggerBusy ? <RefreshCw size={16} className="animate-spin" /> : <Play size={16} />}
          </button>
          {!schedule.is_default && (
            <button
              className="button sm"
              onClick={() => onDelete(schedule.schedule_id)}
              type="button"
              disabled={isOwnMutating}
              aria-label="Excluir"
            >
              <Trash2 size={16} />
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
      <div className="text-sm text-red" style={{ padding: 16 }}>
        Erro ao carregar execuções: {error?.message ?? "desconhecido"}
      </div>
    );
  }

  if (runs.length === 0) {
    return (
      <div className="text-sm text-muted" style={{ padding: 16 }}>
        Nenhuma execução registrada
      </div>
    );
  }

  return (
    <div className="runs-panel-scroll">
      <div className="table-wrap">
        <table className="table w-full">
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
                  <Badge
                    tone={
                      run.status === "completed" ? "good" : run.status === "failed" ? "bad" : "warn"
                    }
                  >
                    {run.status}
                  </Badge>
                </td>
                <td className="text-sm mono">
                  {new Date(run.started_at).toLocaleString("pt-BR", {
                    dateStyle: "short",
                    timeStyle: "short",
                  })}
                </td>
                <td className="text-sm mono">
                  {run.finished_at
                    ? new Date(run.finished_at).toLocaleString("pt-BR", {
                        dateStyle: "short",
                        timeStyle: "short",
                      })
                    : "—"}
                </td>
                <td className="text-sm truncate mono" style={{ maxWidth: 200 }}>
                  {run.result_summary
                    ? typeof run.result_summary === "object"
                      ? Object.entries(run.result_summary as Record<string, unknown>)
                          .slice(0, 3)
                          .map(
                            ([k, v]) =>
                              `${k}: ${typeof v === "object" ? JSON.stringify(v) : String(v)}`,
                          )
                          .join(", ")
                      : String(run.result_summary)
                    : "—"}
                </td>
                <td
                  className="text-sm"
                  style={{ color: run.error_message ? "var(--red)" : "var(--muted)" }}
                >
                  {run.error_message ?? "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {hasMore && (
        <button
          className="button md w-full"
          style={{ marginTop: 8 }}
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
  expandedCategories: Set<string>;
  toggleCategory: (cat: string) => void;
  onTogglePause: (scheduleId: string, paused: boolean) => void;
  onDelete: (scheduleId: string) => void;
  onUpdateInterval: (
    scheduleId: string,
    value: { everyMinutes?: number; everyHours?: number; everyDays?: number },
  ) => Promise<void>;
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
    <div className="card card-pad section-gap overflow-hidden">
      <button type="button" onClick={() => toggleCategory(category)} className="category-toggle">
        {isExpanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
        <div
          className="category-dot"
          style={{ background: CATEGORY_COLORS[category] ?? "#8eaaa0" }}
        />
        <span className="fw-500" style={{ fontSize: 15 }}>
          {CATEGORY_LABELS[category] ?? category}
        </span>
        <Badge tone="neutral">{schedules.length}</Badge>
        <span className="text-sm text-muted" style={{ marginLeft: "auto" }}>
          {activeCount} ativo{activeCount !== 1 ? "s" : ""}
        </span>
      </button>

      {isExpanded && (
        <div className="mt-16">
          <div className="table-wrap">
            <table className="table w-full">
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

          <div className="mt-8">
            {schedules.map((s) => (
              <div key={`runs-${s.schedule_id}`}>
                <button
                  type="button"
                  onClick={() => toggleRunsPanel(s.schedule_id)}
                  className="runs-toggle"
                >
                  <Clock size={12} />
                  Histórico de execuções — {s.description || s.schedule_id}
                  {expandedRuns.has(s.schedule_id) ? (
                    <ChevronDown size={12} />
                  ) : (
                    <ChevronRight size={12} />
                  )}
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
    isReconciling,
    parseDuration,
  } = useSchedules();

  const [expandedCategories, setExpandedCategories] = useState<Set<string>>(
    new Set(["news", "portfolio", "data", "operations", "research", "other"]),
  );
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

  const handleTogglePause = useCallback(
    async (scheduleId: string, paused: boolean) => {
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
    },
    [pause, resume],
  );

  const handleDelete = useCallback(
    async (scheduleId: string) => {
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
    },
    [deleteSchedule],
  );

  const handleUpdateInterval = useCallback(
    async (
      scheduleId: string,
      value: { everyMinutes?: number; everyHours?: number; everyDays?: number },
    ) => {
      try {
        await updateInterval({ scheduleId, ...value });
      } catch (err) {
        const msg = err instanceof Error ? err.message : "Erro desconhecido";
        toast.error(`Falha ao atualizar intervalo: ${msg}`);
        throw err;
      }
    },
    [updateInterval],
  );

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
        <section className="grid grid-4 section-gap" aria-live="polite">
          <div className="card metric">
            <LoadingSkeleton lines={4} />
          </div>
          <div className="card metric">
            <LoadingSkeleton lines={4} />
          </div>
          <div className="card metric">
            <LoadingSkeleton lines={4} />
          </div>
          <div className="card metric">
            <LoadingSkeleton lines={4} />
          </div>
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
          <p className="subtitle">Cron jobs e periodicidades gerenciados pelo Temporal.</p>
        </div>
      </div>

      {dataState === "stale" && <StaleWarning />}

      <section className="grid grid-4 section-gap">
        <Metric label="Total" value={String(count)} note="schedules" />
        <Metric label="Ativos" value={String(activeCount)} note="rodando" />
        <Metric label="Pausados" value={String(pausedCount)} note="pausados" />
        <Metric label="Categorias" value={String(Object.keys(grouped).length)} note="grupos" />
      </section>

      <div className="reconcile-bar">
        <button
          className="button md"
          onClick={handleReconcile}
          type="button"
          disabled={isReconciling}
        >
          <RefreshCw size={12} className="mt-4" />
          {isReconciling ? "Reconciliando..." : "Reconciliar"}
        </button>
      </div>
      {reconcileMsg && <div className="text-sm text-accent text-right mb-16">{reconcileMsg}</div>}

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
