"use client";

import { PortfolioRankingTable } from "@/components/portfolio-ranking-table";
import { useMissionControl } from "@/hooks/use-mission-control";

export default function PortfoliosPage() {
  const query = useMissionControl();

  if (query.isPending) {
    return <main className="p-6 text-slate-400">Carregando carteiras e gates de elegibilidade…</main>;
  }
  if (query.isError) {
    return (
      <main className="p-6">
        <h1 className="text-2xl font-semibold text-slate-100">Carteiras</h1>
        <div role="alert" className="mt-6 rounded-xl border border-red-900 bg-red-950/50 p-4 text-red-200">
          {query.error.message}
        </div>
      </main>
    );
  }

  const data = query.data;
  return (
    <main className="space-y-8 p-6">
      <header>
        <p className="text-xs uppercase tracking-[0.2em] text-slate-500">Portfolio Intelligence</p>
        <h1 className="mt-2 text-3xl font-semibold text-slate-100">Top carteiras</h1>
        <p className="mt-2 max-w-3xl text-sm text-slate-400">
          Ranking por coortes comparáveis. O score só é publicado após NAV reconciliado,
          backtest point-in-time, versão aprovada, cobertura de tese e gates de risco.
        </p>
      </header>

      <PortfolioRankingTable items={data.top_portfolios} />

      <section className="rounded-xl border border-slate-800 bg-slate-950 p-5">
        <h2 className="text-lg font-semibold text-slate-100">Excluídas do ranking</h2>
        <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {data.excluded_portfolios.map((item) => (
            <article key={item.portfolio_id} className="rounded-lg border border-slate-800 p-4">
              <div className="font-medium text-slate-100">{item.name}</div>
              <div className="mt-1 text-xs text-slate-500">{item.category} · {item.benchmark}</div>
              <ul className="mt-3 space-y-1 text-xs text-amber-200">
                {item.exclusion_reasons.map((reason) => <li key={reason}>{reason}</li>)}
              </ul>
            </article>
          ))}
          {data.excluded_portfolios.length === 0 && (
            <p className="text-sm text-slate-400">Nenhuma carteira excluída.</p>
          )}
        </div>
      </section>
    </main>
  );
}
