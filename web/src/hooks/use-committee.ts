"use client";

import { useQuery } from "@tanstack/react-query";

import type { DataState } from "@/components/domain";
import { institutionalApi, queryKeys } from "@/lib/api-client";
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

interface CommitteeSessionListItem {
  id: string;
  state: string;
  scheduled_at?: string | null;
  total_members: number;
  present_members: number;
  created_at?: string | null;
}

interface CommitteeSessionList {
  items: CommitteeSessionListItem[];
  total: number;
}

interface CommitteeSessionDetail extends CommitteeSessionListItem {
  thesis_ids?: string[];
  agenda?: Record<string, unknown>;
  decision?: string | null;
  rationale?: string | null;
  published_at?: string | null;
  votes_in_favor?: number;
  votes_against?: number;
  votes?: Array<Record<string, unknown>>;
}

function mapStatus(session: CommitteeSessionDetail): CommitteeDecision["status"] {
  if (!["published", "archived"].includes(session.state)) return "pending";
  const decision = (session.decision ?? "").toLowerCase();
  if (decision.includes("condition")) return "conditional";
  if (["approve", "approved", "add", "increase", "maintain"].includes(decision)) return "approved";
  if (["reject", "rejected", "exit", "remove"].includes(decision)) return "rejected";
  return "pending";
}

function proposalTitle(session: CommitteeSessionDetail): string {
  const title = session.agenda?.title ?? session.agenda?.case_title ?? session.agenda?.proposal_title;
  if (typeof title === "string" && title.trim()) return title;
  const thesisCount = Array.isArray(session.thesis_ids) ? session.thesis_ids.length : 0;
  return thesisCount > 0 ? `Comitê — ${thesisCount} tese${thesisCount === 1 ? "" : "s"}` : "Sessão do comitê";
}

async function batchFetchDetails(
  sessions: CommitteeSessionListItem[],
  signal: AbortSignal,
): Promise<CommitteeSessionDetail[]> {
  const results: CommitteeSessionDetail[] = [];
  const concurrency = 5;
  for (let i = 0; i < sessions.length; i += concurrency) {
    if (signal.aborted) throw new DOMException("Aborted", "AbortError");
    const batch = sessions.slice(i, i + concurrency);
    const settled = await Promise.allSettled(
      batch.map(async (session) => {
        const { data, error } = await institutionalApi.GET<CommitteeSessionDetail>(
          "/api/v1/committee/sessions/{session_id}",
          { params: { path: { session_id: session.id }, signal } },
        );
        if (error) throw error;
        return data ?? session;
      }),
    );
    for (const result of settled) {
      if (result.status === "fulfilled") {
        results.push(result.value);
      }
    }
  }
  return results;
}

export function useCommittee() {
  const sessionsQuery = useQuery({
    queryKey: queryKeys.committeeSessions(),
    queryFn: async () => {
      const { data, error } = await institutionalApi.GET<CommitteeSessionList>("/api/v1/committee/sessions", {
        params: { query: { limit: 50, offset: 0 } },
      });
      if (error) throw error;
      return data?.items ?? [];
    },
    staleTime: 30_000,
    refetchOnWindowFocus: false,
  });

  const detailsQuery = useQuery({
    queryKey: [...queryKeys.committeeSessions(), "details", sessionsQuery.data?.map((s) => s.id).join(",") ?? ""],
    enabled: Boolean(sessionsQuery.data),
    queryFn: async ({ signal }) => {
      const sessions = sessionsQuery.data ?? [];
      return batchFetchDetails(sessions, signal);
    },
    staleTime: 30_000,
    refetchOnWindowFocus: false,
  });

  const sessions = detailsQuery.data ?? sessionsQuery.data ?? [];
  const decisions: CommitteeDecision[] = sessions.map((session) => {
    const agenda = session.agenda ?? {};
    const conflicts = Array.isArray(agenda.conflicts) ? agenda.conflicts.length : 0;
    const conditions = Array.isArray(agenda.conditions) ? agenda.conditions.map(String) : undefined;
    return {
      id: session.id,
      title: proposalTitle(session),
      description:
        typeof agenda.summary === "string"
          ? agenda.summary
          : "Decision pack com tese, valuation, risco, evidências e proposta.",
      status: mapStatus(session),
      requestedBy: typeof agenda.requested_by === "string" ? agenda.requested_by : "investment-research",
      requestedAt: session.created_at ?? session.scheduled_at ?? "",
      decidedAt: session.published_at ?? undefined,
      reason: session.rationale ?? undefined,
      conditions,
      quorumRequired: Math.floor(session.total_members / 2) + 1,
      quorumCurrent: session.present_members,
      conflictsDeclared: conflicts,
    };
  });

  const pendingDecisions = decisions.filter((decision) => decision.status === "pending");
  const approvedToday = decisions.filter(
    (decision) =>
      ["approved", "conditional"].includes(decision.status) &&
      decision.decidedAt &&
      new Date(decision.decidedAt).toDateString() === new Date().toDateString(),
  );
  const totalConflicts = decisions.reduce((total, decision) => total + decision.conflictsDeclared, 0);
  const quorumRequired = pendingDecisions.length
    ? Math.max(...pendingDecisions.map((decision) => decision.quorumRequired))
    : 0;
  const quorumCurrent = pendingDecisions.length
    ? Math.max(...pendingDecisions.map((decision) => decision.quorumCurrent))
    : 0;

  const isLoading = sessionsQuery.isLoading || detailsQuery.isLoading;
  const isError = sessionsQuery.isError || detailsQuery.isError;
  const dataState: DataState = computeDataState(isLoading, isError, null, decisions.length > 0);

  return {
    decisions,
    pendingDecisions,
    approvedToday,
    totalConflicts,
    quorumRequired,
    quorumCurrent,
    isLoading,
    isError,
    error: sessionsQuery.error ?? detailsQuery.error,
    dataState,
    refetch: async () => {
      await sessionsQuery.refetch();
      await detailsQuery.refetch();
    },
    count: decisions.length,
  };
}
