import * as Tabs from "@radix-ui/react-tabs";
import { Clock3 } from "lucide-react";
import type { ReactNode } from "react";

export function AsOfIndicator({
  value = "18 jul 2026 · 18:05 BRT",
  freshness = "Atual",
}: {
  value?: string;
  freshness?: string;
}) {
  return (
    <div className="asof" title="Data e hora do conjunto de dados">
      <span className="pulse" /> <Clock3 size={12} /> as of {value} · {freshness}
    </div>
  );
}
export function Badge({
  children,
  tone = "neutral",
}: {
  children: ReactNode;
  tone?: "neutral" | "good" | "warn" | "bad";
}) {
  return (
    <span className="badge" data-tone={tone}>
      {children}
    </span>
  );
}
export function Metric({
  label,
  value,
  note,
  tone,
}: {
  label: string;
  value: string;
  note: string;
  tone?: string;
}) {
  return (
    <article className="card metric">
      <div className="metric-label">{label}</div>
      <div className={`metric-value ${tone ?? ""}`}>{value}</div>
      <div className="metric-note">{note}</div>
    </article>
  );
}
export type DataState =
  "empty" | "missing" | "stale" | "partial" | "quarantined" | "forbidden" | "error";

export function StatePanel({
  title,
  detail,
  state = "empty",
}: {
  title: string;
  detail: string;
  state?: DataState;
}) {
  return (
    <div className="state-panel" data-state={state} role={state === "error" ? "alert" : "status"}>
      <strong>{title}</strong>
      <span>{detail}</span>
    </div>
  );
}

export type DomainTab = { id: string; label: string; content: ReactNode };

export function DomainTabs({ label, tabs }: { label: string; tabs: DomainTab[] }) {
  if (!tabs.length) return null;
  return (
    <Tabs.Root className="domain-tabs" defaultValue={tabs[0].id}>
      <Tabs.List aria-label={label} className="tab-list" tabIndex={0}>
        {tabs.map((tab) => (
          <Tabs.Trigger className="tab-trigger" key={tab.id} value={tab.id}>
            {tab.label}
          </Tabs.Trigger>
        ))}
      </Tabs.List>
      {tabs.map((tab) => (
        <Tabs.Content className="tab-content" key={tab.id} value={tab.id}>
          {tab.content}
        </Tabs.Content>
      ))}
    </Tabs.Root>
  );
}
