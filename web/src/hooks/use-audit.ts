"use client";

import { useQuery } from "@tanstack/react-query";

import type { DataState } from "@/components/domain";
import { institutionalApi, queryKeys } from "@/lib/api-client";
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
      const { data, error } = await institutionalApi.GET("/api/v1/audit/logs", {
        params: { query: { limit: 250, offset: 0 } },
      });
      if (error) throw error;
      return data as { items?: Array<Record<string, unknown>> } | undefined;
    },
    staleTime: 30_000,
    refetchOnWindowFocus: false,
  });
  const integrityQuery = useQuery({
    queryKey: ["audit-chain-verification"],
    queryFn: async () => {
      const { data, error } = await institutionalApi.GET("/api/v1/audit/verify");
      if (error) throw error;
      return data as { tampered_entries?: Array<Record<string, unknown>>; verified?: boolean } | undefined;
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

  const totalEvents = auditEvents.length;
  const correlatedEvents = auditEvents.filter((event) => event.correlationId).length;
  const overrides = auditEvents.filter((event) => event.type.includes("override") || event.type.includes("waiv")).length;
  const integrityFailures = auditEvents.filter((event) => event.integrity === "mismatch").length;
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
