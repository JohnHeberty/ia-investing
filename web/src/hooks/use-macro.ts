"use client";

import { useQuery } from "@tanstack/react-query";

import { bffFetch, queryKeys } from "@/lib/api-client";

import type { DataState } from "@/components/domain";
import { computeDataState } from "@/lib/data-state";

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

export function useMacro() {
  const sourceHealthQuery = useQuery({
    queryKey: queryKeys.sourceHealth(),
    queryFn: async () => {
      return await bffFetch<Array<Record<string, unknown>>>("/api/v1/sources/health");
    },
    staleTime: 60_000,
    refetchOnWindowFocus: false,
  });

  const sources = Array.isArray(sourceHealthQuery.data)
    ? sourceHealthQuery.data
    : [];

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
  } as {
    macroSeries: MacroSeries[];
    selic: MacroSeries | undefined;
    ipca: MacroSeries | undefined;
    usdBrl: MacroSeries | undefined;
    staleSeries: number;
    missingSeries: number;
    totalSeries: number;
    isLoading: boolean;
    isError: boolean;
    error: unknown;
    dataState: DataState;
    refetch: () => Promise<unknown>;
  };
}
