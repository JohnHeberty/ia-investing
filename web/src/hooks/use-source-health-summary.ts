"use client";

import { useQuery } from "@tanstack/react-query";

import { bffFetch, queryKeys } from "@/lib/api-client";

import type { DataState } from "@/components/domain";
import { computeDataState } from "@/lib/data-state";

export interface SourceHealthSummary {
  snapshot_id: string;
  as_of: string | null;
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

export function useSourceHealthSummary() {
  const sourceHealthQuery = useQuery({
    queryKey: queryKeys.sourceHealth(),
    queryFn: async () => {
      return await bffFetch<Array<Record<string, unknown>>>("/api/v1/sources/health");
    },
    staleTime: 60_000,
    refetchOnWindowFocus: false,
  });

  const sources = Array.isArray(sourceHealthQuery.data) ? sourceHealthQuery.data : [];

  const staleCount = sources.filter(
    (s) => s.status === "stale" || s.status === "never_succeeded",
  ).length;
  const healthyCount = sources.filter((s) => s.status === "healthy").length;
  const totalSources = sources.length;

  const assessment: SourceHealthSummary = {
    snapshot_id: "latest",
    as_of: null,
    breaches: [],
    volatility: null,
    drawdown: null,
    concentration: { stale_sources: staleCount },
    liquidity: { healthy_sources: healthyCount },
  };

  const dataState: DataState = computeDataState(
    sourceHealthQuery.isLoading,
    sourceHealthQuery.isError,
    null,
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
