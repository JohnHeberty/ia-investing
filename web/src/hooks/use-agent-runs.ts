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

export interface AgentRunSummary {
  id: string;
  status: string;
  agent_name?: string;
  capability_id: string;
  created_at: string;
  data_as_of: string;
  duration_ms: number | null;
  cost_usd: string;
  prompt_tokens: number;
  completion_tokens: number;
  error_code: string | null;
  error_detail: string | null;
  trace_id: string;
  evidence_coverage: string | null;
}

/** Fetch agent runs from agents/runs endpoint. */
export function useAgentRuns(params?: { status?: string; agent_name?: string }) {
  const query = useQuery({
    queryKey: queryKeys.agentRuns(params),
    queryFn: async () => {
      const { data, error } = await institutionalApi.GET("/api/v1/agents/runs", {
        params: {
          query: {
            status: params?.status ?? undefined,
            agent_name: params?.agent_name ?? undefined,
          },
        },
      });
      if (error) throw error;
      return data ?? [];
    },
    staleTime: 30_000,
    refetchOnWindowFocus: false,
  });

  const runs: AgentRunSummary[] = Array.isArray(query.data)
    ? (query.data as Array<Record<string, unknown>>).map((r) => ({
        id: String(r.id ?? ""),
        status: String(r.status ?? "unknown"),
        agent_name: r.agent_name ? String(r.agent_name) : undefined,
        capability_id: String(r.capability_id ?? ""),
        created_at: String(r.created_at ?? ""),
        data_as_of: String(r.data_as_of ?? r.created_at ?? ""),
        duration_ms: typeof r.duration_ms === "number" ? r.duration_ms : null,
        cost_usd: String(r.cost_usd ?? "0"),
        prompt_tokens: typeof r.prompt_tokens === "number" ? r.prompt_tokens : 0,
        completion_tokens: typeof r.completion_tokens === "number" ? r.completion_tokens : 0,
        error_code: r.error_code ? String(r.error_code) : null,
        error_detail: r.error_detail ? String(r.error_detail) : null,
        trace_id: String(r.trace_id ?? ""),
        evidence_coverage: r.evidence_coverage ? String(r.evidence_coverage) : null,
      }))
    : [];

  const latestAsOf = runs.length > 0
    ? runs.reduce((latest, r) => {
        const d = new Date(r.created_at).getTime();
        return d > latest ? d : latest;
      }, 0)
    : null;

  const completedRuns = runs.filter((r) => r.status === "succeeded").length;
  const failedRuns = runs.filter((r) => r.status === "failed").length;
  const totalCost = runs.reduce((sum, r) => sum + (parseFloat(r.cost_usd) || 0), 0);

  const dataState: DataState = computeDataState(
    query.isLoading,
    query.isError,
    latestAsOf ? new Date(latestAsOf).toISOString() : null,
    runs.length > 0,
  );

  return {
    runs,
    completedRuns,
    failedRuns,
    totalCost,
    isLoading: query.isLoading,
    isError: query.isError,
    error: query.error,
    dataState,
    refetch: query.refetch,
    count: runs.length,
  };
}
