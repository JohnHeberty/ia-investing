import type { DriftItem } from "@/hooks/use-rebalance";
import { DriftBadge, pct } from "./shared";

export function DriftTable({ items }: { items: DriftItem[] }) {
  if (items.length === 0) {
    return <p style={{ fontSize: 14, color: "var(--muted)" }}>Nenhum desvio detectado.</p>;
  }
  return (
    <table className="table">
      <thead>
        <tr>
          <th>Ticker</th>
          <th>Atual</th>
          <th>Target</th>
          <th>Desvio</th>
          <th>Severidade</th>
        </tr>
      </thead>
      <tbody>
        {items.map((item) => (
          <tr key={item.ticker}>
            <td style={{ fontWeight: 500, color: "var(--text)" }}>{item.ticker}</td>
            <td>{pct(item.current_weight)}</td>
            <td>{pct(item.target_weight)}</td>
            <td style={{ fontFamily: "var(--font-mono)" }}>{pct(item.drift)}</td>
            <td><DriftBadge severity={item.severity} /></td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
