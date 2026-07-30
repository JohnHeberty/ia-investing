import type { RebalanceTrade } from "@/hooks/use-rebalance";
import { pct, money, SideBadge, StatusBadge } from "./shared";

export function TradesTable({
  trades,
  selected,
  onToggle,
}: {
  trades: RebalanceTrade[];
  selected: Set<string>;
  onToggle: (id: string) => void;
}) {
  if (trades.length === 0) {
    return <p style={{ fontSize: 14, color: "var(--muted)" }}>Nenhuma trade calculada.</p>;
  }
  return (
    <table className="table">
      <thead>
        <tr>
          <th style={{ width: 40 }} />
          <th>Ordem</th>
          <th>Ticker</th>
          <th>Side</th>
          <th>Atual → Target</th>
          <th>Delta</th>
          <th>Valor estimado</th>
          <th>Status</th>
        </tr>
      </thead>
      <tbody>
        {trades.map((trade) => (
          <tr key={trade.id}>
            <td>
              {trade.status === "pending" && (
                <input
                  type="checkbox"
                  checked={selected.has(trade.id)}
                  onChange={() => onToggle(trade.id)}
                  style={{ width: 16, height: 16, accentColor: "var(--accent)" }}
                />
              )}
            </td>
            <td style={{ textAlign: "center", fontSize: 12, color: "var(--muted-2)" }}>{trade.execution_order}</td>
            <td style={{ fontWeight: 500, color: "var(--text)" }}>{trade.ticker}</td>
            <td><SideBadge side={trade.side} /></td>
            <td>
              {pct(trade.current_weight)} → {pct(trade.target_weight)}
            </td>
            <td style={{ fontFamily: "var(--font-mono)", color: trade.delta > 0 ? "var(--accent)" : "var(--red)" }}>
              {trade.delta > 0 ? "+" : ""}{pct(trade.delta)}
            </td>
            <td style={{ fontFamily: "var(--font-mono)", color: "var(--text)" }}>{money.format(trade.estimated_value)}</td>
            <td><StatusBadge status={trade.status} /></td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
