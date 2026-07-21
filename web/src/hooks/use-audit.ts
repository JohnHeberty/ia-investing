"use client";

import { useQuery } from "@tanstack/react-query";

import { institutionalApi, queryKeys } from "@/lib/api-client";

import type { DataState } from "@/components/domain";
import { computeDataState } from "@/lib/data-state";

export interface AuditEvent {
  id: string;
  type: string;
  actor: string;
  target: string;
  version: string;
  correlationId: string;
  timestamp: string;
  integrity: "ok" | "mismatch";
}

/** Fetch audit trail data from agent runs and source health as proxy. */
export function useAudit() {
  const agentRunsQuery = useQuery({
    queryKey: queryKeys.agentRuns(),
    queryFn: async () => {
      const { data, error } = await institutionalApi.GET("/api/v1/agents/runs");
      if (error) throw error;
      return data ?? [];
    },
    staleTime: 30_000,
    refetchOnWindowFocus: false,
  });

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

  const runs = Array.isArray(agentRunsQuery.data)
    ? (agentRunsQuery.data as Array<Record<string, unknown>>)
    : [];

  const sources = Array.isArray(sourceHealthQuery.data)
    ? (sourceHealthQuery.data as Array<Record<string, unknown>>)
    : [];

  // Build audit events from agent runs
  const auditEvents: AuditEvent[] = runs.map((r) => ({
    id: String(r.id ?? ""),
    type: String(r.status ?? "unknown"),
    actor: String(r.agent_name ?? r.capability_id ?? "agent"),
    target: String(r.capability_id ?? ""),
    version: String(r.trace_id ?? ""),
    correlationId: String(r.trace_id ?? ""),
    timestamp: String(r.created_at ?? ""),
    integrity: "ok" as const,
  }));

  // Add source health events
  for (const s of sources) {
    if (s.status === "stale" || s.status === "never_succeeded") {
      auditEvents.push({
        id: `src-${String(s.code ?? "")}`,
        type: "source_health",
        actor: String(s.provider ?? s.code ?? ""),
        target: String(s.name ?? s.code ?? ""),
        version: "",
        correlationId: String(s.code ?? ""),
        timestamp: String(s.last_failure_at ?? new Date().toISOString()),
        integrity: s.status === "never_succeeded" ? "mismatch" : "ok",
      });
    }
  }

  // Sort by timestamp descending
  auditEvents.sort(
    (a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime(),
  );

  const totalEvents = auditEvents.length;
  const correlatedEvents = auditEvents.filter((e) => e.correlationId).length;
  const overrides = auditEvents.filter(
    (e) => e.type === "override" || e.type === "manual",
  ).length;
  const integrityFailures = auditEvents.filter(
    (e) => e.integrity === "mismatch",
  ).length;

  const isLoading = agentRunsQuery.isLoading || sourceHealthQuery.isLoading;
  const isError = agentRunsQuery.isError || sourceHealthQuery.isError;

  const dataState: DataState = computeDataState(
    isLoading,
    isError,
    auditEvents.length > 0,
  );

  return {
    auditEvents,
    totalEvents,
    correlatedEvents,
    correlationRate: totalEvents > 0 ? Math.round((correlatedEvents / totalEvents) * 100) : 0,
    overrides,
    integrityFailures,
    isLoading,
    isError,
    error: agentRunsQuery.error ?? sourceHealthQuery.error,
    dataState,
    refetch: () => {
      agentRunsQuery.refetch();
      sourceHealthQuery.refetch();
    },
  };
}
