"use client";

import { useQuery } from "@tanstack/react-query";

export type PortfolioRankItem = {
  portfolio_id: string;
  name: string;
  cohort_key: string;
  category: string;
  benchmark: string;
  currency: string;
  risk_class: string;
  environment: "paper" | "live";
  stage: string;
  score: string | null;
  rank: number | null;
  eligible: boolean;
  exclusion_reasons: string[];
  nav: string | null;
  nav_as_of: string | null;
  reconciled: boolean;
  volatility: string | null;
  drawdown: string | null;
  open_hard_breaches: number;
  open_soft_breaches: number;
  data_confidence: string;
  thesis_coverage: string;
};

export type CandidatePipeline = {
  total: number;
  awaiting_input: number;
  in_committee: number;
  approved: number;
  rejected: number;
  blocked: number;
  funnel_by_status: Record<string, number>;
};

export type MissionControl = {
  generated_at: string;
  data_as_of: string | null;
  top_portfolios: PortfolioRankItem[];
  excluded_portfolios: PortfolioRankItem[];
  research_funnel: Record<string, number>;
  agent_operations: {
    running: number;
    succeeded_24h: number;
    failed_24h: number;
    schema_pass_rate: string | null;
    evidence_coverage: string | null;
    cost_usd_24h: string;
    p95_duration_ms: number | null;
  };
  source_health: Array<{
    source_id: string;
    code: string;
    name: string;
    status: "healthy" | "stale" | "failed" | "never_succeeded";
    last_success_at: string | null;
    last_failure_at: string | null;
    expected_frequency_minutes: number;
    freshness_grace_minutes: number;
    age_minutes: number | null;
    error_code: string | null;
  }>;
  risk: {
    open_hard_breaches: number;
    open_soft_breaches: number;
    portfolios_with_breaches: number;
    stale_risk_snapshots: number;
  };
  pending_approvals: number;
  critical_alerts: number;
  candidate_pipeline: CandidatePipeline | null;
};

const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL;
const organizationId = process.env.NEXT_PUBLIC_ORGANIZATION_ID;

async function fetchMissionControl(): Promise<MissionControl> {
  if (!apiBaseUrl) {
    throw new Error("NEXT_PUBLIC_API_BASE_URL não está configurado");
  }
  if (!organizationId) {
    throw new Error("NEXT_PUBLIC_ORGANIZATION_ID não está configurado");
  }
  const response = await fetch(`${apiBaseUrl}/api/v1/dashboard/mission-control`, {
    credentials: "include",
    headers: {
      Accept: "application/json",
      "X-Organization-Id": organizationId,
    },
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`Mission Control indisponível (${response.status}): ${detail}`);
  }
  return response.json() as Promise<MissionControl>;
}

export function useMissionControl() {
  return useQuery({
    queryKey: ["mission-control"],
    queryFn: fetchMissionControl,
    staleTime: 30_000,
    refetchInterval: 60_000,
    retry: 1,
  });
}
