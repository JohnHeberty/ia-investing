"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import type { DataState } from "@/components/domain";
import { institutionalApi, queryKeys } from "@/lib/api-client";
import { computeDataState } from "@/lib/data-state";

export interface PortfolioPosition {
  id: string;
  ticker_symbol: string;
  quantity: number;
  avg_cost_per_share: number;
  current_price: number | null;
  weight_pct?: number | null;
}

export interface Portfolio {
  id: string;
  name: string;
  is_paper_trading: boolean;
  base_currency: string;
  description?: string;
  initial_capital?: number;
  positions?: PortfolioPosition[];
}

export interface PortfolioWithPositions extends Portfolio {
  positions: Array<{
    id: string;
    ticker_symbol: string;
    quantity: number;
    avg_cost_per_share: number;
    current_price: number | null;
    weight_pct?: number | null;
  }>;
}

export interface CreatePortfolioInput {
  name: string;
  description?: string;
  is_paper_trading?: boolean;
  base_currency?: string;
  initial_capital?: number;
}

/** Fetch all paper portfolios */
export function usePortfoliosList() {
  const query = useQuery({
    queryKey: ["paperPortfolios"],
    queryFn: async () => {
      const res = await fetch("/api/backend/api/v1/portfolio", {
        credentials: "include",
        headers: { Accept: "application/json" },
      });
      if (!res.ok) {
        const body = await res.text().catch(() => "");
        throw new Error(`HTTP ${res.status}: ${body.slice(0, 200)}`);
      }
      const data = await res.json();
      return (Array.isArray(data) ? data : []) as unknown as Portfolio[];
    },
    staleTime: 30_000,
    refetchOnWindowFocus: false,
  });

  const portfolios = (query.data ?? []) as Portfolio[];
  const dataState: DataState = computeDataState(
    query.isLoading,
    query.isError,
    null,
    portfolios.length > 0,
  );

  return {
    portfolios,
    isLoading: query.isLoading,
    isError: query.isError,
    error: query.error,
    dataState,
    refetch: query.refetch,
    count: portfolios.length,
  };
}

/** Fetch single portfolio with positions */
export function usePortfolioDetail(portfolioId: string | null) {
  const query = useQuery({
    queryKey: ["paperPortfolio", portfolioId],
    queryFn: async () => {
      if (!portfolioId) return null;
      const res = await fetch(`/api/backend/api/v1/portfolio/${portfolioId}`, {
        credentials: "include",
        headers: { Accept: "application/json" },
      });
      if (!res.ok) {
        const body = await res.text().catch(() => "");
        throw new Error(`HTTP ${res.status}: ${body.slice(0, 200)}`);
      }
      return (await res.json()) as unknown as PortfolioWithPositions | null;
    },
    enabled: !!portfolioId,
    staleTime: 30_000,
    refetchOnWindowFocus: false,
  });

  const portfolio = query.data as PortfolioWithPositions | null;

  const dataState: DataState = computeDataState(
    query.isLoading,
    query.isError,
    null,
    !!portfolio,
  );

  return {
    portfolio,
    isLoading: query.isLoading,
    isError: query.isError,
    error: query.error,
    dataState,
    refetch: query.refetch,
  };
}

/** Create a new paper portfolio */
export function useCreatePortfolio() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (input: CreatePortfolioInput) => {
      const idempotencyKey = crypto.randomUUID();
      const res = await fetch("/api/backend/api/v1/portfolio", {
        method: "POST",
        credentials: "include",
        headers: {
          "Content-Type": "application/json",
          "Idempotency-Key": idempotencyKey,
        },
        body: JSON.stringify({
          name: input.name,
          description: input.description,
          is_paper_trading: input.is_paper_trading ?? true,
          base_currency: input.base_currency ?? "BRL",
          initial_capital: input.initial_capital,
        }),
      });
      if (!res.ok) {
        const body = await res.text().catch(() => "");
        throw new Error(`HTTP ${res.status}: ${body.slice(0, 200)}`);
      }
      return (await res.json()) as unknown as Portfolio;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["paperPortfolios"] });
    },
  });
}

