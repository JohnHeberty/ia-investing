"use client";

import { useQuery } from "@tanstack/react-query";

import { bffFetch } from "@/lib/api-client";

export interface AuditLogEntry {
  id: string;
  tenant_id: string;
  actor_id: string | null;
  action: string;
  resource_type: string;
  resource_id: string | null;
  changes: Record<string, unknown> | null;
  metadata: Record<string, unknown>;
  hash_prev: string | null;
  hash: string;
  timestamp: string;
  created_at: string;
}

export function useAuditLogs(resourceType: string, resourceId: string | null) {
  const query = useQuery({
    queryKey: ["auditLogs", resourceType, resourceId],
    queryFn: async () => {
      if (!resourceId) return { items: [], total: 0 };
      const params = new URLSearchParams({
        resource_id: resourceId,
        limit: "50",
      });
      const data = await bffFetch<{ items?: AuditLogEntry[]; total?: number }>(`/api/v1/audit/logs?${params}`);
      return { items: (data.items ?? []) as AuditLogEntry[], total: data.total ?? 0 };
    },
    enabled: !!resourceId,
    staleTime: 30_000,
  });

  return {
    entries: query.data?.items ?? [],
    total: query.data?.total ?? 0,
    isLoading: query.isLoading,
    isError: query.isError,
  };
}
