"use client";

import { useQuery } from "@tanstack/react-query";

import { bffFetch, queryKeys } from "@/lib/api-client";

import type { DataState } from "@/components/domain";
import { computeDataState } from "@/lib/data-state";

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

export function useAgentRuns(params?: { status?: string }) {
  const query = useQuery({
    queryKey: queryKeys.agentRuns(params),
    queryFn: async () => {
      const qs = new URLSearchParams();
      if (params?.status) qs.set("status", params.status);
      const queryStr = qs.toString();
      return await bffFetch<Array<Record<string, unknown>>>(`/api/v1/agent-runs${queryStr ? `?${queryStr}` : ""}`);
    },
    staleTime: 30_000,
    refetchOnWindowFocus: false,
  });

  const runs: AgentRunSummary[] = Array.isArray(query.data)
    ? query.data.map((r) => ({
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
