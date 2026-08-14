"use client";

import { createContext, useContext } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { bffFetch, queryKeys } from "@/lib/api-client";
import type { DataState } from "@/components/domain";
import { computeDataState } from "@/lib/data-state";

export interface PolicyEvent {
  id: string;
  title: string;
  stage: string;
  probability: string;
  exposure: string;
  control: string;
  object_id: string;
  object_name: string;
  sector: string;
  updated_at: string;
}

export interface PolicyAlert {
  id: string;
  policy_object_id: string;
  alert_type: string;
  severity: string;
  title: string;
  description: string | null;
  fired_at: string;
  acknowledged_at: string | null;
  resolved_at: string | null;
}

export interface PolicyForecast {
  id: string;
  policy_object_id: string;
  target_outcome: string;
  probability: number;
  interval_low: number | null;
  interval_high: number | null;
}

export interface PolicySource {
  id: string;
  name: string;
  authority: string;
  source_type: string | null;
  url_pattern: string | null;
  is_active: boolean | null;
  last_fetched_at: string | null;
  last_fetch_error: string | null;
  last_fetch_error_at: string | null;
}

export interface PolicyDataValue {
  events: PolicyEvent[];
  alerts: PolicyAlert[];
  forecasts: PolicyForecast[];
  sources: PolicySource[];
  materialEvents: PolicyEvent[];
  monitoredObjects: number;
  staleSources: number;
  activeAlerts: number;
  isLoading: boolean;
  isError: boolean;
  error: unknown;
  dataState: DataState;
  refetch: () => Promise<unknown>;
}

export const PolicyDataContext = createContext<PolicyDataValue | null>(null);

export function usePolicyData(): PolicyDataValue {
  const ctx = useContext(PolicyDataContext);
  if (!ctx) throw new Error("usePolicyData must be inside PolicyDataProvider");
  return ctx;
}

function usePolicyQueries() {
  const eventsQuery = useQuery({
    queryKey: queryKeys.policyEvents(),
    queryFn: async () => {
      const asOf = new Date().toISOString();
      return await bffFetch<Array<Record<string, unknown>>>(
        `/api/v1/policy/events?as_of=${encodeURIComponent(asOf)}`,
      );
    },
    staleTime: 60_000,
    refetchOnWindowFocus: false,
  });

  const alertsQuery = useQuery({
    queryKey: queryKeys.policyAlerts(),
    queryFn: () => bffFetch<PolicyAlert[]>("/api/v1/policy/alerts"),
    staleTime: 30_000,
    refetchOnWindowFocus: false,
  });

  const forecastsQuery = useQuery({
    queryKey: queryKeys.policyForecasts(),
    queryFn: () => bffFetch<PolicyForecast[]>("/api/v1/policy/forecasts"),
    staleTime: 30_000,
    refetchOnWindowFocus: false,
  });

  const sourcesQuery = useQuery({
    queryKey: queryKeys.policySources(),
    queryFn: () => bffFetch<PolicySource[]>("/api/v1/policy/sources"),
    staleTime: 60_000,
    refetchOnWindowFocus: false,
  });

  return { eventsQuery, alertsQuery, forecastsQuery, sourcesQuery };
}

function normalizeEvent(e: Record<string, unknown>): PolicyEvent {
  return {
    id: String(e.id ?? ""),
    title: String(e.title ?? e.object_name ?? ""),
    stage: String(e.stage ?? e.legal_stage ?? ""),
    probability: String(e.probability ?? "—"),
    exposure: String(e.exposure ?? e.sector ?? ""),
    control: String(e.control ?? e.status ?? "Monitorar"),
    object_id: String(e.object_id ?? e.policy_object_id ?? ""),
    object_name: String(e.object_name ?? ""),
    sector: String(e.sector ?? ""),
    updated_at: String(e.updated_at ?? e.created_at ?? ""),
  };
}

