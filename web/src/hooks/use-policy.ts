"use client";

import { useQuery } from "@tanstack/react-query";

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

export function usePolicy() {
  const policyEventsQuery = useQuery({
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

  const events = Array.isArray(policyEventsQuery.data) ? policyEventsQuery.data : [];

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
