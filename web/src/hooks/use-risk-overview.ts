"use client";

import { useQuery } from "@tanstack/react-query";
import { bffFetch } from "@/lib/api-client";

export interface RiskBreach {
  id: string;
  limit_name: string;
  limit_type: string;
  observed_value: number;
  limit_value: number;
  status: string;
}

export interface StressScenario {
  id: string;
  name: string;
  pnl_impact: number | null;
  nav_impact_ratio: number | null;
}

export interface RiskSnapshot {
  id: string;
  portfolio_id: string | null;
  as_of: string;
  volatility: number | null;
  drawdown: number | null;
  concentration: Record<string, unknown> | null;
  liquidity: Record<string, unknown> | null;
  exposures: Record<string, unknown> | null;
  breach_count: number;
}

export interface RiskOverview {
  snapshots: RiskSnapshot[];
  breaches: RiskBreach[];
  stress_scenarios: StressScenario[];
  hard_breach_count: number;
  soft_breach_count: number;
  latest_volatility: number | null;
  latest_drawdown: number | null;
  total_snapshots: number;
}

export function useRiskOverview() {
  const query = useQuery({
    queryKey: ["riskOverview"],
    queryFn: async () => {
      return await bffFetch<RiskOverview>("/api/v1/risk/overview");
    },
    staleTime: 60_000,
    refetchOnWindowFocus: false,
  });

  return {
    overview: query.data ?? null,
    isLoading: query.isLoading,
    isError: query.isError,
    refetch: query.refetch,
  };
}

export interface RiskPolicy {
  id: string;
  mandate_id: string | null;
  version: number;
  methodology_version: string;
  limits: Record<string, unknown>;
  status: string;
}

export function useRiskPolicies() {
  const query = useQuery({
    queryKey: ["riskPolicies"],
    queryFn: async () => {
      return await bffFetch<{ policies: RiskPolicy[]; count: number }>("/api/v1/risk/policies");
    },
    staleTime: 60_000,
    refetchOnWindowFocus: false,
  });

  return {
    policies: query.data?.policies ?? [],
    count: query.data?.count ?? 0,
    isLoading: query.isLoading,
    isError: query.isError,
  };
}
