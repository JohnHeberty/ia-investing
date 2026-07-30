"use client";

import { useQuery } from "@tanstack/react-query";

import type { DataState } from "@/components/domain";
import { bffFetch, queryKeys } from "@/lib/api-client";
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

export function useAudit() {
  const logsQuery = useQuery({
    queryKey: queryKeys.auditLogs(),
    queryFn: async () => {
      return await bffFetch<{ items?: Array<Record<string, unknown>> }>("/api/v1/audit/logs?limit=250&offset=0");
    },
    staleTime: 30_000,
    refetchOnWindowFocus: false,
  });
  const integrityQuery = useQuery({
    queryKey: ["audit-chain-verification"],
    queryFn: async () => {
      return await bffFetch<{ tampered_entries?: Array<Record<string, unknown>>; verified?: boolean }>("/api/v1/audit/verify");
    },
    staleTime: 60_000,
    refetchOnWindowFocus: false,
  });

  const entries = Array.isArray(logsQuery.data?.items) ? logsQuery.data.items : [];
  const tamperedIds = new Set(
    (integrityQuery.data?.tampered_entries ?? []).map((item) => String(item.id ?? "")),
  );
  const auditEvents: AuditEvent[] = entries.map((entry) => ({
    id: String(entry.id ?? ""),
    type: String(entry.action ?? "unknown"),
    actor: String(entry.actor_id ?? "system"),
    target: `${String(entry.resource_type ?? "resource")}:${String(entry.resource_id ?? "")}`,
    version: String(entry.hash ?? ""),
    correlationId: String((entry.metadata as Record<string, unknown> | undefined)?.correlation_id ?? ""),
    timestamp: String(entry.timestamp ?? entry.created_at ?? ""),
    integrity: tamperedIds.has(String(entry.id ?? "")) ? "mismatch" : "ok",
  }));

  const { totalEvents, correlatedEvents, overrides, integrityFailures } = auditEvents.reduce(
    (acc, event) => {
      acc.totalEvents++;
      if (event.correlationId) acc.correlatedEvents++;
      if (event.type.includes("override") || event.type.includes("waiv")) acc.overrides++;
      if (event.integrity === "mismatch") acc.integrityFailures++;
      return acc;
    },
    { totalEvents: 0, correlatedEvents: 0, overrides: 0, integrityFailures: 0 },
  );
  const isLoading = logsQuery.isLoading || integrityQuery.isLoading;
  const isError = logsQuery.isError || integrityQuery.isError;
  const dataState: DataState = computeDataState(isLoading, isError, null, auditEvents.length > 0);

  return {
    auditEvents,
    totalEvents,
    correlatedEvents,
    correlationRate: totalEvents > 0 ? Math.round((correlatedEvents / totalEvents) * 100) : 0,
    overrides,
    integrityFailures,
    isLoading,
    isError,
    error: logsQuery.error ?? integrityQuery.error,
    dataState,
    refetch: () => {
      void logsQuery.refetch();
      void integrityQuery.refetch();
    },
  };
}