export function usePolicyValue(): PolicyDataValue {
  const { eventsQuery, alertsQuery, forecastsQuery, sourcesQuery } = usePolicyQueries();

  const rawEvents = Array.isArray(eventsQuery.data) ? eventsQuery.data : [];
  const events = rawEvents.map(normalizeEvent);
  const alerts = alertsQuery.data ?? [];
  const forecasts = forecastsQuery.data ?? [];
  const sources = sourcesQuery.data ?? [];

  const materialEvents = events.filter(
    (e) => e.control === "Revisão humana" || e.control === "Pausado",
  );
  const monitoredObjects = new Set(events.map((e) => e.object_id)).size;
  const staleSources = events.filter(
    (e) => e.control === "Stale" || e.control === "Desatualizado",
  ).length;
  const activeAlerts = alerts.filter((a) => !a.resolved_at).length;

  const latestAsOf =
    events.length > 0
      ? events.reduce((latest, e) => {
          const d = new Date(e.updated_at).getTime();
          return d > latest ? d : latest;
        }, 0)
      : null;

  const isLoading =
    eventsQuery.isLoading || alertsQuery.isLoading || forecastsQuery.isLoading || sourcesQuery.isLoading;
  const isError =
    eventsQuery.isError || alertsQuery.isError || forecastsQuery.isError || sourcesQuery.isError;
  const dataState: DataState = computeDataState(
    isLoading,
    isError,
    latestAsOf ? new Date(latestAsOf).toISOString() : null,
    events.length > 0,
  );

  return {
    events,
    alerts,
    forecasts,
    sources,
    materialEvents,
    monitoredObjects,
    staleSources,
    activeAlerts,
    isLoading,
    isError,
    error: eventsQuery.error ?? alertsQuery.error ?? forecastsQuery.error ?? sourcesQuery.error,
    dataState,
    refetch: () =>
      Promise.all([
        eventsQuery.refetch(),
        alertsQuery.refetch(),
        forecastsQuery.refetch(),
        sourcesQuery.refetch(),
      ]),
  };
}

export function useAlertMutations() {
  const queryClient = useQueryClient();

  const invalidate = () => queryClient.invalidateQueries({ queryKey: queryKeys.policyAlerts() });

  const acknowledge = useMutation({
    mutationFn: (alertId: string) =>
      bffFetch(`/api/v1/policy/alerts/${alertId}/acknowledge`, { method: "POST" }),
    onSuccess: invalidate,
    onError: (error: Error) => {
      console.error("Failed to acknowledge alert:", error.message);
    },
  });

  const resolve = useMutation({
    mutationFn: ({ alertId, notes }: { alertId: string; notes: string }) =>
      bffFetch(`/api/v1/policy/alerts/${alertId}/resolve`, {
        method: "POST",
        body: JSON.stringify({ notes }),
      }),
    onSuccess: invalidate,
    onError: (error: Error) => {
      console.error("Failed to resolve alert:", error.message);
    },
  });

  return { acknowledge, resolve };
}

export function useSourceMutations() {
  const queryClient = useQueryClient();

  const invalidate = () => queryClient.invalidateQueries({ queryKey: queryKeys.policySources() });

  const createMutation = useMutation({
    mutationFn: (data: {
      name: string;
      authority?: string;
      source_type?: string;
      url_pattern?: string;
    }) =>
      bffFetch<PolicySource>("/api/v1/policy/sources", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...data, authority: data.authority ?? "camara" }),
      }),
    onSuccess: invalidate,
    onError: (error: Error) => {
      toast.error(`Falha ao criar fonte: ${error.message}`);
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({
      id,
      ...data
    }: {
      id: string;
      name?: string;
      source_type?: string;
      url_pattern?: string;
      is_active?: boolean;
    }) =>
      bffFetch<PolicySource>(`/api/v1/policy/sources/${id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      }),
    onSuccess: invalidate,
    onError: (error: Error) => {
      toast.error(`Falha ao atualizar fonte: ${error.message}`);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) =>
      bffFetch<void>(`/api/v1/policy/sources/${id}`, { method: "DELETE" }),
    onSuccess: invalidate,
    onError: (error: Error) => {
      toast.error(`Falha ao remover: ${error.message}`);
    },
  });

  return { createMutation, updateMutation, deleteMutation };
}

export function usePolicy(): ReturnType<typeof usePolicyValue> {
  if (process.env.NODE_ENV === "development") {
    console.warn("usePolicy() is deprecated. Use usePolicyData() inside PolicyDataProvider instead.");
  }
  return usePolicyValue();
}
