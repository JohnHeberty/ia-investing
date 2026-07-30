import { getCsrfToken } from "./csrf";

const apiBase = "/api/backend";

async function api<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const url = `${apiBase}/api/v1${path}`;
  const method = (options.method ?? "GET").toUpperCase();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    Accept: "application/json",
    ...(options.headers as Record<string, string>),
  };
  if (["POST", "PUT", "PATCH", "DELETE"].includes(method)) {
    const token = getCsrfToken();
    if (token) headers["x-csrf-token"] = token;
  }
  const response = await fetch(url, {
    ...options,
    credentials: "include",
    headers,
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(
      (body as { detail?: string }).detail ?? `API error: ${response.status}`,
    );
  }
  if (response.status === 204) return undefined as unknown as Promise<T>;
  return response.json() as Promise<T>;
}

export type CandidateStatus =
  | "suggested"
  | "identity_resolution"
  | "source_discovery"
  | "awaiting_user_input"
  | "source_validation"
  | "document_collection"
  | "data_quality"
  | "fundamental_analysis"
  | "risk_analysis"
  | "committee_review"
  | "approved"
  | "rejected"
  | "watchlist"
  | "cancelled";

export type SourceKind =
  | "company_website"
  | "investor_relations"
  | "financial_reports"
  | "cvm_profile"
  | "cvm_filings"
  | "b3_listing"
  | "governance"
  | "newsroom"
  | "regulator"
  | "market_data";

export interface Candidate {
  id: string;
  ticker: string;
  exchange: string;
  legal_name: string | null;
  cnpj: string | null;
  cvm_code: string | null;
  origin: string;
  status: CandidateStatus;
  rationale: string | null;
  instrument_id: string | null;
  final_decision: string | null;
  final_decision_reason: string | null;
  approved_portfolio_eligible: boolean;
  updated_at: string;
}

export interface CandidateSource {
  id: string;
  kind: SourceKind;
  url: string;
  status: string;
  official: boolean;
  verification_method: string;
  confidence: string;
}

export interface CandidateGap {
  id: string;
  title: string;
  description: string;
  level: string;
  status: string;
  source_kind: string | null;
  requested_user_action: string;
}

export interface AnalysisRun {
  id: string;
  run_number: number;
  trigger: string;
  status: string;
  decision: string | null;
  data_as_of: string;
  blocker_codes: string[];
}

export interface TimelineEvent {
  id: string;
  event_type: string;
  actor_type: string;
  actor_id: string;
  occurred_at: string;
  aggregate_version: number;
}

export interface CandidateDetail {
  candidate: Candidate;
  readiness_score: string;
  blocking_gap_codes: string[];
  gaps: CandidateGap[];
  sources: CandidateSource[];
  analysis_runs: AnalysisRun[];
  timeline: TimelineEvent[];
}

export interface ExplorationRun {
  id: string;
  status: string;
  strategy_codes: string[];
  universe_size: number;
  eligible_size: number;
  created_at: string;
  error_detail: string | null;
}

export interface ExplorationSuggestion {
  id: string;
  ticker: string;
  exchange: string;
  status: string;
  quantitative_score: string;
  data_coverage_score: string;
  source_discovery_score: string;
  rationale: string;
  signals: string[];
  risks: string[];
  promoted_candidate_id: string | null;
}

export interface ExplorationDetail {
  run: ExplorationRun;
  suggestions: ExplorationSuggestion[];
}

export function createCandidate(input: {
  ticker: string;
  exchange: string;
  legal_name?: string;
  cnpj?: string;
  cvm_code?: string;
  rationale?: string;
}): Promise<Candidate> {
  return api<Candidate>("/investment-candidates", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function addCandidateSource(
  candidateId: string,
  etag: string,
  input: { kind: SourceKind; url: string; notes?: string },
): Promise<void> {
  return api<void>(`/investment-candidates/${candidateId}/sources`, {
    method: "POST",
    headers: { "If-Match": etag },
    body: JSON.stringify(input),
  });
}

export function getCandidate(id: string): Promise<{ data: CandidateDetail; etag: string }> {
  const url = `${apiBase}/api/v1/investment-candidates/${id}`;
  return fetch(url, {
    credentials: "include",
    headers: {
      Accept: "application/json",
    },
  })
    .then(async (response) => {
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new Error(
          (body as { detail?: string }).detail ?? `API error: ${response.status}`,
        );
      }
      const data = await response.json() as CandidateDetail;
      const etag = response.headers.get("ETag") ?? "";
      return { data, etag };
    });
}

export function requestCandidateReanalysis(
  candidateId: string,
  etag: string,
  force: boolean,
): Promise<void> {
  return api<void>(`/investment-candidates/${candidateId}/reanalyze`, {
    method: "POST",
    headers: { "If-Match": etag },
    body: JSON.stringify({ force }),
  });
}

export function listCandidates(status?: string): Promise<{ items: Candidate[] }> {
  const query = status ? `?status=${encodeURIComponent(status)}` : "";
  return api<{ items: Candidate[] }>(
    `/investment-candidates${query}`,
  );
}

export function listExplorationRuns(): Promise<ExplorationRun[]> {
  return api<ExplorationRun[]>("/exploration-runs");
}

export function getExplorationRun(id: string): Promise<ExplorationDetail> {
  return api<ExplorationDetail>(`/exploration-runs/${id}`);
}

export function createExplorationRun(input: {
  strategy_codes: string[];
  minimum_liquidity: string;
  maximum_suggestions: number;
}): Promise<ExplorationRun> {
  return api<ExplorationRun>("/exploration-runs", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function createExplorationSchedule(input: {
  name: string;
  strategy_codes: string[];
  minimum_liquidity: string;
  maximum_suggestions: number;
  interval_hours: number;
  paused: boolean;
}): Promise<{ schedule_id: string; interval_hours: number }> {
  return api("/exploration-runs/schedules", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function promoteExplorationSuggestion(id: string): Promise<Candidate> {
  return api<Candidate>(`/exploration-suggestions/${id}/promote`, {
    method: "POST",
  });
}

export function dismissExplorationSuggestion(
  id: string,
  reason: string,
): Promise<void> {
  return api<void>(`/exploration-suggestions/${id}/dismiss`, {
    method: "POST",
    body: JSON.stringify({ reason }),
  });
}
