"use client";

import Link from "next/link";

import { PortfolioRankingTable } from "@/components/portfolio-ranking-table";
import { useMissionControl } from "@/hooks/use-mission-control";

const integer = new Intl.NumberFormat("pt-BR");
const money = new Intl.NumberFormat("pt-BR", {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 2,
});
const percent = new Intl.NumberFormat("pt-BR", {
  style: "percent",
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
});
const dateTime = new Intl.DateTimeFormat("pt-BR", {
  dateStyle: "short",
  timeStyle: "short",
});

function percentage(value: string | null): string {
  if (value === null) return "Não medido";
  const parsed = Number(value);
  return Number.isFinite(parsed) ? percent.format(parsed) : "Inválido";
}

function StatusCard({
  label,
  value,
  detail,
  critical = false,
}: {
  label: string;
  value: string;
  detail: string;
  critical?: boolean;
}) {
  return (
    <article className={`rounded-xl border p-4 ${critical ? "border-red-900 bg-red-950/30" : "border-slate-800 bg-slate-950"}`}>
      <div className="text-xs uppercase tracking-wide text-slate-500">{label}</div>
      <div className={`mt-2 text-3xl font-semibold tabular-nums ${critical ? "text-red-200" : "text-slate-100"}`}>
        {value}
      </div>
      <p className="mt-2 text-xs text-slate-400">{detail}</p>
    </article>
  );
}

