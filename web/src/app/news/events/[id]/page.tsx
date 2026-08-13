"use client";

import { use } from "react";
import { Suspense } from "react";
import { TrendingUp, TrendingDown, ArrowLeft } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import type { Route } from "next";
import { bffFetch, queryKeys } from "@/lib/api-client";
import { directionTone, effectTone } from "@/lib/news-helpers";
import { AsOfIndicator, Badge } from "@/components/domain";
import { DataStatePanel, LoadingSkeleton } from "@/components/data-state-components";

interface EventImpact {
  id: string;
  thesis_id: string | null;
  impact_score: number | null;
  confidence: number | null;
  reasoning: string | null;
  thesis_effect: string | null;
  created_at: string | null;
}

interface EventDetail {
  id: string;
  news_item_id: string | null;
  issuer_id: string | null;
  event_type: string | null;
  description: string | null;
  materiality_score: number | null;
  direction_hint: string | null;
  time_horizon: string | null;
  affected_metrics: Record<string, unknown> | null;
  created_at: string | null;
  impacts: EventImpact[];
}

function EventDetailContent({ eventId }: { eventId: string }) {
  const {
    data: event,
    isLoading,
    isError,
    error,
  } = useQuery({
    queryKey: queryKeys.newsEvent(eventId),
    queryFn: () => bffFetch<EventDetail>(`/api/v1/news/events/${eventId}`),
    staleTime: 30_000,
  });

  if (isLoading) return <LoadingSkeleton lines={12} />;
  if (isError)
    return (
      <DataStatePanel
        state="error"
        title="Erro ao carregar evento"
        detail={error instanceof Error ? error.message : String(error)}
      />
    );
  if (!event)
    return <DataStatePanel state="missing" title="Evento nao encontrado" detail="ID invalido." />;

  return (
    <div className="section-gap">
      <header className="page-head">
        <div className="eyebrow">
          <Link href={"/news" as Route} className="text-accent">
            <ArrowLeft size={14} /> Noticias
          </Link>
          {" / Evento"}
        </div>
        <h1>Detalhe do Evento</h1>
        <div className="subtitle">
          Evento detectado via analise de noticias.
          <AsOfIndicator />
        </div>
      </header>

      <section
        className="grid grid-4 section-gap"
        aria-label="Metricas do evento"
        aria-live="polite"
      >
        <article className="card metric">
          <div className="metric-label">Tipo</div>
          <div className="metric-value">
            <Badge tone="neutral">{event.event_type ?? "—"}</Badge>
          </div>
        </article>
        <article className="card metric">
          <div className="metric-label">Direcao</div>
          <div className="metric-value">
            <Badge tone={directionTone(event.direction_hint)}>
              {event.direction_hint === "positive" && (
                <TrendingUp size={14} style={{ marginRight: 4 }} />
              )}
              {event.direction_hint === "negative" && (
                <TrendingDown size={14} style={{ marginRight: 4 }} />
              )}
              {event.direction_hint ?? "—"}
            </Badge>
          </div>
        </article>
        <article className="card metric">
          <div className="metric-label">Materialidade</div>
          <div className="metric-value mono">
            {event.materiality_score !== null ? event.materiality_score.toFixed(2) : "—"}
          </div>
        </article>
        <article className="card metric">
          <div className="metric-label">Horizonte</div>
          <div className="metric-value">
            <Badge tone="neutral">{event.time_horizon ?? "—"}</Badge>
          </div>
        </article>
      </section>

      <div className="card card-pad section-gap">
        <h2 className="mb-12">Descricao</h2>
        <p className="lh-relaxed">{event.description ?? "Sem descricao disponivel."}</p>
      </div>

      {event.affected_metrics && (
        <div className="card card-pad section-gap">
          <h2 className="mb-12">Metricas Afetadas</h2>
          <div className="flex flex-wrap gap-8">
            {Array.isArray(event.affected_metrics?.metrics) ? (
              (event.affected_metrics.metrics as unknown[]).map((m, i) => (
                <Badge key={i} tone="neutral">
                  {typeof m === "string" ? m : String(m)}
                </Badge>
              ))
            ) : (
              <span className="subtitle">Nenhuma metrica identificada</span>
            )}
          </div>
          {Array.isArray(event.affected_metrics?.key_claims) &&
            event.affected_metrics.key_claims.length > 0 && (
              <div className="mt-16">
                <h3 className="mb-8" style={{ fontSize: 14 }}>
                  Claims chave
                </h3>
                <ul style={{ margin: 0, paddingLeft: 20 }}>
                  {(event.affected_metrics.key_claims as unknown[]).map((claim, i) => (
                    <li key={i} className="muted mb-4" style={{ fontSize: 13 }}>
                      {typeof claim === "string" ? claim : String(claim)}
                    </li>
                  ))}
                </ul>
              </div>
            )}
        </div>
      )}

      <div className="card card-pad section-gap" aria-live="polite">
        <h2 className="mb-16">Impactos em Teses ({event.impacts.length})</h2>
        {event.impacts.length === 0 ? (
          <p className="subtitle">Nenhum impacto registrado para este evento.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="table">
              <thead>
                <tr>
                  <th>Tese</th>
                  <th>Efeito</th>
                  <th>Impacto</th>
                  <th>Confianca</th>
                  <th>Raciocinio</th>
                </tr>
              </thead>
              <tbody>
                {event.impacts.map((impact) => (
                  <tr key={impact.id}>
                    <td className="mono text-sm">
                      {impact.thesis_id ? impact.thesis_id.slice(0, 8) + "..." : "—"}
                    </td>
                    <td>
                      <Badge tone={effectTone(impact.thesis_effect)}>
                        {impact.thesis_effect ?? "—"}
                      </Badge>
                    </td>
                    <td className="mono">
                      {impact.impact_score !== null ? impact.impact_score.toFixed(2) : "—"}
                    </td>
                    <td className="mono">
                      {impact.confidence !== null
                        ? `${(impact.confidence * 100).toFixed(0)}%`
                        : "—"}
                    </td>
                    <td className="max-w-320 truncate muted" style={{ fontSize: 13 }}>
                      {impact.reasoning ?? "—"}
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

export default function EventDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  return (
    <Suspense fallback={<LoadingSkeleton lines={12} />}>
      <EventDetailContent eventId={id} />
    </Suspense>
  );
}
