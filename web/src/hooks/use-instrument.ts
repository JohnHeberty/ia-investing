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

export interface InstrumentDetail {
  id: string;
  ticker: string;
  name: string;
  exchange: string;
  listing: string;
  instrument_type: string;
  issuer_id: string;
  issuer_name: string;
  valid_as_of: string;
  fair_value: string | null;
  observed_price: string | null;
  safety_margin: string | null;
  evidence_coverage: string | null;
  material_claims: number;
  data_sources: Array<{
    id: string;
    name: string;
    type: string;
    confidence: number;
    retrievedAt: string;
  }>;
}

/** Fetch instrument detail from instruments/resolve endpoint. */
export function useInstrument(instrumentId: string | null) {
  const query = useQuery({
    queryKey: queryKeys.instrument(instrumentId ?? ""),
    queryFn: async () => {
      if (!instrumentId) return null;
      const { data, error } = await institutionalApi.GET("/api/v1/instruments/resolve", {
        params: { query: { query: instrumentId, as_of: new Date().toISOString().slice(0, 10) } },
      });
      if (error) throw error;
      return data ?? null;
    },
    enabled: !!instrumentId,
    staleTime: 60_000,
    refetchOnWindowFocus: false,
  });

  const raw = query.data as Record<string, unknown> | null;

  const instrument: InstrumentDetail | null = raw
    ? {
        id: String(raw.id ?? instrumentId ?? ""),
        ticker: String(raw.ticker ?? raw.symbol ?? ""),
        name: String(raw.name ?? raw.description ?? ""),
        exchange: String(raw.exchange ?? raw.market ?? ""),
        listing: String(raw.listing ?? ""),
        instrument_type: String(raw.instrument_type ?? raw.type ?? ""),
        issuer_id: String(raw.issuer_id ?? ""),
        issuer_name: String(raw.issuer_name ?? ""),
        valid_as_of: String(raw.valid_as_of ?? raw.as_of ?? ""),
        fair_value: raw.fair_value != null ? String(raw.fair_value) : null,
        observed_price: raw.observed_price != null ? String(raw.observed_price) : null,
        safety_margin: raw.safety_margin != null ? String(raw.safety_margin) : null,
        evidence_coverage: raw.evidence_coverage != null ? String(raw.evidence_coverage) : null,
        material_claims:
          typeof raw.material_claims === "number" ? raw.material_claims : 0,
        data_sources: Array.isArray(raw.data_sources)
          ? (raw.data_sources as Array<Record<string, unknown>>).map((s) => ({
              id: String(s.id ?? ""),
              name: String(s.name ?? ""),
              type: String(s.type ?? "manual"),
              confidence: typeof s.confidence === "number" ? s.confidence : 0.5,
              retrievedAt: String(s.retrieved_at ?? s.retrievedAt ?? ""),
            }))
          : [],
      }
    : null;

  const dataState: DataState = computeDataState(
    query.isLoading,
    query.isError,
    instrument?.valid_as_of || null,
    !!instrument,
  );

  return {
    instrument,
    isLoading: query.isLoading,
    isError: query.isError,
    error: query.error,
    dataState,
    refetch: query.refetch,
  };
}