/** Add a position to a portfolio */
export function useAddPosition() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      portfolioId,
      ticker,
      quantity,
      avgCost,
      currentPrice,
    }: {
      portfolioId: string;
      ticker: string;
      quantity: number;
      avgCost: number;
      currentPrice?: number;
    }) => {
      const res = await fetch(`/api/backend/api/v1/portfolio/${portfolioId}/positions`, {
        method: "POST",
        credentials: "include",
        headers: {
          "Content-Type": "application/json",
          "Idempotency-Key": crypto.randomUUID(),
        },
        body: JSON.stringify({
          ticker_symbol: ticker,
          quantity,
          avg_cost_per_share: avgCost,
          current_price: currentPrice,
        }),
      });
      if (!res.ok) {
        const body = await res.text().catch(() => "");
        throw new Error(`HTTP ${res.status}: ${body.slice(0, 200)}`);
      }
      return (await res.json()) as unknown;
    },
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ["paperPortfolio", variables.portfolioId] });
      queryClient.invalidateQueries({ queryKey: ["paperPortfolios"] });
    },
  });
}

export interface PortfolioRecommendation {
  ticker: string;
  action: string;
  current_weight: number;
  target_weight: number;
  confidence: number;
  rationale: string;
  risk_reward: number | null;
}

export interface PortfolioRecommendations {
  portfolio_id: string;
  summary: string;
  overall_risk: string;
  recommendations: PortfolioRecommendation[];
  risk_assessment: Record<string, unknown>;
  performance_outlook: Record<string, unknown>;
  key_risks: string[];
  suggested_limits: Record<string, unknown>;
}

/** Fetch portfolio recommendations */
export function usePortfolioRecommendations(portfolioId: string | null) {
  const query = useQuery({
    queryKey: ["portfolioRecommendations", portfolioId],
    queryFn: async () => {
      if (!portfolioId) return null;
      const res = await fetch(`/api/backend/api/v1/portfolio/${portfolioId}/recommendations`, {
        credentials: "include",
        headers: { Accept: "application/json" },
      });
      if (!res.ok) {
        const body = await res.text().catch(() => "");
        throw new Error(`HTTP ${res.status}: ${body.slice(0, 200)}`);
      }
      return (await res.json()) as unknown as PortfolioRecommendations;
    },
    enabled: !!portfolioId,
    staleTime: 60_000,
    refetchOnWindowFocus: false,
  });

  return {
    recommendations: query.data as PortfolioRecommendations | null,
    isLoading: query.isLoading,
    isError: query.isError,
    error: query.error,
    refetch: query.refetch,
  };
}

/** Delete a position from a portfolio */
export function useDeletePosition() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ portfolioId, positionId }: { portfolioId: string; positionId: string }) => {
      const res = await fetch(`/api/backend/api/v1/portfolio/${portfolioId}/positions/${positionId}`, {
        method: "DELETE",
        credentials: "include",
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error((body as Record<string, unknown>).detail as string || `HTTP ${res.status}`);
      }
      return (await res.json()) as { deleted: boolean };
    },
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ["paperPortfolio", variables.portfolioId] });
      queryClient.invalidateQueries({ queryKey: ["paperPortfolios"] });
    },
  });
}

/** Update a position in a portfolio */
export function useUpdatePosition() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      portfolioId,
      positionId,
      ticker_symbol,
      quantity,
      avg_cost_per_share,
      current_price,
    }: {
      portfolioId: string;
      positionId: string;
      ticker_symbol?: string;
      quantity?: number;
      avg_cost_per_share?: number;
      current_price?: number;
    }) => {
      const body: Record<string, unknown> = {};
      if (ticker_symbol !== undefined) body.ticker_symbol = ticker_symbol;
      if (quantity !== undefined) body.quantity = quantity;
      if (avg_cost_per_share !== undefined) body.avg_cost_per_share = avg_cost_per_share;
      if (current_price !== undefined) body.current_price = current_price;

      const res = await fetch(`/api/backend/api/v1/portfolio/${portfolioId}/positions/${positionId}`, {
        method: "PUT",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error((body as Record<string, unknown>).detail as string || `HTTP ${res.status}`);
      }
      if (res.headers.get("content-length") === "0") return { deleted: true };
      return (await res.json().catch(() => ({ deleted: true }))) as { deleted: boolean };
    },
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ["paperPortfolio", variables.portfolioId] });
      queryClient.invalidateQueries({ queryKey: ["paperPortfolios"] });
    },
  });
}

/** Delete a portfolio */
export function useDeletePortfolio() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (portfolioId: string) => {
      const res = await fetch(`/api/backend/api/v1/portfolio/${portfolioId}`, {
        method: "DELETE",
        credentials: "include",
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error((body as Record<string, unknown>).detail as string || `HTTP ${res.status}`);
      }
      return (await res.json().catch(() => ({ id: portfolioId, deleted: true }))) as { id: string; deleted: boolean };
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["paperPortfolios"] });
    },
  });
}
