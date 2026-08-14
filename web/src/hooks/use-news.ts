"use client";

import { createContext, useContext } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { bffFetch, queryKeys } from "@/lib/api-client";
import type { DataState } from "@/components/domain";
import { computeDataState } from "@/lib/data-state";

export interface NewsItem {
  id: string;
  title: string | null;
  body: string | null;
  url: string | null;
  source_id: string;
  source_name: string | null;
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

export interface NewsSource {
  id: string;
  name: string;
  url_pattern: string | null;
  trust_level: number | null;
  source_type: string | null;
  is_active: boolean | null;
  created_at: string | null;
}

export interface NewsStats {
  total_items: number;
  processed_items: number;
  unprocessed_items: number;
  total_events: number;
  positive_events: number;
  negative_events: number;
  neutral_events: number;
  total_impacts: number;
  active_sources: number;
}

export interface PortfolioImpact {
  event_id: string;
  event_type: string | null;
  materiality_score: number | null;
  direction_hint: string | null;
  issuer_id: string;
  portfolio_id: string;
  portfolio_name: string;
  event_created_at: string | null;
}

export interface NewsDataValue {
  items: NewsItem[];
  events: DetectedEvent[];
  sources: NewsSource[];
  stats: NewsStats | undefined;
  totalItems: number;
  totalEvents: number;
  processedCount: number;
  unprocessedCount: number;
  positiveEvents: number;
  negativeEvents: number;
  isLoading: boolean;
  isError: boolean;
  error: unknown;
  dataState: DataState;
  refetch: () => Promise<unknown[]>;
}

export const NewsDataContext = createContext<NewsDataValue | null>(null);

export function useNewsData(): NewsDataValue {
  const ctx = useContext(NewsDataContext);
  if (!ctx) throw new Error("useNewsData must be inside NewsDataProvider");
  return ctx;
}

function useNewsQueries() {
  const itemsQuery = useQuery({
    queryKey: queryKeys.newsItems(),
    queryFn: () => bffFetch<{ items: NewsItem[]; total: number }>("/api/v1/news/items?limit=100"),
    staleTime: 30_000,
    refetchOnWindowFocus: false,
  });

  const eventsQuery = useQuery({
    queryKey: queryKeys.newsEvents(),
    queryFn: () =>
      bffFetch<{ items: DetectedEvent[]; total: number }>("/api/v1/news/events?limit=100"),
    staleTime: 30_000,
    refetchOnWindowFocus: false,
  });

  const sourcesQuery = useQuery({
    queryKey: queryKeys.newsSources(),
    queryFn: () => bffFetch<NewsSource[]>("/api/v1/news/sources"),
    staleTime: 60_000,
  });

  const statsQuery = useQuery({
    queryKey: queryKeys.newsStats(),
    queryFn: () => bffFetch<NewsStats>("/api/v1/news/stats"),
    staleTime: 30_000,
  });

  return { itemsQuery, eventsQuery, sourcesQuery, statsQuery };
}

export function useNewsValue(): NewsDataValue {
  const { itemsQuery, eventsQuery, sourcesQuery, statsQuery } = useNewsQueries();

  const items = itemsQuery.data?.items ?? [];
  const events = eventsQuery.data?.items ?? [];
  const sources = sourcesQuery.data ?? [];
  const stats = statsQuery.data;
  const totalItems = itemsQuery.data?.total ?? 0;
  const totalEvents = eventsQuery.data?.total ?? 0;

  const processedCount = items.filter((i) => i.is_processed === true).length;
  const unprocessedCount = items.filter((i) => i.is_processed === false).length;

  const positiveEvents = events.filter((e) => e.direction_hint === "positive").length;
  const negativeEvents = events.filter((e) => e.direction_hint === "negative").length;

    const isLoading =
      itemsQuery.isLoading || eventsQuery.isLoading || sourcesQuery.isLoading || statsQuery.isLoading;
    const isError = itemsQuery.isError || eventsQuery.isError || sourcesQuery.isError || statsQuery.isError;
  const dataState: DataState = computeDataState(
    isLoading,
    isError,
    items.length > 0 ? items[0].created_at : null,
    items.length > 0,
  );

  return {
    items,
    events,
    sources,
    stats,
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
    refetch: () => Promise.all([itemsQuery.refetch(), eventsQuery.refetch()]),
  };
}

/** @deprecated Use useNewsData() inside NewsDataProvider instead */
export function useNews(): NewsDataValue {
  if (process.env.NODE_ENV === "development") {
    console.warn("useNews() is deprecated. Use useNewsData() inside NewsDataProvider instead.");
  }
  return useNewsValue();
}

export function useSourceMutations() {
  const queryClient = useQueryClient();

  const invalidateSources = () => {
    queryClient.invalidateQueries({ queryKey: queryKeys.newsSources() });
    queryClient.invalidateQueries({ queryKey: queryKeys.newsStats() });
  };

  const createMutation = useMutation({
    mutationFn: (data: {
      name: string;
      source_type?: string;
      url_pattern?: string;
      trust_level?: number;
    }) =>
      bffFetch<NewsSource>("/api/v1/news/sources", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      }),
    onSuccess: invalidateSources,
  });

  const updateMutation = useMutation({
    mutationFn: ({
      id,
      ...data
    }: {
      id: string;
      name?: string;
      source_type?: string;
      url_pattern?: string;
      trust_level?: number;
      is_active?: boolean;
    }) =>
      bffFetch<NewsSource>(`/api/v1/news/sources/${id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      }),
    onSuccess: invalidateSources,
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => bffFetch<void>(`/api/v1/news/sources/${id}`, { method: "DELETE" }),
    onSuccess: invalidateSources,
  });

  return { createMutation, updateMutation, deleteMutation };
}

export function useNewsPortfolioImpacts() {
  return useQuery({
    queryKey: [...queryKeys.newsItems(), "portfolio-impacts"],
    queryFn: () => bffFetch<PortfolioImpact[]>("/api/v1/news/portfolio-impacts"),
    staleTime: 30_000,
    refetchOnWindowFocus: false,
  });
}
