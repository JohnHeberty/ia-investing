"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import type { DataState } from "@/components/domain";
import { bffFetch, queryKeys } from "@/lib/api-client";
import { computeDataState } from "@/lib/data-state";

export interface ScheduleSummary {
  schedule_id: string;
  status: string;
  paused: boolean;
  category: string;
  description: string;
  is_default: boolean;
  next_action_time: string | null;
  spec: {
    intervals: Array<{ every: string; offset: string | null }>;
    calendars: unknown[];
    cron_expressions: unknown[];
  } | null;
  state: { paused: boolean; remaining_actions: number } | null;
  last_run_at: string | null;
  running_workflows: number;
}

export interface ScheduleRun {
  id: string;
  schedule_id: string;
  workflow_id: string | null;
  status: string;
  started_at: string;
  finished_at: string | null;
  result_summary: Record<string, unknown> | null;
  error_message: string | null;
}

export interface ReconcileResult {
  created: string[];
  updated: string[];
  deleted: string[];
  total: number;
}

function parseDuration(every: string): string {
  if (!every) return "—";
  const isoMatch = every.match(/^P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?$/i);
  if (isoMatch) {
    const d = isoMatch[1] ? parseInt(isoMatch[1]) : 0;
    const h = isoMatch[2] ? parseInt(isoMatch[2]) : 0;
    const m = isoMatch[3] ? parseInt(isoMatch[3]) : 0;
    if (d > 0) return `${d}d`;
    if (h > 0 && m > 0) return `${h}h ${m}m`;
    if (h > 0) return `${h}h`;
    if (m > 0) return `${m}m`;
  }
  const dayMatch = every.match(/^(\d+)\s+day/);
  if (dayMatch) return `${dayMatch[1]}d`;
  const timeMatch = every.match(/^(\d+):(\d+):(\d+)/);
  if (timeMatch) {
    const h = parseInt(timeMatch[1]);
    const m = parseInt(timeMatch[2]);
    if (h >= 24 && h % 24 === 0) return `${h / 24}d`;
    if (h > 0 && m > 0) return `${h}h ${m}m`;
    if (h > 0) return `${h}h`;
    if (m > 0) return `${m}m`;
  }
  return every;
}

export function parseIntervalValue(every: string): { value: number; unit: string } {
  const isoMatch = every.match(/^P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?/i);
  if (isoMatch) {
    const d = isoMatch[1] ? parseInt(isoMatch[1]) : 0;
    const h = isoMatch[2] ? parseInt(isoMatch[2]) : 0;
    const m = isoMatch[3] ? parseInt(isoMatch[3]) : 0;
    if (d > 0) return { value: d, unit: "days" };
    if (h > 0 && m === 0) return { value: h, unit: "hours" };
    if (m > 0) return { value: m, unit: "minutes" };
  }
  const dayTimeMatch = every.match(/^(\d+)\s+day[s]?,?\s*(?:(\d+):(\d+):(\d+))?/i);
  if (dayTimeMatch) {
    const d = parseInt(dayTimeMatch[1]);
    const h = dayTimeMatch[2] ? parseInt(dayTimeMatch[2]) : 0;
    if (h >= 12) return { value: d + 1, unit: "days" };
    return { value: d, unit: "days" };
  }
  const dayMatch = every.match(/^(\d+)\s+day/);
  if (dayMatch) return { value: parseInt(dayMatch[1]), unit: "days" };
  const timeMatch = every.match(/^(\d+):(\d+):(\d+)/);
  if (timeMatch) {
    const h = parseInt(timeMatch[1]);
    const m = parseInt(timeMatch[2]);
    if (h >= 24) return { value: h / 24, unit: "days" };
    if (h > 0 && m === 0) return { value: h, unit: "hours" };
    if (h === 0 && m > 0) return { value: m, unit: "minutes" };
    if (h > 0 && m > 0) return { value: h * 60 + m, unit: "minutes" };
  }
  return { value: 4, unit: "hours" };
}

