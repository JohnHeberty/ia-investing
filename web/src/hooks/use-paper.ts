"use client";

import { useQuery } from "@tanstack/react-query";

import { institutionalApi, queryKeys } from "@/lib/api-client";

import type { DataState } from "@/components/domain";

/** Calculate data state from query status. */
function computeDataState(
  isLoading: boolean,
  isError: boolean,
  hasData?: boolean,
): DataState {
  if (isLoading) return "empty";
  if (isError) return "error";
  if (!hasData) return "missing";
  return "empty";
}

export interface PaperOrder {
  id: string;
  intent: string;
  side: string;
  instrument: string;
  version: string;
  status: string;
  fillQuantity: string;
  fillTotal: string;
  reconciliation: string;
  created_at: string;
}

/** Fetch paper trade intents from paper/trade-intents endpoint. */
export function usePaper() {
  const tradeIntentsQuery = useQuery({
    queryKey: queryKeys.paperTradeIntents(),
    queryFn: async () => {
      const { data, error } = await institutionalApi.GET("/api/v1/paper/trade-intents");
      if (error) throw error;
      return data ?? [];
    },
    staleTime: 30_000,
    refetchOnWindowFocus: false,
  });

  const intents = Array.isArray(tradeIntentsQuery.data)
    ? (tradeIntentsQuery.data as Array<Record<string, unknown>>)
    : [];

  const orders: PaperOrder[] = intents.map((i) => {
    const side = String(i.side ?? i.direction ?? "BUY");
    const instrument = String(i.instrument ?? i.instrument_id ?? "—");
    return {
      id: String(i.id ?? ""),
      intent: `${side} · ${instrument}`,
      side,
      instrument,
      version: String(i.version ?? i.portfolio_version ?? "—"),
      status: String(i.status ?? "pending"),
      fillQuantity: String(i.filled_quantity ?? i.fill_quantity ?? "0"),
      fillTotal: String(i.total_quantity ?? i.quantity ?? "0"),
      reconciliation: String(i.reconciliation ?? i.reconciliation_status ?? "Pendente"),
      created_at: String(i.created_at ?? ""),
    };
  });

  const approvedIntents = intents.filter(
    (i) => i.status === "approved" || i.status === "filled",
  ).length;
  const partialFills = intents.filter(
    (i) => i.status === "partially_filled" || i.status === "partial",
  ).length;
  const criticalBreaks = intents.filter(
    (i) => i.reconciliation === "break" || i.reconciliation_status === "break",
  ).length;

  const isLoading = tradeIntentsQuery.isLoading;
  const isError = tradeIntentsQuery.isError;

  const dataState: DataState = computeDataState(
    isLoading,
    isError,
    intents.length > 0,
  );

  return {
    orders,
    approvedIntents,
    partialFills,
    criticalBreaks,
    isLoading,
    isError,
    error: tradeIntentsQuery.error,
    dataState,
    refetch: tradeIntentsQuery.refetch,
    count: orders.length,
  };
}
