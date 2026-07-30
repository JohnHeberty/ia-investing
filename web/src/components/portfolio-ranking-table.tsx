import Link from "next/link";

import type { PortfolioRankItem } from "@/hooks/use-mission-control";

const percent = new Intl.NumberFormat("pt-BR", {
  style: "percent",
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
});
function asNumber(value: string | null): number | null {
  if (value === null) return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function formatPercent(value: string | null): string {
  const parsed = asNumber(value);
  return parsed === null ? "Indisponível" : percent.format(parsed);
}

export function PortfolioRankingTable({ items }: { items: PortfolioRankItem[] }) {
  if (items.length === 0) {
    return (
      <section style={{ borderRadius: 10, border: "1px solid var(--line)", background: "var(--surface)", padding: 24 }}>
        <h2 style={{ fontSize: 18, fontWeight: 600, color: "var(--text)" }}>Top carteiras</h2>
        <p style={{ marginTop: 8, fontSize: 14, color: "var(--muted)" }}>
          Nenhuma carteira atende aos gates de ranking. Consulte &ldquo;Excluídas&rdquo; para ver NAV,
          backtest, risco, cobertura de tese ou confiança de dados pendentes.
        </p>
      </section>
    );
  }

  return (
    <div style={{ overflowX: "auto", borderRadius: 10, border: "1px solid var(--line)", background: "var(--surface)" }}>
      <table style={{ minWidth: "100%", fontSize: 14 }}>
        <caption className="sr-only">Ranking auditável de carteiras por coorte</caption>
        <thead style={{ borderBottom: "1px solid var(--line)", textAlign: "left", fontSize: 12, textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--muted)" }}>
          <tr>
            <th style={{ padding: "12px 16px" }}>Posição</th>
            <th style={{ padding: "12px 16px" }}>Carteira</th>
            <th style={{ padding: "12px 16px" }}>Coorte</th>
            <th style={{ padding: "12px 16px", textAlign: "right" }}>Score</th>
            <th style={{ padding: "12px 16px", textAlign: "right" }}>NAV</th>
            <th style={{ padding: "12px 16px", textAlign: "right" }}>Volatilidade</th>
            <th style={{ padding: "12px 16px", textAlign: "right" }}>Drawdown</th>
            <th style={{ padding: "12px 16px", textAlign: "right" }}>Teses</th>
            <th style={{ padding: "12px 16px", textAlign: "right" }}>Dados</th>
            <th style={{ padding: "12px 16px" }}>Estado</th>
          </tr>
        </thead>
        <tbody style={{ color: "var(--muted)" }}>
          {items.map((item) => (
            <tr key={item.portfolio_id} style={{ borderBottom: "1px solid var(--line-soft)" }}>
              <td style={{ padding: "12px 16px", fontFamily: "var(--font-mono, monospace)", fontVariantNumeric: "tabular-nums", color: "var(--text)" }}>#{item.rank ?? "–"}</td>
              <td style={{ padding: "12px 16px" }}>
                <Link style={{ fontWeight: 500, color: "var(--text)" }} href={`/portfolios/${item.portfolio_id}`}>
                  {item.name}
                </Link>
                <div style={{ fontSize: 12, color: "var(--muted-2)" }}>{item.environment.toUpperCase()}</div>
              </td>
              <td style={{ padding: "12px 16px", color: "var(--text)" }}>
                <div>{item.category}</div>
                <div style={{ fontSize: 12, color: "var(--muted-2)" }}>{item.benchmark} · {item.risk_class}</div>
              </td>
              <td style={{ padding: "12px 16px", textAlign: "right", fontFamily: "var(--font-mono, monospace)", fontVariantNumeric: "tabular-nums", color: "var(--text)" }}>
                {formatPercent(item.score)}
              </td>
              <td style={{ padding: "12px 16px", textAlign: "right", fontFamily: "var(--font-mono, monospace)", fontVariantNumeric: "tabular-nums", color: "var(--text)" }}>
                {(() => {
                  if (item.nav === null) return "Indisponível";
                  const nav = Number(item.nav);
                  if (!Number.isFinite(nav)) return "Indisponível";
                  return new Intl.NumberFormat("pt-BR", {
                    style: "currency",
                    currency: item.currency || "BRL",
                    maximumFractionDigits: 0,
                  }).format(nav);
                })()}
              </td>
              <td style={{ padding: "12px 16px", textAlign: "right", fontFamily: "var(--font-mono, monospace)", fontVariantNumeric: "tabular-nums", color: "var(--text)" }}>
                {formatPercent(item.volatility)}
              </td>
              <td style={{ padding: "12px 16px", textAlign: "right", fontFamily: "var(--font-mono, monospace)", fontVariantNumeric: "tabular-nums", color: "var(--text)" }}>
                {formatPercent(item.drawdown)}
              </td>
              <td style={{ padding: "12px 16px", textAlign: "right", fontFamily: "var(--font-mono, monospace)", fontVariantNumeric: "tabular-nums", color: "var(--text)" }}>
                {formatPercent(item.thesis_coverage)}
              </td>
              <td style={{ padding: "12px 16px", textAlign: "right", fontFamily: "var(--font-mono, monospace)", fontVariantNumeric: "tabular-nums", color: "var(--text)" }}>
                {formatPercent(item.data_confidence)}
              </td>
              <td style={{ padding: "12px 16px" }}>
                <span style={{ borderRadius: 999, border: "1px solid var(--line)", padding: "4px 8px", fontSize: 12, color: "var(--muted)" }}>
                  {item.stage}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
