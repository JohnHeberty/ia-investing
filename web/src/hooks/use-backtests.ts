"use client";

import { useCallback, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import type { DataState } from "@/components/domain";
import { bffFetch, queryKeys } from "@/lib/api-client";
import { computeDataState } from "@/lib/data-state";

const PAGE_SIZE = 50;

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
  const [page, setPage] = useState(0);
  const offset = page * PAGE_SIZE;

  const query = useQuery({
    queryKey: [...queryKeys.backtests(), { offset, limit: PAGE_SIZE }],
    queryFn: async () => {
      return await bffFetch<Array<Record<string, unknown>>>(
        `/api/v1/backtests?limit=${PAGE_SIZE}&offset=${offset}`,
      );
    },
    staleTime: 60_000,
    refetchOnWindowFocus: false,
  });

  const items = Array.isArray(query.data) ? query.data : [];
  const runs: BacktestRun[] = items.map((item) => {
    const results =
      item.results && typeof item.results === "object"
        ? (item.results as Record<string, unknown>)
        : {};
    const metrics =
      results.metrics && typeof results.metrics === "object"
        ? (results.metrics as Record<string, unknown>)
        : results;
    const checks =
      results.validation && typeof results.validation === "object"
        ? (results.validation as Record<string, unknown>)
        : {};
    return {
      id: String(item.id ?? ""),
      status: String(item.status ?? "unknown"),
      strategy: String(item.strategy_name ?? "—"),
      sharpeRatio: metrics.sharpe_ratio == null ? null : String(metrics.sharpe_ratio),
      pitGate:
        checks.point_in_time_verified === true
          ? "100%"
          : checks.point_in_time_verified === false
            ? "falhou"
            : "—",
      reproducibility: item.result_sha256 ? String(item.result_sha256).slice(0, 12) : "—",
      totalCost: metrics.total_cost == null ? "—" : String(metrics.total_cost),
      createdAt: String(item.created_at ?? ""),
    };
  });

  const completedRuns = runs.filter((run) => run.status === "succeeded").length;
  const pitGatePass = runs.length > 0 && runs.every((run) => run.pitGate === "100%");

  const latestAsOf =
    runs.length > 0
      ? runs.reduce((latest, r) => {
          const d = new Date(r.createdAt).getTime();
          return d > latest ? d : latest;
        }, 0)
      : null;

  const dataState: DataState = computeDataState(
    query.isLoading,
    query.isError,
    latestAsOf ? new Date(latestAsOf).toISOString() : null,
    runs.length > 0,
  );

  const hasMore = runs.length === PAGE_SIZE;
  const loadMore = useCallback(() => {
    if (hasMore && !query.isLoading) setPage((p) => p + 1);
  }, [hasMore, query.isLoading]);

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
    hasMore,
    loadMore,
    page,
  };
}
