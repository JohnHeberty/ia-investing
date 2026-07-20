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

export interface RiskAssessmentSummary {
  snapshot_id: string;
  as_of: string;
  breaches: Array<{
    id: string;
    limit_name: string;
    limit_type: string;
    limit_value: string;
    observed_value: string;
    status: string;
  }>;
  volatility: string | null;
  drawdown: string | null;
  concentration: Record<string, unknown>;
  liquidity: Record<string, unknown>;
}

/** Fetch risk data. Uses source health as a proxy for risk status. */
export function useRiskAssessments() {
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

  const staleCount = sources.filter(
    (s) => s.status === "stale" || s.status === "never_succeeded",
  ).length;
  const healthyCount = sources.filter((s) => s.status === "healthy").length;
  const totalSources = sources.length;

  // Build risk summary from source health data
  const assessment: RiskAssessmentSummary = {
    snapshot_id: "latest",
    as_of: new Date().toISOString(),
    breaches: [],
    volatility: null,
    drawdown: null,
    concentration: { stale_sources: staleCount },
    liquidity: { healthy_sources: healthyCount },
  };

  const dataState: DataState = computeDataState(
    sourceHealthQuery.isLoading,
    sourceHealthQuery.isError,
    new Date().toISOString(),
    sources.length > 0,
  );

  return {
    assessment,
    assessments: [assessment],
    sources,
    staleCount,
    healthyCount,
    totalSources,
    isLoading: sourceHealthQuery.isLoading,
    isError: sourceHealthQuery.isError,
    error: sourceHealthQuery.error,
    dataState,
    refetch: sourceHealthQuery.refetch,
  };
}
