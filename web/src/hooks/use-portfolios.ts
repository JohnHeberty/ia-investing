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

export interface PortfolioSummary {
  id: string;
  name: string;
  state: string;
  mandate_id: string;
  base_currency: string;
  environment: string;
  created_at: string;
  updated_at: string;
  eligible?: boolean;
  category?: string;
}

/** Fetch portfolio summary list from model-portfolios endpoint. */
export function usePortfolios(params?: { state?: string; limit?: number }) {
  const query = useQuery({
    queryKey: queryKeys.modelPortfolios(params),
    queryFn: async () => {
      const { data, error } = await institutionalApi.GET("/api/v1/model-portfolios", {
        params: { query: { state: params?.state ?? undefined, limit: params?.limit ?? undefined } },
      });
      if (error) throw error;
      return data ?? [];
    },
    staleTime: 60_000,
    refetchOnWindowFocus: false,
  });

  const portfolios: PortfolioSummary[] = Array.isArray(query.data)
    ? query.data.map((p: Record<string, unknown>) => ({
        id: String(p.id ?? ""),
        name: String(p.name ?? ""),
        state: String(p.state ?? ""),
        mandate_id: String(p.mandate_id ?? ""),
        base_currency: String(p.base_currency ?? "BRL"),
        environment: String(p.environment ?? ""),
        created_at: String(p.created_at ?? ""),
        updated_at: String(p.updated_at ?? ""),
        eligible: p.eligible !== false,
        category: String(p.category ?? ""),
      }))
    : [];

  const latestAsOf = portfolios.length > 0
    ? portfolios.reduce((latest, p) => {
        const d = new Date(p.updated_at).getTime();
        return d > latest ? d : latest;
      }, 0)
    : null;

  const dataState: DataState = computeDataState(
    query.isLoading,
    query.isError,
    latestAsOf ? new Date(latestAsOf).toISOString() : null,
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

/** Fetch single portfolio detail. */
export function usePortfolio(portfolioId: string | null) {
  const query = useQuery({
    queryKey: queryKeys.modelPortfolio(portfolioId ?? ""),
    queryFn: async () => {
      if (!portfolioId) return null;
      const { data, error } = await institutionalApi.GET("/api/v1/model-portfolios/{portfolio_id}", {
        params: { path: { portfolio_id: portfolioId } },
      });
      if (error) throw error;
      return data ?? null;
    },
    enabled: !!portfolioId,
    staleTime: 60_000,
    refetchOnWindowFocus: false,
  });

  const portfolio = query.data as Record<string, unknown> | null;

  const dataState: DataState = computeDataState(
    query.isLoading,
    query.isError,
    portfolio ? String(portfolio.updated_at ?? portfolio.created_at ?? "") : null,
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
