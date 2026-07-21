"use client";

import { useCallback, useMemo } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

/**
 * Hook for reading/writing URL search params as typed state.
 * Supports filters, sorting, pagination, and tabs.
 */
export function useUrlState<T extends Record<string, string | string[] | undefined>>(defaults: T) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const state = useMemo(() => {
    const result = {} as Record<string, string | string[] | undefined>;
    for (const [key, defaultValue] of Object.entries(defaults)) {
      const param = searchParams.get(key);
      if (param === null) {
        result[key] = defaultValue;
      } else if (Array.isArray(defaultValue)) {
        result[key] = searchParams.getAll(key);
      } else {
        result[key] = param;
      }
    }
    return result as T;
  }, [searchParams, defaults]);

  const setState = useCallback(
    (updates: Partial<T>) => {
      const params = new URLSearchParams(searchParams.toString());
      for (const [key, value] of Object.entries(updates)) {
        if (value === undefined || value === null || value === "" || value === defaults[key]) {
          params.delete(key);
        } else if (Array.isArray(value)) {
          params.delete(key);
          for (const v of value) {
            params.append(key, v);
          }
        } else {
          params.set(key, String(value));
        }
      }
      const qs = params.toString();
      router.push(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
    },
    [router, pathname, searchParams, defaults],
  );

  return [state, setState] as const;
}

/**
 * Preset filter configurations for common pages.
 */
export const filterPresets = {
  missionControl: {
    category: undefined as string | undefined,
    sortBy: "confidence" as string | undefined,
    status: undefined as string | undefined,
    eligibility: "eligible" as string | undefined,
  },
  portfolio: {
    tab: "positions" as string | undefined,
    sortBy: "weight" as string | undefined,
    sortDir: "desc" as string | undefined,
  },
  asset: {
    tab: "metrics" as string | undefined,
    evidenceFilter: "all" as string | undefined,
  },
  opportunities: {
    stage: undefined as string | undefined,
    materiality: undefined as string | undefined,
    sortBy: "score" as string | undefined,
  },
  risk: {
    severity: undefined as string | undefined,
    type: undefined as string | undefined,
  },
  agents: {
    status: undefined as string | undefined,
    capability: undefined as string | undefined,
    page: "1" as string | undefined,
  },
  dataQuality: {
    source: undefined as string | undefined,
    status: undefined as string | undefined,
  },
} as const;
