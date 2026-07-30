"use client";

import { useQuery } from "@tanstack/react-query";

import { bffFetch, queryKeys } from "@/lib/api-client";

import type { DataState } from "@/components/domain";
import { computeDataState } from "@/lib/data-state";

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

export function usePaper() {
  const tradeIntentsQuery = useQuery({
    queryKey: queryKeys.paperTradeIntents(),
    queryFn: async () => {
      return await bffFetch<Array<Record<string, unknown>>>("/api/v1/paper/trade-intents");
    },
    staleTime: 30_000,
    refetchOnWindowFocus: false,
  });

  const intents = Array.isArray(tradeIntentsQuery.data)
    ? tradeIntentsQuery.data
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
    null,
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
