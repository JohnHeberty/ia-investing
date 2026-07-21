"use client";

import { useQuery } from "@tanstack/react-query";

import { institutionalApi, queryKeys } from "@/lib/api-client";

import type { DataState } from "@/components/domain";
import { computeDataState } from "@/lib/data-state";

export interface ResearchCaseSummary {
  id: string;
  title: string;
  state: string;
  case_type: string;
  priority: string;
  issuer_id: string;
  instrument_id: string | null;
  data_as_of: string;
  created_at: string;
  updated_at: string;
  due_at: string | null;
  created_by: string;
}

/** Fetch research cases. */
export function useResearchCases() {
  const query = useQuery({
    queryKey: queryKeys.researchCases(),
    queryFn: async () => {
      const { data, error } = await institutionalApi.GET("/api/v1/research/cases");
      if (error) throw error;
      return data ?? [];
    },
    staleTime: 60_000,
    refetchOnWindowFocus: false,
  });

  const cases: ResearchCaseSummary[] = Array.isArray(query.data)
    ? (query.data as Array<Record<string, unknown>>).map((c) => ({
        id: String(c.id ?? ""),
        title: String(c.title ?? ""),
        state: String(c.state ?? ""),
        case_type: String(c.case_type ?? ""),
        priority: String(c.priority ?? ""),
        issuer_id: String(c.issuer_id ?? ""),
        instrument_id: c.instrument_id ? String(c.instrument_id) : null,
        data_as_of: String(c.data_as_of ?? c.created_at ?? ""),
        created_at: String(c.created_at ?? ""),
        updated_at: String(c.updated_at ?? ""),
        due_at: c.due_at ? String(c.due_at) : null,
        created_by: String(c.created_by ?? ""),
      }))
    : [];

  const latestAsOf = cases.length > 0
    ? cases.reduce((latest, c) => {
        const d = new Date(c.data_as_of).getTime();
        return d > latest ? d : latest;
      }, 0)
    : null;

  const openCases = cases.filter((c) => c.state === "open" || c.state === "triaged").length;
  const researchCases = cases.filter((c) => c.state === "in_research").length;
  const readyForCommittee = cases.filter((c) => c.state === "ready_for_committee").length;

  const dataState: DataState = computeDataState(
    query.isLoading,
    query.isError,
    latestAsOf ? new Date(latestAsOf).toISOString() : null,
    cases.length > 0,
  );

  return {
    cases,
    openCases,
    researchCases,
    readyForCommittee,
    isLoading: query.isLoading,
    isError: query.isError,
    error: query.error,
    dataState,
    refetch: query.refetch,
    count: cases.length,
  };
}
