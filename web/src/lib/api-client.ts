import createClient from "openapi-fetch";
import type { paths } from "./api-schema.d";
import { getCsrfToken } from "./csrf";

function csrfFetch(input: RequestInfo, init?: RequestInit): Promise<Response> {
  const method = (init?.method ?? "GET").toUpperCase();
  const requestId = crypto.randomUUID();
  const headers = new Headers(init?.headers);
  headers.set("X-Request-Id", requestId);

  if (["POST", "PUT", "PATCH", "DELETE"].includes(method)) {
    const token = getCsrfToken();
    if (token) {
      headers.set("x-csrf-token", token);
    }
  }

  return fetch(input, { ...init, headers });
}

export const institutionalApi = createClient<paths>({
  baseUrl: process.env.NEXT_PUBLIC_API_BASE_URL ?? "",
  credentials: "include",
  headers: {
    "Content-Type": "application/json",
  },
  fetch: csrfFetch,
});

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
