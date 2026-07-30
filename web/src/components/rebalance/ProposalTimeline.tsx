import type { RebalanceProposal } from "@/hooks/use-rebalance";
import { StatusBadge, dateTime } from "./shared";

export function ProposalTimeline({ items }: { items: RebalanceProposal[] }) {
  if (items.length === 0) {
    return <p style={{ fontSize: 14, color: "var(--muted)" }}>Nenhum rebalanceamento anterior.</p>;
  }
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      {items.map((item) => (
        <div
          key={item.id}
          className="event"
          style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}
        >
          <div>
            <div style={{ fontSize: 14, fontWeight: 500, color: "var(--text)" }}>
              Proposta {item.id.slice(0, 8)}
            </div>
            <div style={{ marginTop: 4, fontSize: 12, color: "var(--muted-2)" }}>
              {dateTime.format(new Date(item.created_at))}
            </div>
          </div>
          <StatusBadge status={item.status} />
        </div>
      ))}
    </div>
  );
}