export function useSchedules() {
  const queryClient = useQueryClient();

  const query = useQuery({
    queryKey: queryKeys.schedules(),
    queryFn: async () => {
      return await bffFetch<ScheduleSummary[]>("/api/v1/schedules");
    },
    staleTime: 15_000,
    refetchInterval: 5_000,
    refetchOnWindowFocus: true,
  });

  const pauseMutation = useMutation({
    mutationFn: async (scheduleId: string) => {
      const idempotencyKey = `pause-${scheduleId}`;
      return await bffFetch<{ schedule_id: string; message: string }>(
        `/api/v1/schedules/${scheduleId}/pause`,
        { method: "POST", headers: { "Idempotency-Key": idempotencyKey } },
      );
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.schedules() }),
  });

  const resumeMutation = useMutation({
    mutationFn: async (scheduleId: string) => {
      const idempotencyKey = `resume-${scheduleId}`;
      return await bffFetch<{ schedule_id: string; message: string }>(
        `/api/v1/schedules/${scheduleId}/resume`,
        { method: "POST", headers: { "Idempotency-Key": idempotencyKey } },
      );
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.schedules() }),
  });

  const deleteMutation = useMutation({
    mutationFn: async (scheduleId: string) => {
      return await bffFetch<{ schedule_id: string; message: string }>(
        `/api/v1/schedules/${scheduleId}`,
        { method: "DELETE" },
      );
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.schedules() }),
  });

  const reconcileMutation = useMutation({
    mutationFn: async () => {
      return await bffFetch<ReconcileResult>("/api/v1/schedules/reconcile", {
        method: "POST",
        headers: { "Idempotency-Key": `reconcile-${Date.now()}` },
      });
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.schedules() }),
  });

  const updateIntervalMutation = useMutation({
    mutationFn: async ({
      scheduleId,
      everyMinutes,
      everyHours,
      everyDays,
    }: {
      scheduleId: string;
      everyMinutes?: number;
      everyHours?: number;
      everyDays?: number;
    }) => {
      return await bffFetch<{ schedule_id: string; message: string }>(
        `/api/v1/schedules/${scheduleId}/update-interval`,
        {
          method: "PUT",
          headers: { "Idempotency-Key": `update-${scheduleId}-${Date.now()}` },
          body: JSON.stringify({
            every_minutes: everyMinutes ?? null,
            every_hours: everyHours ?? null,
            every_days: everyDays ?? null,
          }),
        },
      );
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.schedules() }),
  });

  const items = Array.isArray(query.data) ? query.data : [];

  const grouped = items.reduce<Record<string, ScheduleSummary[]>>((acc, s) => {
    const cat = s.category ?? "other";
    if (!acc[cat]) acc[cat] = [];
    acc[cat].push(s);
    return acc;
  }, {});

  const activeCount = items.filter((s) => !s.paused).length;
  const pausedCount = items.filter((s) => s.paused).length;

  const dataState: DataState = computeDataState(
    query.isLoading,
    query.isError,
    null,
    items.length > 0,
  );

  return {
    items,
    grouped,
    activeCount,
    pausedCount,
    isLoading: query.isLoading,
    isError: query.isError,
    error: query.error,
    dataState,
    refetch: query.refetch,
    count: items.length,
    pause: pauseMutation.mutateAsync,
    resume: resumeMutation.mutateAsync,
    deleteSchedule: deleteMutation.mutateAsync,
    updateInterval: updateIntervalMutation.mutateAsync,
    reconcile: reconcileMutation.mutateAsync,
    reconcileResult: reconcileMutation.data,
    isMutating:
      pauseMutation.isPending ||
      resumeMutation.isPending ||
      deleteMutation.isPending ||
      reconcileMutation.isPending ||
      updateIntervalMutation.isPending,
    isReconciling: reconcileMutation.isPending,
    parseDuration,
  };
}

