"use client";

import { useQuery } from "@tanstack/react-query";

import type { DataState } from "@/components/domain";
import { institutionalApi, queryKeys } from "@/lib/api-client";
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
      const { data, error } = await institutionalApi.GET("/api/v1/quality/incidents", {
        params: { query: { limit: 250, offset: 0 } },
      });
      if (error) throw error;
      return data as { items?: Array<Record<string, unknown>> } | undefined;
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
  const dataState: DataState = computeDataState(query.isLoading, query.isError, null, incidents.length > 0);

  return {
    incidents,
    sources: [],
    healthySources: 0,
    staleSources: 0,
    neverSucceededSources: 0,
    totalSources: 0,
    openIncidents,
    isLoading: query.isLoading,
    isError: query.isError,
    error: query.error,
    dataState,
    refetch: query.refetch,
    count: incidents.length,
  };
}
