"use client";

import { useQuery } from "@tanstack/react-query";
import { bffFetch } from "@/lib/api-client";
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
  const macroQuery = useQuery({
    queryKey: ["macroIndicators"],
    queryFn: async () => {
      return await bffFetch<{
        indicators: Array<{
          id: string;
          indicator_name: string;
          source: string;
          value: number | null;
          unit: string | null;
          period_date: string | null;
          published_at: string | null;
        }>;
        selic: { value: number | null; source: string; period_date: string | null } | null;
        ipca: { value: number | null; source: string; period_date: string | null } | null;
        usd_brl: { value: number | null; source: string; period_date: string | null } | null;
        count: number;
      }>("/api/v1/risk/macro");
    },
    staleTime: 60_000,
    refetchOnWindowFocus: false,
  });

  const sourceHealthQuery = useQuery({
    queryKey: ["sourceHealth"],
    queryFn: async () => {
      return await bffFetch<Array<Record<string, unknown>>>("/api/v1/sources/health");
    },
    staleTime: 60_000,
    refetchOnWindowFocus: false,
  });

  const macroData = macroQuery.data;
  const sources = Array.isArray(sourceHealthQuery.data) ? sourceHealthQuery.data : [];

  const macroSeries: MacroSeries[] = macroData?.indicators?.map((ind) => ({
    id: ind.id,
    name: ind.indicator_name,
    value: ind.value !== null ? String(ind.value) : null,
    source: ind.source,
    status: ind.value !== null ? "ok" : "missing",
    lastUpdated: ind.published_at ?? ind.period_date,
    frequency: ind.unit ?? "—",
    unit: ind.unit ?? "",
  })) ?? [];

  const staleFromHealth = sources.filter(
    (s) => s.status === "stale" || s.status === "never_succeeded",
  ).length;

  const _find = (patterns: string[]): MacroSeries | undefined =>
    macroSeries.find((s) => {
      const n = s.name.toLowerCase();
      return patterns.some((p) => n.includes(p));
    });

  const selic = _find(["selic", "copom"]);
  const ipca = _find(["ipca", "inflação"]);
  const usdBrl = _find(["usd", "dólar", "usdbrl"]);

  const staleSeries = macroSeries.filter((s) => s.status === "stale").length +
    (staleFromHealth > 0 ? 1 : 0);
  const missingSeries = macroSeries.filter((s) => s.status === "missing").length;

  const latestAsOf = macroSeries.length > 0
    ? macroSeries
        .filter((s) => s.lastUpdated)
        .reduce((latest, s) => {
          const d = new Date(s.lastUpdated!).getTime();
          return d > latest ? d : latest;
        }, 0)
    : null;

  const dataState: DataState = computeDataState(
    macroQuery.isLoading,
    macroQuery.isError,
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
    isLoading: macroQuery.isLoading,
    isError: macroQuery.isError,
    error: macroQuery.error,
    dataState,
    refetch: macroQuery.refetch,
  };
}
