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

export interface MacroSeries {
  id: string;
  name: string;
  value: string | null;
  source: string;
  status: "ok" | "stale" | "missing" | "error";
  lastUpdated: string | null;
  frequency: string;
  unit: string;
}

/** Fetch macro series from source health endpoint, deriving series data. */
export function useMacro() {
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

  // Derive macro series from source health data
  const macroSeries: MacroSeries[] = sources.map((s) => {
    const status = s.status === "healthy" ? "ok" : s.status === "stale" ? "stale" : "missing";
    const lastSuccess = s.last_success_at ? String(s.last_success_at) : null;

    return {
      id: String(s.code ?? s.id ?? ""),
      name: String(s.name ?? s.code ?? ""),
      value: status === "ok" ? (s.last_value ? String(s.last_value) : null) : null,
      source: String(s.provider ?? s.source ?? ""),
      status: status as MacroSeries["status"],
      lastUpdated: lastSuccess,
      frequency: String(s.frequency ?? "diária"),
      unit: String(s.unit ?? ""),
    };
  });

  // Identify key macro indicators
  const selic = macroSeries.find(
    (s) => s.id.includes("selic") || s.name.toLowerCase().includes("selic"),
  );
  const ipca = macroSeries.find(
    (s) => s.id.includes("ipca") || s.name.toLowerCase().includes("ipca"),
  );
  const usdBrl = macroSeries.find(
    (s) => s.id.includes("usd") || s.name.toLowerCase().includes("dólar"),
  );

  const staleSeries = macroSeries.filter((s) => s.status === "stale").length;
  const missingSeries = macroSeries.filter((s) => s.status === "missing").length;

  const latestAsOf =
    macroSeries.length > 0
      ? macroSeries
          .filter((s) => s.lastUpdated)
          .reduce((latest, s) => {
            const d = new Date(s.lastUpdated!).getTime();
            return d > latest ? d : latest;
          }, 0)
      : null;

  const dataState: DataState = computeDataState(
    sourceHealthQuery.isLoading,
    sourceHealthQuery.isError,
    latestAsOf ? new Date(latestAsOf).toISOString() : null,
    macroSeries.length > 0,
  );

  return {
    macroSeries,
    selic,
    ipca,
    usdBrl,
    staleSeries,
    missingSeries,
    totalSeries: macroSeries.length,
    isLoading: sourceHealthQuery.isLoading,
    isError: sourceHealthQuery.isError,
    error: sourceHealthQuery.error,
    dataState,
    refetch: sourceHealthQuery.refetch,
  };
}