export default function MissionControlPage() {
  const query = useMissionControl();

  if (query.isPending) {
    return <main className="p-6 text-slate-400">Consolidando carteiras, risco, fontes, pesquisa e agents…</main>;
  }
  if (query.isError) {
    return (
      <main className="p-6">
        <h1 className="text-2xl font-semibold text-slate-100">Mission Control</h1>
        <div role="alert" className="mt-6 rounded-xl border border-red-900 bg-red-950/50 p-4 text-red-200">
          {query.error.message}
        </div>
      </main>
    );
  }

  const data = query.data;
  const unhealthySources = data.source_health.filter((source) => source.status !== "healthy");
  const funnelTotal = Object.values(data.research_funnel).reduce((sum, count) => sum + count, 0);
  const cohorts = new Set(data.top_portfolios.map((portfolio) => portfolio.cohort_key)).size;

  return (
    <main className="space-y-8 p-6">
      <header className="flex flex-col gap-4 border-b border-slate-800 pb-6 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="text-xs uppercase tracking-[0.2em] text-slate-500">IA Investing OS</p>
          <h1 className="mt-2 text-3xl font-semibold text-slate-100">Mission Control</h1>
          <p className="mt-2 max-w-3xl text-sm text-slate-400">
            Uma visão operacional única de carteiras, risco, pesquisa, fontes e execução dos agents. Nenhum score é
            publicado sem os gates institucionais de dados, backtest, tese, risco e aprovação.
          </p>
        </div>
        <div className="text-xs text-slate-500">
          <div>Gerado em {dateTime.format(new Date(data.generated_at))}</div>
          <div>Dados até {data.data_as_of ? dateTime.format(new Date(data.data_as_of)) : "indisponível"}</div>
        </div>
      </header>

      <section aria-label="Indicadores operacionais" className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
        <StatusCard
          label="Alertas críticos"
          value={integer.format(data.critical_alerts)}
          detail="Fontes problemáticas e violações duras abertas."
          critical={data.critical_alerts > 0}
        />
        <StatusCard
          label="Aprovações pendentes"
          value={integer.format(data.pending_approvals)}
          detail="Agents e carteiras aguardando decisão humana."
        />
        <StatusCard
          label="Carteiras elegíveis"
          value={integer.format(data.top_portfolios.length)}
          detail={`${cohorts} coorte(s) comparável(is).`}
        />
        <StatusCard
          label="Pesquisa ativa"
          value={integer.format(funnelTotal)}
          detail="Casos em todos os estados do funil de pesquisa."
        />
        <StatusCard
          label="Agents em execução"
          value={integer.format(data.agent_operations.running)}
          detail={`${integer.format(data.agent_operations.failed_24h)} falha(s) nas últimas 24 horas.`}
          critical={data.agent_operations.failed_24h > 0}
        />
      </section>

      {data.candidate_pipeline && (
        <section className="space-y-4">
          <div className="flex items-center justify-between gap-4">
            <div>
              <h2 className="text-xl font-semibold text-slate-100">Pipeline de candidatos</h2>
              <p className="mt-1 text-sm text-slate-400">Fluxo de investigação: da sugestão ao comitê de investimento.</p>
            </div>
            <Link className="text-sm text-blue-400 hover:underline" href="/opportunities/candidates">Abrir candidatos</Link>
          </div>
          <div className="grid gap-4 sm:grid-cols-3 xl:grid-cols-6">
            {[
              ["Total", data.candidate_pipeline.total, false],
              ["Aguardando", data.candidate_pipeline.awaiting_input, data.candidate_pipeline.awaiting_input > 0],
              ["Bloqueados", data.candidate_pipeline.blocked, data.candidate_pipeline.blocked > 0],
              ["Em comitê", data.candidate_pipeline.in_committee, false],
              ["Aprovados", data.candidate_pipeline.approved, false],
              ["Rejeitados", data.candidate_pipeline.rejected, false],
            ].map(([label, value, critical]) => (
              <article key={String(label)} className={`rounded-xl border p-4 ${critical ? "border-amber-900 bg-amber-950/30" : "border-slate-800 bg-slate-950"}`}>
                <div className="text-xs uppercase tracking-wide text-slate-500">{String(label)}</div>
                <div className={`mt-2 text-3xl font-semibold tabular-nums ${critical ? "text-amber-200" : "text-slate-100"}`}>
                  {integer.format(Number(value))}
                </div>
              </article>
            ))}
          </div>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-7">
            {Object.entries(data.candidate_pipeline.funnel_by_status).map(([status, count]) => (
              <div key={status} className="rounded-lg border border-slate-800 p-3">
                <div className="text-xs uppercase tracking-wide text-slate-500">{status.replaceAll("_", " ")}</div>
                <div className="mt-2 text-2xl font-semibold tabular-nums text-slate-100">{integer.format(count)}</div>
              </div>
            ))}
          </div>
        </section>
      )}

      <section className="space-y-4">
        <div className="flex items-center justify-between gap-4">
          <div>
            <h2 className="text-xl font-semibold text-slate-100">Top carteiras por coorte</h2>
            <p className="mt-1 text-sm text-slate-400">A posição é relativa apenas a carteiras com mandato e risco comparáveis.</p>
          </div>
          <Link className="text-sm text-blue-400 hover:underline" href="/portfolios">Ver ranking e exclusões</Link>
        </div>
        <PortfolioRankingTable items={data.top_portfolios} />
      </section>

      <section className="grid gap-6 xl:grid-cols-3">
        <article className="rounded-xl border border-slate-800 bg-slate-950 p-5">
          <h2 className="text-lg font-semibold text-slate-100">Risco</h2>
          <dl className="mt-4 space-y-3 text-sm">
            {[
              ["Violações duras", data.risk.open_hard_breaches],
              ["Violações flexíveis", data.risk.open_soft_breaches],
              ["Carteiras afetadas", data.risk.portfolios_with_breaches],
              ["Snapshots desatualizados", data.risk.stale_risk_snapshots],
            ].map(([label, value]) => (
              <div key={String(label)} className="flex justify-between border-b border-slate-900 pb-2">
                <dt className="text-slate-400">{label}</dt>
                <dd className="font-mono tabular-nums text-slate-100">{integer.format(Number(value))}</dd>
              </div>
            ))}
          </dl>
          <Link className="mt-5 inline-block text-sm text-blue-400 hover:underline" href="/risk">Abrir Risk Center</Link>
        </article>

        <article className="rounded-xl border border-slate-800 bg-slate-950 p-5">
          <h2 className="text-lg font-semibold text-slate-100">Agents</h2>
          <dl className="mt-4 space-y-3 text-sm">
            <div className="flex justify-between border-b border-slate-900 pb-2">
              <dt className="text-slate-400">Sucesso em 24h</dt>
              <dd className="font-mono text-slate-100">{integer.format(data.agent_operations.succeeded_24h)}</dd>
            </div>
            <div className="flex justify-between border-b border-slate-900 pb-2">
              <dt className="text-slate-400">Cobertura de evidências</dt>
              <dd className="font-mono text-slate-100">{percentage(data.agent_operations.evidence_coverage)}</dd>
            </div>
            <div className="flex justify-between border-b border-slate-900 pb-2">
              <dt className="text-slate-400">Schema pass rate</dt>
              <dd className="font-mono text-slate-100">{percentage(data.agent_operations.schema_pass_rate)}</dd>
            </div>
            <div className="flex justify-between border-b border-slate-900 pb-2">
              <dt className="text-slate-400">Custo em 24h</dt>
              <dd className="font-mono text-slate-100">{money.format(Number(data.agent_operations.cost_usd_24h))}</dd>
            </div>
          </dl>
          <Link className="mt-5 inline-block text-sm text-blue-400 hover:underline" href="/agents">Abrir operações dos agents</Link>
        </article>

        <article className="rounded-xl border border-slate-800 bg-slate-950 p-5">
          <h2 className="text-lg font-semibold text-slate-100">Qualidade das fontes</h2>
          <div className="mt-4 space-y-3">
            {unhealthySources.slice(0, 6).map((source) => (
              <div key={source.source_id} className="rounded-lg border border-slate-800 p-3">
                <div className="flex items-center justify-between gap-3">
                  <span className="text-sm font-medium text-slate-100">{source.name}</span>
                  <span className="rounded-full border border-amber-900 px-2 py-0.5 text-xs text-amber-200">{source.status}</span>
                </div>
                <div className="mt-1 text-xs text-slate-500">
                  {source.age_minutes === null ? "Nunca concluída" : `${integer.format(source.age_minutes)} min desde o último sucesso`}
                </div>
              </div>
            ))}
            {unhealthySources.length === 0 && <p className="text-sm text-emerald-300">Todas as fontes ativas estão dentro do SLA.</p>}
          </div>
          <Link className="mt-5 inline-block text-sm text-blue-400 hover:underline" href="/data-quality">Abrir Data Quality Center</Link>
        </article>
      </section>

      <section className="rounded-xl border border-slate-800 bg-slate-950 p-5">
        <h2 className="text-lg font-semibold text-slate-100">Funil de pesquisa</h2>
        <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-7">
          {Object.entries(data.research_funnel).map(([state, count]) => (
            <div key={state} className="rounded-lg border border-slate-800 p-3">
              <div className="text-xs uppercase tracking-wide text-slate-500">{state.replaceAll("_", " ")}</div>
              <div className="mt-2 text-2xl font-semibold tabular-nums text-slate-100">{integer.format(count)}</div>
            </div>
          ))}
        </div>
      </section>
    </main>
  );
}
