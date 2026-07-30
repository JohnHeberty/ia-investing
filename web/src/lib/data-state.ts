import type { DataState } from "@/components/domain";

const STALE_THRESHOLD_MS = 24 * 60 * 60 * 1000;

export function computeDataState(
  isLoading: boolean,
  isError: boolean,
  latestAsOf: string | null,
  hasData: boolean,
): DataState {
  if (isLoading) return "empty";
  if (isError) return "error";
  if (!hasData) return "empty";
  if (latestAsOf) {
    const age = Date.now() - new Date(latestAsOf).getTime();
    if (age > STALE_THRESHOLD_MS) return "stale";
  }
  return "ready";
}
