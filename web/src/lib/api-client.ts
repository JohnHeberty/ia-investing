import { getCsrfToken } from "./csrf";

/**
 * Direct fetch through the BFF proxy.
 * Prepends /api/backend to the path.
 * Automatically adds CSRF token for mutating methods.
 */
function generateRequestId(): string {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}

/**
 * Direct fetch through the BFF proxy.
 * Prepends /api/backend to the path.
 * Automatically adds CSRF token for mutating methods and X-Request-Id for tracing.
 */
export async function bffFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const method = (init?.method ?? "GET").toUpperCase();
  const headers: Record<string, string> = {
    "x-request-id": generateRequestId(),
    Accept: "application/json",
    ...(init?.headers as Record<string, string>),
  };

  if (["POST", "PUT", "PATCH", "DELETE"].includes(method)) {
    const token = getCsrfToken();
    if (token) {
      headers["x-csrf-token"] = token;
    }
    if (init?.body && typeof init.body === "string" && !headers["Content-Type"]) {
      headers["Content-Type"] = "application/json";
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
  if (res.status === 204) return undefined as T;
  try {
    return (await res.json()) as T;
  } catch {
    throw new Error(`HTTP ${res.status}: Response body is not valid JSON`);
  }
}

function k(prefix: string, ...rest: unknown[]): unknown[] {
  return [prefix, ...rest];
}

export const queryKeys = {
  policyEvents: () => k("policyEvents"),
  policyAlerts: () => k("policyAlerts"),
  policyForecasts: () => k("policyForecasts"),
  policySources: () => k("policySources"),
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
  newsItems: () => k("newsItems"),
  newsEvents: () => k("newsEvents"),
  newsSources: () => k("newsSources"),
  newsStats: () => k("newsStats"),
  newsEvent: (id: string) => k("newsEvent", id),
  paperTradeIntents: () => k("paperTradeIntents"),
  rebalanceProposals: () => k("rebalanceProposals"),
  auditLogs: () => k("auditLogs"),
  auditTrail: () => k("auditTrail"),
  schedules: () => k("schedules"),
  scheduleRuns: (scheduleId: string, limit?: number) => k("scheduleRuns", scheduleId, limit),
};
