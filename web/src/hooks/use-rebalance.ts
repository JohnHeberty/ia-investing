"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { bffFetch } from "@/lib/api-client";

export type DriftItem = {
  ticker: string;
  current_weight: number;
  target_weight: number;
  drift: number;
  severity: "green" | "yellow" | "red";
};

export type DriftSummary = {
  portfolio_id: string;
  portfolio_name: string;
  snapshot_date: string | null;
  current_allocations: Record<string, number>;
  target_allocations: Record<string, number>;
  max_drift: number;
  total_drift: number;
  items: DriftItem[];
};

export type RebalanceTrade = {
  id: string;
  ticker: string;
  side: "buy" | "sell";
  current_weight: number;
  target_weight: number;
  delta: number;
  estimated_value: number;
  estimated_fees: number | null;
  estimated_taxes: number | null;
  status: "pending" | "executed" | "skipped" | "failed";
  execution_order: number;
  executed_at: string | null;
  fill_price: number | null;
  fill_quantity: number | null;
};

export type RebalanceProposal = {
  id: string;
  portfolio_id: string;
  status: "draft" | "approved" | "in_progress" | "completed" | "cancelled";
  target_allocations: Record<string, number>;
  current_allocations: Record<string, number> | null;
  drift_analysis: {
    max_drift: number;
    total_drift: number;
    items: DriftItem[];
    compliance: {
      passed: boolean;
      issues: string[];
      concentration_limit: number;
      sector_limit: number;
    };
  } | null;
  rationale: string;
  created_by: string;
  approved_by: string | null;
  approval_notes: string | null;
  cancelled_reason: string | null;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
  cancelled_at: string | null;
  trades: RebalanceTrade[];
  execution_progress?: {
    total: number;
    executed: number;
    skipped: number;
    failed: number;
    percent_complete: number;
  };
};

export function useDriftSummary(portfolioId: string | undefined) {
  return useQuery({
    queryKey: ["rebalance", "drift", portfolioId],
    queryFn: () => bffFetch<DriftSummary>(`/api/v1/rebalance/${portfolioId}/drift`),
    enabled: !!portfolioId,
    staleTime: 30_000,
    retry: 1,
  });
}

export function useRebalanceProposals(portfolioId?: string, status?: string) {
  const params = new URLSearchParams();
  if (portfolioId) params.set("portfolio_id", portfolioId);
  if (status) params.set("status", status);
  const qs = params.toString();

  return useQuery({
    queryKey: ["rebalance", "proposals", portfolioId, status],
    queryFn: () => bffFetch<RebalanceProposal[]>(`/api/v1/rebalance/proposals${qs ? `?${qs}` : ""}`),
    staleTime: 15_000,
    retry: 1,
  });
}

export function useRebalanceProposal(id: string | undefined) {
  return useQuery({
    queryKey: ["rebalance", "proposal", id],
    queryFn: () => bffFetch<RebalanceProposal>(`/api/v1/rebalance/proposals/${id}`),
    enabled: !!id,
    staleTime: 10_000,
    retry: 1,
  });
}

export function useProposeRebalance() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      portfolioId,
      targetAllocations,
      rationale,
    }: {
      portfolioId: string;
      targetAllocations: Record<string, number>;
      rationale: string;
    }) =>
      bffFetch<RebalanceProposal>(`/api/v1/rebalance/${portfolioId}/propose`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ target_allocations: targetAllocations, rationale }),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["rebalance"] });
    },
  });
}

export function useApproveRebalance() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      proposalId,
      notes,
    }: {
      proposalId: string;
      notes?: string;
    }) =>
      bffFetch<RebalanceProposal>(`/api/v1/rebalance/proposals/${proposalId}/approve`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ notes }),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["rebalance"] });
    },
  });
}

export function useExecuteTradeStep() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      proposalId,
      tradeIds,
    }: {
      proposalId: string;
      tradeIds: string[];
    }) =>
      bffFetch<RebalanceProposal>(`/api/v1/rebalance/proposals/${proposalId}/execute-step`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ trade_ids: tradeIds }),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["rebalance"] });
    },
  });
}

export function useCompleteRebalance() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ proposalId }: { proposalId: string }) =>
      bffFetch<RebalanceProposal>(`/api/v1/rebalance/proposals/${proposalId}/complete`, {
        method: "POST",
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["rebalance"] });
    },
  });
}

export function useCancelRebalance() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      proposalId,
      reason,
    }: {
      proposalId: string;
      reason: string;
    }) =>
      bffFetch<RebalanceProposal>(`/api/v1/rebalance/proposals/${proposalId}/cancel`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ reason }),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["rebalance"] });
    },
  });
}
