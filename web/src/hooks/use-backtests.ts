"use client";

import { useQuery } from "@tanstack/react-query";

import type { DataState } from "@/components/domain";
import { institutionalApi, queryKeys } from "@/lib/api-client";
import { computeDataState } from "@/lib/data-state";

export interface BacktestRun {
  id: string;
  status: string;
  strategy: string;
  sharpeRatio: string | null;
  pitGate: string;
  reproducibility: string;
  totalCost: string;
  createdAt: string;
}

export function useBacktests() {
  const query = useQuery({
    queryKey: queryKeys.backtests(),
    queryFn: async () => {
      const { data, error } = await institutionalApi.GET("/api/v1/backtests", {
        params: { query: { limit: 100, offset: 0 } },
      });
      if (error) throw error;
      return data as { items?: Array<Record<string, unknown>> } | undefined;
    },
    staleTime: 60_000,
    refetchOnWindowFocus: false,
  });

  const items = Array.isArray(query.data?.items) ? query.data.items : [];
  const runs: BacktestRun[] = items.map((item) => {
    const results = item.results && typeof item.results === "object" ? item.results as Record<string, unknown> : {};
    const metrics = results.metrics && typeof results.metrics === "object" ? results.metrics as Record<string, unknown> : results;
    const checks = results.validation && typeof results.validation === "object" ? results.validation as Record<string, unknown> : {};
    return {
      id: String(item.id ?? ""),
      status: String(item.status ?? "unknown"),
      strategy: String(item.strategy_name ?? "—"),
      sharpeRatio: metrics.sharpe_ratio == null ? null : String(metrics.sharpe_ratio),
      pitGate: checks.point_in_time_verified === true ? "100%" : checks.point_in_time_verified === false ? "falhou" : "—",
      reproducibility: item.result_sha256 ? String(item.result_sha256).slice(0, 12) : "—",
      totalCost: metrics.total_cost == null ? "—" : String(metrics.total_cost),
      createdAt: String(item.created_at ?? ""),
    };
  });

  const completedRuns = runs.filter((run) => run.status === "succeeded").length;
  const pitGatePass = runs.length > 0 && runs.every((run) => run.pitGate === "100%");
  const dataState: DataState = computeDataState(query.isLoading, query.isError, null, runs.length > 0);

  return {
    runs,
    completedRuns,
    pitGatePass,
    isLoading: query.isLoading,
    isError: query.isError,
    error: query.error,
    dataState,
    refetch: query.refetch,
    count: runs.length,
  };
}
