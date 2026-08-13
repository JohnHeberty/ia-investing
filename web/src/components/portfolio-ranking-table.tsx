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
      <section className="card" style={{ borderRadius: 10, padding: 24 }}>
        <h2 className="text-sm fw-500" style={{ fontSize: 18 }}>
          Top carteiras
        </h2>
        <p className="muted text-sm mt-8">
          Nenhuma carteira atende aos gates de ranking. Consulte &ldquo;Excluídas&rdquo; para ver
          NAV, backtest, risco, cobertura de tese ou confiança de dados pendentes.
        </p>
      </section>
    );
  }

  return (
    <div className="card" style={{ overflowX: "auto", borderRadius: 10 }}>
      <table style={{ minWidth: "100%" }} className="text-sm">
        <caption className="sr-only">Ranking auditável de carteiras por coorte</caption>
        <thead
          style={{
            borderBottom: "1px solid var(--line)",
            textAlign: "left",
            textTransform: "uppercase",
            letterSpacing: "0.05em",
            color: "var(--muted)",
          }}
        >
          <tr>
            <th style={{ padding: "12px 16px" }}>Posição</th>
            <th style={{ padding: "12px 16px" }}>Carteira</th>
            <th style={{ padding: "12px 16px" }}>Coorte</th>
            <th className="text-right" style={{ padding: "12px 16px" }}>
              Score
            </th>
            <th className="text-right" style={{ padding: "12px 16px" }}>
              NAV
            </th>
            <th className="text-right" style={{ padding: "12px 16px" }}>
              Volatilidade
            </th>
            <th className="text-right" style={{ padding: "12px 16px" }}>
              Drawdown
            </th>
            <th className="text-right" style={{ padding: "12px 16px" }}>
              Teses
            </th>
            <th className="text-right" style={{ padding: "12px 16px" }}>
              Dados
            </th>
            <th style={{ padding: "12px 16px" }}>Estado</th>
          </tr>
        </thead>
        <tbody className="muted">
          {items.map((item) => (
            <tr key={item.portfolio_id} style={{ borderBottom: "1px solid var(--line-soft)" }}>
              <td className="mono" style={{ padding: "12px 16px", color: "var(--text)" }}>
                #{item.rank ?? "–"}
              </td>
              <td style={{ padding: "12px 16px" }}>
                <Link
                  className="fw-500"
                  style={{ color: "var(--text)" }}
                  href={`/portfolios/${item.portfolio_id}`}
                >
                  {item.name}
                </Link>
                <div className="text-sm muted" style={{ color: "var(--muted-2)" }}>
                  {item.environment.toUpperCase()}
                </div>
              </td>
              <td style={{ padding: "12px 16px", color: "var(--text)" }}>
                <div>{item.category}</div>
                <div className="text-sm muted" style={{ color: "var(--muted-2)" }}>
                  {item.benchmark} · {item.risk_class}
                </div>
              </td>
              <td
                className="mono text-right"
                style={{ padding: "12px 16px", color: "var(--text)" }}
              >
                {formatPercent(item.score)}
              </td>
              <td
                className="mono text-right"
                style={{ padding: "12px 16px", color: "var(--text)" }}
              >
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
              <td
                className="mono text-right"
                style={{ padding: "12px 16px", color: "var(--text)" }}
              >
                {formatPercent(item.volatility)}
              </td>
              <td
                className="mono text-right"
                style={{ padding: "12px 16px", color: "var(--text)" }}
              >
                {formatPercent(item.drawdown)}
              </td>
              <td
                className="mono text-right"
                style={{ padding: "12px 16px", color: "var(--text)" }}
              >
                {formatPercent(item.thesis_coverage)}
              </td>
              <td
                className="mono text-right"
                style={{ padding: "12px 16px", color: "var(--text)" }}
              >
                {formatPercent(item.data_confidence)}
              </td>
              <td style={{ padding: "12px 16px" }}>
                <span className="badge text-sm muted">{item.stage}</span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
