"use client";

import { useQuery } from "@tanstack/react-query";
import { bffFetch, queryKeys } from "@/lib/api-client";
import type { DataState } from "@/components/domain";
import { computeDataState } from "@/lib/data-state";

export interface NewsItem {
  id: string;
  title: string | null;
  body: string | null;
  url: string | null;
  source_id: string;
  published_at: string | null;
  language: string | null;
  sentiment_score: number | null;
  is_processed: boolean | null;
  created_at: string | null;
}

export interface DetectedEvent {
  id: string;
  news_item_id: string | null;
  issuer_id: string | null;
  event_type: string | null;
  description: string | null;
  materiality_score: number | null;
  direction_hint: string | null;
  time_horizon: string | null;
  affected_metrics: Record<string, unknown> | null;
  created_at: string | null;
}

export function useNews() {
  const itemsQuery = useQuery({
    queryKey: queryKeys.newsItems(),
    queryFn: async () => {
      return await bffFetch<{ items: NewsItem[]; total: number }>("/api/v1/news/items?limit=100");
    },
    staleTime: 30_000,
    refetchOnWindowFocus: false,
  });

  const eventsQuery = useQuery({
    queryKey: queryKeys.newsEvents(),
    queryFn: async () => {
      return await bffFetch<{ items: DetectedEvent[]; total: number }>("/api/v1/news/events?limit=100");
    },
    staleTime: 30_000,
    refetchOnWindowFocus: false,
  });

  const items = itemsQuery.data?.items ?? [];
  const events = eventsQuery.data?.items ?? [];
  const totalItems = itemsQuery.data?.total ?? 0;
  const totalEvents = eventsQuery.data?.total ?? 0;

  const processedCount = items.filter((i) => i.is_processed).length;
  const unprocessedCount = items.filter((i) => !i.is_processed).length;

  const positiveEvents = events.filter((e) => e.direction_hint === "positive").length;
  const negativeEvents = events.filter((e) => e.direction_hint === "negative").length;

  const isLoading = itemsQuery.isLoading || eventsQuery.isLoading;
  const isError = itemsQuery.isError || eventsQuery.isError;
  const dataState: DataState = computeDataState(
    isLoading,
    isError,
    items.length > 0 ? items[0].created_at : null,
    items.length > 0,
  );

  return {
    items,
    events,
    totalItems,
    totalEvents,
    processedCount,
    unprocessedCount,
    positiveEvents,
    negativeEvents,
    isLoading,
    isError,
    error: itemsQuery.error ?? eventsQuery.error,
    dataState,
    refetch: () => {
      void itemsQuery.refetch();
      void eventsQuery.refetch();
    },
  };
}
