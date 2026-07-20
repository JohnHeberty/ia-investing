"use client";

import { useQuery } from "@tanstack/react-query";

import { institutionalApi, queryKeys } from "@/lib/api-client";

import type { DataState } from "@/components/domain";

/** Calculate data state from query status and data freshness. */
function computeDataState(
  isLoading: boolean,
  isError: boolean,
  asOf?: string | null,
  hasData?: boolean,
): DataState {
  if (isLoading) return "empty";
  if (isError) return "error";
  if (!hasData) return "missing";
  if (asOf) {
    const ageMs = Date.now() - new Date(asOf).getTime();
    if (ageMs > 60 * 60 * 1000) return "stale";
  }
  return "empty";
}

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

/** Fetch policy events from policy/events endpoint. */
export function usePolicy() {
  const policyEventsQuery = useQuery({
    queryKey: queryKeys.policyEvents(),
    queryFn: async () => {
      const { data, error } = await institutionalApi.GET("/api/v1/policy/events", {
        params: { query: { as_of: new Date().toISOString().slice(0, 10) } },
      });
      if (error) throw error;
      return data ?? [];
    },
    staleTime: 60_000,
    refetchOnWindowFocus: false,
  });

  const events = Array.isArray(policyEventsQuery.data)
    ? (policyEventsQuery.data as Array<Record<string, unknown>>)
    : [];

  const policyEvents: PolicyEvent[] = events.map((e) => ({
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
  }));

  const latestAsOf =
    policyEvents.length > 0
      ? policyEvents.reduce((latest, e) => {
          const d = new Date(e.updated_at).getTime();
          return d > latest ? d : latest;
        }, 0)
      : null;

  const materialEvents = policyEvents.filter(
    (e) => e.control === "Revisão humana" || e.control === "Pausado",
  );
  const monitoredObjects = new Set(policyEvents.map((e) => e.object_id)).size;
  const staleSources = policyEvents.filter(
    (e) => e.control === "Stale" || e.control === "Desatualizado",
  ).length;

  const dataState: DataState = computeDataState(
    policyEventsQuery.isLoading,
    policyEventsQuery.isError,
    latestAsOf ? new Date(latestAsOf).toISOString() : null,
    policyEvents.length > 0,
  );

  return {
    policyEvents,
    materialEvents,
    monitoredObjects,
    staleSources,
    isLoading: policyEventsQuery.isLoading,
    isError: policyEventsQuery.isError,
    error: policyEventsQuery.error,
    dataState,
    refetch: policyEventsQuery.refetch,
    count: policyEvents.length,
  };
}
