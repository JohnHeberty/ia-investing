import { ArrowDownRight, ArrowUpRight, Minus } from "lucide-react";

export type DiffEntry = {
  ticker: string;
  name: string;
  currentWeight: number;
  targetWeight: number;
  action: "buy" | "sell" | "hold" | "new" | "exit";
};

/**
 * Portfolio diff table showing before/after weights and actions.
 */
export function PortfolioDiff({ entries }: { entries: DiffEntry[] }) {
  return (
    <div className="card card-pad">
      <div className="card-title">
        <h2>Proposta de rebalanceamento</h2>
        <span>{entries.length} ativos</span>
      </div>
      <div className="table-wrap">
        <table className="table">
          <thead>
            <tr>
              <th>Ativo</th>
              <th className="numeric">Atual</th>
              <th className="numeric">Proposto</th>
              <th className="numeric">Δ</th>
              <th>Ação</th>
            </tr>
          </thead>
          <tbody>
            {entries.map((entry) => {
              const delta = entry.targetWeight - entry.currentWeight;
              return (
                <tr key={entry.ticker}>
                  <td>
                    <div style={{ fontWeight: 600 }}>{entry.ticker}</div>
                    <div style={{ fontSize: 11, color: "var(--muted)" }}>{entry.name}</div>
                  </td>
                  <td className="numeric" style={{ fontFamily: "var(--font-mono)" }}>
                    {entry.currentWeight.toFixed(1)}%
                  </td>
                  <td className="numeric" style={{ fontFamily: "var(--font-mono)" }}>
                    {entry.targetWeight.toFixed(1)}%
                  </td>
                  <td
                    className={`numeric ${delta > 0 ? "positive" : delta < 0 ? "negative" : ""}`}
                    style={{ fontFamily: "var(--font-mono)" }}
                  >
                    {delta > 0 ? "+" : ""}
                    {delta.toFixed(1)}%
                  </td>
                  <td>
                    <ActionIcon action={entry.action} />
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function ActionIcon({ action }: { action: DiffEntry["action"] }) {
  const config = {
    buy: { icon: <ArrowUpRight size={14} />, color: "var(--accent)", label: "Compra" },
    sell: { icon: <ArrowDownRight size={14} />, color: "var(--red)", label: "Venda" },
    hold: { icon: <Minus size={14} />, color: "var(--muted)", label: "Mantém" },
    new: { icon: <ArrowUpRight size={14} />, color: "var(--blue)", label: "Novo" },
    exit: { icon: <ArrowDownRight size={14} />, color: "var(--red)", label: "Saída" },
  };
  const { icon, color, label } = config[action];
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 4, color, fontSize: 12 }}>
      {icon} {label}
    </span>
  );
}

/**
 * Scenario waterfall chart showing impact of risk scenarios.
 */
export type ScenarioEntry = {
  name: string;
  impact: number;
  cumulative: number;
};

export function ScenarioWaterfall({ scenarios }: { scenarios: ScenarioEntry[] }) {
  const maxAbs = Math.max(...scenarios.map((s) => Math.abs(s.impact)), 1);
  return (
    <div className="card card-pad">
      <div className="card-title">
        <h2>Waterfall de cenários</h2>
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        {scenarios.map((scenario) => {
          const width = (Math.abs(scenario.impact) / maxAbs) * 100;
          const isPositive = scenario.impact >= 0;
          return (
            <div key={scenario.name} style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12 }}>
              <span style={{ minWidth: 140, color: "var(--muted)" }}>{scenario.name}</span>
              <div style={{ flex: 1, position: "relative", height: 16 }}>
                <div
                  style={{
                    position: "absolute",
                    left: isPositive ? "50%" : `${50 - width / 2}%`,
                    width: `${width / 2}%`,
                    height: "100%",
                    background: isPositive ? "var(--accent)" : "var(--red)",
                    borderRadius: 3,
                    opacity: 0.8,
                  }}
                />
              </div>
              <span
                className={`numeric ${isPositive ? "positive" : "negative"}`}
                style={{ minWidth: 50, textAlign: "right", fontFamily: "var(--font-mono)" }}
              >
                {isPositive ? "+" : ""}
                {(scenario.impact * 100).toFixed(1)}%
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

/**
 * Approval card showing decision status with four-eyes principle.
 */
export type ApprovalStatus = "pending" | "approved" | "rejected" | "expired" | "conditional";

export function ApprovalCard({
  title,
  description,
  status,
  requestedBy,
  requestedAt,
  decidedBy,
  decidedAt,
  reason,
  conditions,
}: {
  title: string;
  description: string;
  status: ApprovalStatus;
  requestedBy: string;
  requestedAt: string;
  decidedBy?: string;
  decidedAt?: string;
  reason?: string;
  conditions?: string[];
}) {
  const statusConfig = {
    pending: { label: "Pendente", tone: "warn" as const },
    approved: { label: "Aprovado", tone: "good" as const },
    rejected: { label: "Rejeitado", tone: "bad" as const },
    expired: { label: "Expirado", tone: "neutral" as const },
    conditional: { label: "Condicionado", tone: "warn" as const },
  };
  const { label, tone } = statusConfig[status];
  return (
    <article className="card card-pad" style={{ borderLeft: `3px solid var(--${tone === "good" ? "accent" : tone === "warn" ? "amber" : tone === "bad" ? "red" : "muted"})` }}>
      <div className="card-title">
        <h3 style={{ fontSize: 14 }}>{title}</h3>
        <span className="badge" data-tone={tone}>{label}</span>
      </div>
      <p style={{ color: "var(--muted)", fontSize: 12, marginBottom: 12 }}>{description}</p>
      <div style={{ display: "flex", gap: 16, fontSize: 11, color: "var(--muted)" }}>
        <span>Solicitado por: <strong style={{ color: "var(--text)" }}>{requestedBy}</strong></span>
        <span>{requestedAt}</span>
      </div>
      {decidedBy && (
        <div style={{ display: "flex", gap: 16, fontSize: 11, color: "var(--muted)", marginTop: 4 }}>
          <span>Decidido por: <strong style={{ color: "var(--text)" }}>{decidedBy}</strong></span>
          <span>{decidedAt}</span>
        </div>
      )}
      {reason && (
        <p style={{ fontSize: 12, marginTop: 8, padding: 8, background: "var(--surface-2)", borderRadius: 6 }}>
          Razão: {reason}
        </p>
      )}
      {conditions && conditions.length > 0 && (
        <div style={{ marginTop: 8 }}>
          <span style={{ fontSize: 11, color: "var(--muted)" }}>Condições:</span>
          <ul style={{ margin: "4px 0 0 16px", padding: 0, fontSize: 12 }}>
            {conditions.map((c, i) => (
              <li key={i}>{c}</li>
            ))}
          </ul>
        </div>
      )}
    </article>
  );
}
