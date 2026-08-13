import { renderHook } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, expect, it, vi } from "vitest";
import React, { type ReactNode } from "react";

import { useSourceHealthSummary } from "./use-source-health-summary";

vi.mock("@/lib/api-client", () => ({
  bffFetch: vi.fn(),
  queryKeys: {
    sourceHealth: () => ["sourceHealth"] as const,
  },
}));

const mockUseQuery = vi.fn();
vi.mock("@tanstack/react-query", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@tanstack/react-query")>();
  return { ...actual, useQuery: (...args: unknown[]) => mockUseQuery(...args) };
});

function makeWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
  };
}

describe("useSourceHealthSummary", () => {
  it("computes staleCount and healthyCount from source data", () => {
    mockUseQuery.mockReturnValue({
      data: [
        { code: "a", status: "healthy", name: "A" },
        { code: "b", status: "stale", name: "B" },
        { code: "c", status: "never_succeeded", name: "C" },
        { code: "d", status: "healthy", name: "D" },
      ],
      isLoading: false,
      isError: false,
      error: null,
    });

    const { result } = renderHook(() => useSourceHealthSummary(), { wrapper: makeWrapper() });

    expect(result.current.totalSources).toBe(4);
    expect(result.current.healthyCount).toBe(2);
    expect(result.current.staleCount).toBe(2);
    expect(result.current.sources).toHaveLength(4);
  });

  it("returns zero counts when no data", () => {
    mockUseQuery.mockReturnValue({
      data: [],
      isLoading: false,
      isError: false,
      error: null,
    });

    const { result } = renderHook(() => useSourceHealthSummary(), { wrapper: makeWrapper() });

    expect(result.current.totalSources).toBe(0);
    expect(result.current.healthyCount).toBe(0);
    expect(result.current.staleCount).toBe(0);
  });

  it("returns empty breaches array", () => {
    mockUseQuery.mockReturnValue({
      data: [{ code: "a", status: "healthy", name: "A" }],
      isLoading: false,
      isError: false,
      error: null,
    });

    const { result } = renderHook(() => useSourceHealthSummary(), { wrapper: makeWrapper() });

    expect(result.current.assessment.breaches).toEqual([]);
    expect(result.current.assessment.snapshot_id).toBe("latest");
  });

  it("exposes loading state", () => {
    mockUseQuery.mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
      error: null,
    });

    const { result } = renderHook(() => useSourceHealthSummary(), { wrapper: makeWrapper() });

    expect(result.current.isLoading).toBe(true);
  });
});
