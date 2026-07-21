"use client";

import { useQuery } from "@tanstack/react-query";

import { institutionalApi, queryKeys } from "@/lib/api-client";

import type { DataState } from "@/components/domain";
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

/** Fetch quality incidents. Falls back to source health data if endpoint unavailable. */
export function useQualityIncidents() {
  const sourceHealthQuery = useQuery({
    queryKey: queryKeys.sourceHealth(),
    queryFn: async () => {
      const { data, error } = await institutionalApi.GET("/api/v1/sources/health");
      if (error) throw error;
      return data ?? [];
    },
    staleTime: 60_000,
    refetchOnWindowFocus: false,
  });

  const sources = Array.isArray(sourceHealthQuery.data)
    ? (sourceHealthQuery.data as Array<Record<string, unknown>>)
    : [];

  // Derive quality metrics from source health data
  const healthySources = sources.filter((s) => s.status === "healthy").length;
  const staleSources = sources.filter((s) => s.status === "stale").length;
  const neverSucceededSources = sources.filter((s) => s.status === "never_succeeded").length;
  const totalSources = sources.length;

  // Build synthetic incidents from source health data
  const incidents: QualityIncidentSummary[] = sources
    .filter((s) => s.status === "stale" || s.status === "never_succeeded")
    .map((s) => ({
      id: `src-${String(s.code ?? "")}`,
      severity: s.status === "never_succeeded" ? "high" : "medium",
      status: "open",
      impact_summary: `Fonte ${String(s.name ?? s.code ?? "")} ${s.status === "stale" ? "desatualizada" : "nunca retornou sucesso"}`,
      owner_role: String(s.owner_role ?? ""),
      created_at: String(s.last_failure_at ?? new Date().toISOString()),
      updated_at: String(s.last_failure_at ?? new Date().toISOString()),
      resolution_notes: null,
      waiver_reason: null,
      waiver_expires_at: null,
    }));

  const dataState: DataState = computeDataState(
    sourceHealthQuery.isLoading,
    sourceHealthQuery.isError,
    sources.length > 0,
  );

  return {
    incidents,
    sources,
    healthySources,
    staleSources,
    neverSucceededSources,
    totalSources,
    isLoading: sourceHealthQuery.isLoading,
    isError: sourceHealthQuery.isError,
    error: sourceHealthQuery.error,
    dataState,
    refetch: sourceHealthQuery.refetch,
    count: incidents.length,
  };
}
