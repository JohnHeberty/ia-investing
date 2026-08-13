"use client";

import { Suspense } from "react";
import { TrendingUp, TrendingDown, Minus, ArrowLeft } from "lucide-react";
import Link from "next/link";
import type { Route } from "next";
import { NewsDataContext, useNewsValue, useNewsPortfolioImpacts } from "@/hooks/use-news";
import { directionTone } from "@/lib/news-helpers";
import { AsOfIndicator, Badge, Metric } from "@/components/domain";
import { LoadingSkeleton } from "@/components/data-state-components";

function ImpactContent() {
  const { events, totalEvents, positiveEvents, negativeEvents } = useNewsValue();
  const { data: portfolioImpacts, isLoading: impactsLoading } = useNewsPortfolioImpacts();

  const impacts = portfolioImpacts ?? [];
  const affectedPortfolios = new Set(impacts.map((i) => i.portfolio_id)).size;

  const sortedEvents = [...events].sort((a, b) => {
    const aScore = Math.abs(a.materiality_score ?? 0);
    const bScore = Math.abs(b.materiality_score ?? 0);
    return bScore - aScore;
  });

  const directionIcon = (hint: string | null) => {
    if (hint === "positive") return <TrendingUp size={12} />;
    if (hint === "negative") return <TrendingDown size={12} />;
    return <Minus size={12} />;
  };

  return (
    <div className="section-gap">
      <header className="page-head">
        <div className="eyebrow">
          <Link href={"/news" as Route} className="text-accent">
            <ArrowLeft size={14} /> Noticias
          </Link>
          {" / Impacto"}
        </div>
        <h1>Impacto de Noticias</h1>
        <div className="subtitle">
          Eventos recentes e cruzamento com posicoes dos portfolios.
          <AsOfIndicator />
        </div>
      </header>

      <section
        className="grid grid-4 section-gap"
        aria-label="Metricas de impacto"
        aria-live="polite"
      >
        <Metric label="Eventos" value={String(totalEvents)} note="detectados por LLM" />
        <Metric label="Positivos" value={String(positiveEvents)} note="direction_hint=positive" />
        <Metric label="Negativos" value={String(negativeEvents)} note="direction_hint=negative" />
        <Metric
          label="Portfolios afetados"
          value={String(affectedPortfolios)}
          note={`${impacts.length} intersecoes`}
        />
      </section>

      <div className="card card-pad section-gap">
        <h2 className="mb-16">Timeline de Eventos Recentes</h2>
        {sortedEvents.length === 0 ? (
          <div className="subtitle">Nenhum evento detectado ainda.</div>
        ) : (
          <div className="flex flex-col gap-8">
            {sortedEvents.slice(0, 20).map((event) => {
              const eventImpacts = impacts.filter((i) => i.event_id === event.id);
              return (
                <div key={event.id} className="timeline-event">
                  <div className="flex-shrink-0" style={{ marginTop: 2 }}>
                    {directionIcon(event.direction_hint)}
                  </div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div className="flex items-center gap-8 mb-4">
                      <Link
                        href={`/news/events/${event.id}` as Route}
                        className="text-accent fw-500"
                      >
                        {event.event_type ?? "evento"}
                      </Link>
                      <Badge tone={directionTone(event.direction_hint)}>
                        {event.direction_hint ?? "—"}
                      </Badge>
                      {event.materiality_score !== null &&
                        Math.abs(event.materiality_score) >= 0.7 && (
                          <Badge tone="bad">ALERTA</Badge>
                        )}
                      <span className="mono text-sm muted">
                        {event.materiality_score !== null
                          ? event.materiality_score.toFixed(2)
                          : "—"}
                      </span>
                    </div>
                    <div className="truncate muted" style={{ fontSize: 13 }}>
                      {event.description ?? "—"}
                    </div>
                    {eventImpacts.length > 0 && (
                      <div className="mt-6 flex flex-wrap gap-4">
                        {eventImpacts.map((imp) => (
                          <Badge key={imp.event_id + imp.portfolio_id} tone="neutral">
                            {imp.portfolio_name}
                          </Badge>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      <div className="card card-pad section-gap" aria-live="polite">
        <h2 className="mb-16">Impacto por Ativo nos Portfolios</h2>
        {impactsLoading ? (
          <LoadingSkeleton lines={4} />
        ) : impacts.length === 0 ? (
          <div className="subtitle">Nenhum cruzamento evento-portfolio nos ultimos 7 dias.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="table">
              <thead>
                <tr>
                  <th>Evento</th>
                  <th>Direcao</th>
                  <th>Materialidade</th>
                  <th>Portfolio</th>
                  <th>Ativo</th>
                  <th>Data</th>
                </tr>
              </thead>
              <tbody>
                {impacts.map((impact, idx) => (
                  <tr key={`${impact.event_id}-${impact.portfolio_id}-${idx}`}>
                    <td>
                      <Link
                        href={`/news/events/${impact.event_id}` as Route}
                        className="text-accent"
                      >
                        <Badge tone="neutral">{impact.event_type ?? "—"}</Badge>
                      </Link>
                    </td>
                    <td>
                      <Badge tone={directionTone(impact.direction_hint)}>
                        {impact.direction_hint === "positive" && (
                          <TrendingUp size={12} style={{ marginRight: 4 }} />
                        )}
                        {impact.direction_hint === "negative" && (
                          <TrendingDown size={12} style={{ marginRight: 4 }} />
                        )}
                        {impact.direction_hint ?? "—"}
                      </Badge>
                    </td>
                    <td className="mono">
                      {impact.materiality_score !== null
                        ? impact.materiality_score.toFixed(2)
                        : "—"}
                    </td>
                    <td>{impact.portfolio_name}</td>
                    <td>
                      <Badge tone="neutral">{impact.issuer_id.slice(0, 8)}</Badge>
                    </td>
                    <td>
                      {impact.event_created_at
                        ? new Date(impact.event_created_at).toLocaleDateString("pt-BR", {
                            day: "2-digit",
                            month: "short",
                          })
                        : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

export default function NewsImpactPage() {
  return (
    <Suspense fallback={<LoadingSkeleton lines={12} />}>
      <NewsDataProvider />
    </Suspense>
  );
}

function NewsDataProvider() {
  const value = useNewsValue();
  return (
    <NewsDataContext.Provider value={value}>
      <ImpactContent />
    </NewsDataContext.Provider>
  );
}
