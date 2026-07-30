import type { DriftItem } from "@/hooks/use-rebalance";

export const percent = new Intl.NumberFormat("pt-BR", {
  style: "percent",
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
});
export const money = new Intl.NumberFormat("pt-BR", {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 0,
});
export const dateTime = new Intl.DateTimeFormat("pt-BR", {
  dateStyle: "short",
  timeStyle: "short",
});

export function pct(value: number): string {
  return percent.format(value / 100);
}

export function DriftBadge({ severity }: { severity: DriftItem["severity"] }) {
  const tone = severity === "green" ? "good" : severity === "yellow" ? "warn" : "bad";
  return (
    <span className="badge" data-tone={tone}>
      {severity === "green" ? "<1%" : severity === "yellow" ? "1-3%" : ">3%"}
    </span>
  );
}

export function SideBadge({ side }: { side: "buy" | "sell" }) {
  return (
    <span className="badge" data-tone={side === "buy" ? "good" : "bad"}>
      {side.toUpperCase()}
    </span>
  );
}

export function StatusBadge({ status }: { status: string }) {
  const toneMap: Record<string, string> = {
    draft: "neutral",
    approved: "info",
    in_progress: "warn",
    completed: "good",
    cancelled: "bad",
  };
  return (
    <span className="badge" data-tone={toneMap[status] ?? "neutral"}>
      {status.replaceAll("_", " ")}
    </span>
  );
}
