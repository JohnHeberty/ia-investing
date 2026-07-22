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
      <section className="rounded-xl border border-slate-800 bg-slate-950 p-6">
        <h2 className="text-lg font-semibold text-slate-100">Top carteiras</h2>
        <p className="mt-2 text-sm text-slate-400">
          Nenhuma carteira atende aos gates de ranking. Consulte &ldquo;Excluídas&rdquo; para ver NAV,
          backtest, risco, cobertura de tese ou confiança de dados pendentes.
        </p>
      </section>
    );
  }

  return (
    <div className="overflow-x-auto rounded-xl border border-slate-800 bg-slate-950">
      <table className="min-w-full text-sm">
        <caption className="sr-only">Ranking auditável de carteiras por coorte</caption>
        <thead className="border-b border-slate-800 text-left text-xs uppercase tracking-wide text-slate-400">
          <tr>
            <th className="px-4 py-3">Posição</th>
            <th className="px-4 py-3">Carteira</th>
            <th className="px-4 py-3">Coorte</th>
            <th className="px-4 py-3 text-right">Score</th>
            <th className="px-4 py-3 text-right">NAV</th>
            <th className="px-4 py-3 text-right">Volatilidade</th>
            <th className="px-4 py-3 text-right">Drawdown</th>
            <th className="px-4 py-3 text-right">Teses</th>
            <th className="px-4 py-3 text-right">Dados</th>
            <th className="px-4 py-3">Estado</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-900">
          {items.map((item) => (
            <tr key={item.portfolio_id} className="hover:bg-slate-900/60">
              <td className="px-4 py-3 font-mono tabular-nums text-slate-300">#{item.rank ?? "–"}</td>
              <td className="px-4 py-3">
                <Link className="font-medium text-slate-100 hover:underline" href={`/portfolios/${item.portfolio_id}`}>
                  {item.name}
                </Link>
                <div className="text-xs text-slate-500">{item.environment.toUpperCase()}</div>
              </td>
              <td className="px-4 py-3 text-slate-300">
                <div>{item.category}</div>
                <div className="text-xs text-slate-500">{item.benchmark} · {item.risk_class}</div>
              </td>
              <td className="px-4 py-3 text-right font-mono tabular-nums text-slate-100">
                {formatPercent(item.score)}
              </td>
              <td className="px-4 py-3 text-right font-mono tabular-nums text-slate-300">
                {item.nav === null
                  ? "Indisponível"
                  : new Intl.NumberFormat("pt-BR", {
                      style: "currency",
                      currency: item.currency,
                      maximumFractionDigits: 0,
                    }).format(Number(item.nav))}
              </td>
              <td className="px-4 py-3 text-right font-mono tabular-nums text-slate-300">
                {formatPercent(item.volatility)}
              </td>
              <td className="px-4 py-3 text-right font-mono tabular-nums text-slate-300">
                {formatPercent(item.drawdown)}
              </td>
              <td className="px-4 py-3 text-right font-mono tabular-nums text-slate-300">
                {formatPercent(item.thesis_coverage)}
              </td>
              <td className="px-4 py-3 text-right font-mono tabular-nums text-slate-300">
                {formatPercent(item.data_confidence)}
              </td>
              <td className="px-4 py-3">
                <span className="rounded-full border border-slate-700 px-2 py-1 text-xs text-slate-300">
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
