import { getCsrfToken } from "./csrf";

/**
 * Direct fetch through the BFF proxy.
 * Prepends /api/backend to the path.
 * Automatically adds CSRF token for mutating methods.
 */
export async function bffFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const method = (init?.method ?? "GET").toUpperCase();
  const headers: Record<string, string> = {
    Accept: "application/json",
    ...(init?.headers as Record<string, string>),
  };

  if (["POST", "PUT", "PATCH", "DELETE"].includes(method)) {
    const token = getCsrfToken();
    if (token) {
      headers["x-csrf-token"] = token;
    }
  }

  const res = await fetch(`/api/backend${path}`, {
    credentials: "include",
    ...init,
    headers,
  });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`HTTP ${res.status}: ${body.slice(0, 200)}`);
  }
  return (await res.json()) as T;
}

function k(prefix: string, ...rest: unknown[]): unknown[] {
  return [prefix, ...rest];
}

export const queryKeys = {
  policyEvents: () => k("policyEvents"),
  modelPortfolios: (params?: { state?: string; limit?: number }) => k("modelPortfolios", params),
  modelPortfolio: (id: string) => k("modelPortfolio", id),
  agentRuns: (params?: { status?: string; agent_name?: string }) => k("agentRuns", params),
  researchCases: () => k("researchCases"),
  sourceHealth: () => k("sourceHealth"),
  instrument: (id: string) => k("instrument", id),
  committeeSessions: () => k("committeeSessions"),
  riskAssessments: () => k("riskAssessments"),
  qualityIncidents: () => k("qualityIncidents"),
  backtests: () => k("backtests"),
  macroSeries: () => k("macroSeries"),
  paperTradeIntents: () => k("paperTradeIntents"),
  rebalanceProposals: () => k("rebalanceProposals"),
  auditLogs: () => k("auditLogs"),
  auditTrail: () => k("auditTrail"),
};