export function useScheduleRuns(scheduleId: string | null) {
  const query = useQuery({
    queryKey: queryKeys.scheduleRuns(scheduleId ?? "", 20),
    queryFn: async ({ signal }) => {
      return await bffFetch<ScheduleRun[]>(`/api/v1/schedules/${scheduleId}/runs?limit=20`, {
        signal,
      });
    },
    enabled: !!scheduleId,
    staleTime: 10_000,
    refetchInterval: 10_000,
    refetchOnWindowFocus: true,
  });

  const items = Array.isArray(query.data) ? query.data : [];
  const dataState: DataState = computeDataState(
    query.isLoading,
    query.isError,
    null,
    items.length > 0,
  );

  return {
    runs: items,
    isLoading: query.isLoading,
    isError: query.isError,
    error: query.error,
    dataState,
    refetch: query.refetch,
  };
}

export type TriggerPhase = "idle" | "starting" | "completed" | "failed" | "timeout";

const TRIGGER_POLL_MS = 3_000;
const TRIGGER_START_TIMEOUT_MS = 60_000;
const TRIGGER_RUN_TIMEOUT_MS = 10 * 60_000;

export function selectTriggeredRun(runs: ScheduleRun[], triggeredAt: number): ScheduleRun | undefined {
  return runs.find((run) => new Date(run.started_at).getTime() >= triggeredAt);
}

export function useScheduleTrigger(scheduleId: string, description: string) {
  const queryClient = useQueryClient();
  const [phase, setPhase] = useState<TriggerPhase>("idle");
  const startedAtRef = useRef<number>(0);
  const observedRunRef = useRef(false);

  useEffect(() => {
    if (phase !== "starting") return;

    const interval = setInterval(async () => {
      try {
        const runs = await bffFetch<ScheduleRun[]>(`/api/v1/schedules/${scheduleId}/runs?limit=5`);
        const triggeredRun = selectTriggeredRun(runs, startedAtRef.current);
        observedRunRef.current ||= triggeredRun !== undefined;
        if (triggeredRun?.status === "failed") {
          setPhase("failed");
          clearInterval(interval);
          return;
        }
        if (triggeredRun?.status === "completed") {
          setPhase("completed");
          clearInterval(interval);
          return;
        }
      } catch {
        // Network error — will retry on next tick
      }

      const timeout = observedRunRef.current ? TRIGGER_RUN_TIMEOUT_MS : TRIGGER_START_TIMEOUT_MS;
      if (Date.now() - startedAtRef.current > timeout) {
        setPhase("timeout");
        clearInterval(interval);
      }
    }, TRIGGER_POLL_MS);

    return () => clearInterval(interval);
  }, [phase, scheduleId]);

  useEffect(() => {
    if (phase === "completed") {
      toast.success(`Execução concluída — ${description}`);
      const t = setTimeout(() => setPhase("idle"), 3000);
      return () => clearTimeout(t);
    }
    if (phase === "failed") {
      toast.error(`Execução falhou — ${description}`);
      const t = setTimeout(() => setPhase("idle"), 3000);
      return () => clearTimeout(t);
    }
    if (phase === "timeout") {
      toast.warning(`Execução pode não ter sido processada — ${description}`);
      const t = setTimeout(() => setPhase("idle"), 3000);
      return () => clearTimeout(t);
    }
  }, [phase, description]);

  const trigger = useCallback(async () => {
    const requestedAt = Date.now();
    const idempotencyKey = `trigger-${scheduleId}-${requestedAt}`;
    startedAtRef.current = requestedAt;
    observedRunRef.current = false;
    try {
      const response = await bffFetch<{
        schedule_id: string;
        message: string;
        triggered_at: string | null;
      }>(
        `/api/v1/schedules/${scheduleId}/trigger`,
        { method: "POST", headers: { "Idempotency-Key": idempotencyKey } },
      );
      queryClient.invalidateQueries({ queryKey: queryKeys.schedules() });
      queryClient.invalidateQueries({ queryKey: queryKeys.scheduleRuns(scheduleId, 20) });

      if (response.triggered_at) {
        startedAtRef.current = new Date(response.triggered_at).getTime();
      }
      setPhase("starting");
      toast.success(`Execução iniciada — ${description}`);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Erro desconhecido";
      toast.error(`Falha ao iniciar execução — ${description}: ${msg}`);
    }
  }, [scheduleId, description, queryClient]);

  return { trigger, phase };
}
