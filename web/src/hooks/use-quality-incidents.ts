"use client";

import { useQuery } from "@tanstack/react-query";

import type { DataState } from "@/components/domain";
import { bffFetch, queryKeys } from "@/lib/api-client";
import { computeDataState } from "@/lib/data-state";

export interface QualityIncidentSummary {
  id: string;
  severity: string;
  status: string;
  impact_summary: string;
  owner_role: string;
  created_at: string;
  updated_at: string;
  resolution_notes: string | null;
  waiver_reason: string | null;
  waiver_expires_at: string | null;
}

export function useQualityIncidents() {
  const query = useQuery({
    queryKey: queryKeys.qualityIncidents(),
    queryFn: async () => {
      return await bffFetch<{ items?: Array<Record<string, unknown>> }>("/api/v1/quality/incidents?limit=250&offset=0");
    },
    staleTime: 60_000,
    refetchOnWindowFocus: false,
  });

  const sourceHealthQuery = useQuery({
    queryKey: queryKeys.sourceHealth(),
    queryFn: async () => {
      return await bffFetch<Array<Record<string, unknown>>>("/api/v1/sources/health");
    },
    staleTime: 60_000,
    refetchOnWindowFocus: false,
  });

  const raw = Array.isArray(query.data?.items) ? query.data.items : [];
  const incidents: QualityIncidentSummary[] = raw.map((item) => ({
    id: String(item.id ?? ""),
    severity: String(item.severity ?? "unknown"),
    status: String(item.status ?? "unknown"),
    impact_summary: String(item.impact_summary ?? ""),
    owner_role: String(item.owner_role ?? ""),
    created_at: String(item.created_at ?? ""),
    updated_at: String(item.updated_at ?? item.created_at ?? ""),
    resolution_notes: item.resolution_notes ? String(item.resolution_notes) : null,
    waiver_reason: item.waiver_reason ? String(item.waiver_reason) : null,
    waiver_expires_at: item.waiver_expires_at ? String(item.waiver_expires_at) : null,
  }));
  const openIncidents = incidents.filter((incident) => ["open", "acknowledged"].includes(incident.status));

  const sources = Array.isArray(sourceHealthQuery.data)
    ? sourceHealthQuery.data
    : [];
  const healthySources = sources.filter((s) => s.status === "healthy").length;
  const staleSources = sources.filter((s) => s.status === "stale").length;
  const neverSucceededSources = sources.filter((s) => s.status === "never_succeeded").length;

  const dataState: DataState = computeDataState(query.isLoading, query.isError, null, incidents.length > 0);

  return {
    incidents,
    sources,
    healthySources,
    staleSources,
    neverSucceededSources,
    totalSources: sources.length,
    openIncidents,
    isLoading: query.isLoading || sourceHealthQuery.isLoading, // NOTE: consumers may want to check query.isLoading and sourceHealthQuery.isLoading separately for granular loading states
    isError: query.isError || sourceHealthQuery.isError,
    error: query.error ?? sourceHealthQuery.error,
    dataState,
    refetch: query.refetch,
    count: incidents.length,
  };
}
