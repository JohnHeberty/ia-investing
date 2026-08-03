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
  running_workflows: number;
  last_run_at: string | null;
  last_run_status: string | null;
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
  const dayMatch = every.match(/^(\d+)\s+day/);
  if (dayMatch) return { value: parseInt(dayMatch[1]), unit: "days" };
  const timeMatch = every.match(/^(\d+):(\d+):(\d+)/);
  if (timeMatch) {
    const h = parseInt(timeMatch[1]);
    const m = parseInt(timeMatch[2]);
    if (h >= 24 && h % 24 === 0) return { value: h / 24, unit: "days" };
    if (h > 0 && m === 0) return { value: h, unit: "hours" };
    if (h === 0 && m > 0) return { value: m, unit: "minutes" };
    if (h > 0 && m > 0) return { value: h * 60 + m, unit: "minutes" };
  }
  const isoMatch = every.match(/^P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?/i);
  if (isoMatch) {
    const d = isoMatch[1] ? parseInt(isoMatch[1]) : 0;
    const h = isoMatch[2] ? parseInt(isoMatch[2]) : 0;
    const m = isoMatch[3] ? parseInt(isoMatch[3]) : 0;
    if (d > 0) return { value: d, unit: "days" };
    if (h > 0 && m === 0) return { value: h, unit: "hours" };
    if (m > 0) return { value: m, unit: "minutes" };
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
      return await bffFetch<ReconcileResult>(
        "/api/v1/schedules/reconcile",
        { method: "POST", headers: { "Idempotency-Key": `reconcile-${Date.now()}` } },
      );
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.schedules() }),
  });

  const updateIntervalMutation = useMutation({
    mutationFn: async ({ scheduleId, everyMinutes, everyHours, everyDays }: {
      scheduleId: string;
      everyMinutes?: number;
      everyHours?: number;
      everyDays?: number;
    }) => {
      return await bffFetch<{ schedule_id: string; message: string }>(
        `/api/v1/schedules/${scheduleId}/update-interval`,
        {
          method: "PUT",
          headers: { "Idempotency-Key": `update-${scheduleId}` },
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

  const dataState: DataState = computeDataState(query.isLoading, query.isError, null, items.length > 0);

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
    isMutating: pauseMutation.isPending || resumeMutation.isPending
      || deleteMutation.isPending || reconcileMutation.isPending || updateIntervalMutation.isPending,
    isReconciling: reconcileMutation.isPending,
    parseDuration,
  };
}

export function useScheduleRuns(scheduleId: string | null) {
  const query = useQuery({
    queryKey: queryKeys.scheduleRuns(scheduleId ?? "", 20),
    queryFn: async ({ signal }) => {
      return await bffFetch<ScheduleRun[]>(`/api/v1/schedules/${scheduleId}/runs?limit=20`, { signal });
    },
    enabled: !!scheduleId,
    staleTime: 10_000,
    refetchInterval: 10_000,
    refetchOnWindowFocus: true,
  });

  const items = Array.isArray(query.data) ? query.data : [];
  const dataState: DataState = computeDataState(query.isLoading, query.isError, null, items.length > 0);

  return {
    runs: items,
    isLoading: query.isLoading,
    isError: query.isError,
    error: query.error,
    dataState,
    refetch: query.refetch,
  };
}

export function useScheduleLastRuns(scheduleIds: string[]) {
  const query = useQuery({
    queryKey: ["schedule-last-runs", ...scheduleIds.sort()],
    queryFn: async () => {
      const results: Record<string, { lastRunAt: string | null; status: string | null; runCount: number; failCount: number }> = {};
      await Promise.all(
        scheduleIds.map(async (id) => {
          try {
            const runs = await bffFetch<ScheduleRun[]>(`/api/v1/schedules/${id}/runs?limit=10`);
            const lastRun = runs[0] ?? null;
            results[id] = {
              lastRunAt: lastRun?.started_at ?? null,
              status: lastRun?.status ?? null,
              runCount: runs.length,
              failCount: runs.filter((r) => r.status === "failed").length,
            };
          } catch {
            results[id] = { lastRunAt: null, status: null, runCount: 0, failCount: 0 };
          }
        }),
      );
      return results;
    },
    staleTime: 5_000,
    refetchInterval: 5_000,
    refetchOnWindowFocus: true,
    enabled: scheduleIds.length > 0,
  });

  return {
    lastRuns: query.data ?? {},
    isLoading: query.isLoading,
  };
}

export type TriggerPhase = "idle" | "starting" | "running" | "completed" | "failed" | "timeout";

const STARTING_TIMEOUT_MS = 30_000;

export function useScheduleTrigger(scheduleId: string, description: string, items: ScheduleSummary[]) {
  const queryClient = useQueryClient();
  const [phase, setPhase] = useState<TriggerPhase>("idle");
  const lastRunAtRef = useRef<string | null>(null);
  const startedAtRef = useRef<number>(0);

  const schedule = items.find((s) => s.schedule_id === scheduleId);
  const runningCount = schedule?.running_workflows ?? 0;
  const currentLastRunAt = schedule?.last_run_at ?? null;

  useEffect(() => {
    if (phase === "idle") return;

    if (phase === "starting" && runningCount > 0) {
      setPhase("running");
    } else if (phase === "running" && runningCount === 0) {
      if (currentLastRunAt && currentLastRunAt !== lastRunAtRef.current) {
        const lastStatus = schedule?.last_run_status;
        setPhase(lastStatus === "failed" ? "failed" : "completed");
      }
    }
  }, [phase, runningCount, currentLastRunAt, schedule?.last_run_status]);

  useEffect(() => {
    if (phase !== "starting") return;
    const interval = setInterval(() => {
      if (Date.now() - startedAtRef.current > STARTING_TIMEOUT_MS) {
        setPhase("timeout");
        clearInterval(interval);
      }
    }, 1_000);
    return () => clearInterval(interval);
  }, [phase]);

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
      toast.warning(`Worker pode não estar rodando — ${description}`);
      const t = setTimeout(() => setPhase("idle"), 3000);
      return () => clearTimeout(t);
    }
  }, [phase, description]);

  const trigger = useCallback(async () => {
    const idempotencyKey = `trigger-${scheduleId}`;
    try {
      await bffFetch<{ schedule_id: string; message: string }>(
        `/api/v1/schedules/${scheduleId}/trigger`,
        { method: "POST", headers: { "Idempotency-Key": idempotencyKey } },
      );
      queryClient.invalidateQueries({ queryKey: queryKeys.schedules() });
      queryClient.invalidateQueries({ queryKey: queryKeys.scheduleRuns(scheduleId, 20) });

      lastRunAtRef.current = currentLastRunAt;
      startedAtRef.current = Date.now();
      setPhase("starting");
      toast.success(`Execução iniciada — ${description}`);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Erro desconhecido";
      toast.error(`Falha ao iniciar execução — ${description}: ${msg}`);
    }
  }, [scheduleId, description, currentLastRunAt, queryClient]);

  return { trigger, phase };
}
