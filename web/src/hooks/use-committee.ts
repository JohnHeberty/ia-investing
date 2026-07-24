"use client";

import { useQuery } from "@tanstack/react-query";

import { institutionalApi, queryKeys } from "@/lib/api-client";

import type { DataState } from "@/components/domain";
import { computeDataState } from "@/lib/data-state";

export interface CommitteeDecision {
  id: string;
  title: string;
  description: string;
  status: "pending" | "approved" | "rejected" | "expired" | "conditional";
  requestedBy: string;
  requestedAt: string;
  decidedBy?: string;
  decidedAt?: string;
  reason?: string;
  conditions?: string[];
  quorumRequired: number;
  quorumCurrent: number;
  conflictsDeclared: number;
}

/** Fetch committee data from decision-packs endpoint. Falls back to agent runs for derivation. */
export function useCommittee() {
  const decisionPacksQuery = useQuery({
    queryKey: queryKeys.decisionPacks(),
    queryFn: async () => {
      return [] as Array<Record<string, unknown>>;
    },
    enabled: false,
    staleTime: 30_000,
    refetchOnWindowFocus: false,
  });

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

  const packs = Array.isArray(decisionPacksQuery.data)
    ? (decisionPacksQuery.data as Array<Record<string, unknown>>)
    : [];

  const runs = Array.isArray(agentRunsQuery.data)
    ? (agentRunsQuery.data as Array<Record<string, unknown>>)
    : [];

  // Derive committee decisions from decision packs and agent runs
  const decisions: CommitteeDecision[] = packs.map((p) => {
    const votes = Array.isArray(p.votes) ? p.votes : [];
    const approvedVotes = votes.filter(
      (v: Record<string, unknown>) => v.decision === "approve",
    ).length;
    const conflicts = votes.filter(
      (v: Record<string, unknown>) => v.conflict_declared === true,
    ).length;

    return {
      id: String(p.id ?? ""),
      title: String(p.title ?? p.case_title ?? "Decision pack"),
      description: String(p.description ?? p.summary ?? ""),
      status: (p.status as CommitteeDecision["status"]) ?? "pending",
      requestedBy: String(p.requested_by ?? p.author ?? ""),
      requestedAt: String(p.requested_at ?? p.created_at ?? ""),
      decidedBy: p.decided_by ? String(p.decided_by) : undefined,
      decidedAt: p.decided_at ? String(p.decided_at) : undefined,
      reason: p.reason ? String(p.reason) : undefined,
      conditions: Array.isArray(p.conditions)
        ? p.conditions.map(String)
        : undefined,
      quorumRequired: typeof p.quorum_required === "number" ? p.quorum_required : 3,
      quorumCurrent: approvedVotes,
      conflictsDeclared: conflicts,
    };
  });

  // If no decision packs, derive from recent agent runs awaiting approval
  if (decisions.length === 0) {
    const pendingRuns = runs.filter(
      (r) => r.status === "awaiting_approval" || r.status === "pending_review",
    );
    for (const run of pendingRuns.slice(0, 5)) {
      decisions.push({
        id: String(run.id ?? ""),
        title: `Agent run: ${String(run.agent_name ?? run.capability_id ?? "")}`,
        description: String(run.error_detail ?? "Aguardando aprovação do comitê."),
        status: "pending",
        requestedBy: String(run.agent_name ?? "agent"),
        requestedAt: String(run.created_at ?? ""),
        quorumRequired: 3,
        quorumCurrent: 0,
        conflictsDeclared: 0,
      });
    }
  }

  const pendingDecisions = decisions.filter((d) => d.status === "pending");
  const approvedToday = decisions.filter(
    (d) =>
      d.status === "approved" &&
      d.decidedAt &&
      new Date(d.decidedAt).toDateString() === new Date().toDateString(),
  );
  const totalConflicts = decisions.reduce((sum, d) => sum + d.conflictsDeclared, 0);

  // Quorum: max quorum required across all pending decisions
  const quorumRequired =
    pendingDecisions.length > 0
      ? Math.max(...pendingDecisions.map((d) => d.quorumRequired))
      : 3;
  const quorumCurrent =
    pendingDecisions.length > 0
      ? Math.max(...pendingDecisions.map((d) => d.quorumCurrent))
      : 0;

  const isLoading = decisionPacksQuery.isLoading || agentRunsQuery.isLoading;
  const isError = decisionPacksQuery.isError || agentRunsQuery.isError;

  const dataState: DataState = computeDataState(
    isLoading,
    isError,
    null,
    decisions.length > 0,
  );

  return {
    decisions,
    pendingDecisions,
    approvedToday,
    totalConflicts,
    quorumRequired,
    quorumCurrent,
    isLoading,
    isError,
    error: decisionPacksQuery.error ?? agentRunsQuery.error,
    dataState,
    refetch: () => {
      decisionPacksQuery.refetch();
      agentRunsQuery.refetch();
    },
    count: decisions.length,
  };
}
