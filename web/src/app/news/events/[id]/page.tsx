"use client";

import { use } from "react";
import { Suspense } from "react";
import { Newspaper, TrendingUp, TrendingDown, ArrowLeft } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import type { Route } from "next";
import { bffFetch } from "@/lib/api-client";
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
  const { data: event, isLoading, isError, error } = useQuery({
    queryKey: ["newsEvent", eventId],
    queryFn: () => bffFetch<EventDetail>(`/api/v1/news/events/${eventId}`),
    staleTime: 30_000,
  });

  if (isLoading) return <LoadingSkeleton lines={12} />;
  if (isError) return <DataStatePanel state="error" title="Erro ao carregar evento" detail={String(error)} />;
  if (!event) return <DataStatePanel state="missing" title="Evento nao encontrado" detail="ID invalido." />;

  const directionTone = (hint: string | null) => {
    if (hint === "positive") return "good";
    if (hint === "negative") return "bad";
    return "neutral";
  };

  const effectTone = (effect: string | null) => {
    if (effect === "strengthen") return "good";
    if (effect === "weaken") return "bad";
    return "neutral";
  };

  return (
    <div className="section-gap">
      <header className="page-head">
        <div className="eyebrow">
          <Link href={"/news" as Route} style={{ color: "var(--accent)", textDecoration: "none" }}>
            <ArrowLeft size={14} /> Noticias
          </Link>
          {" / Evento"}
        </div>
        <h1>Detalhe do Evento</h1>
        <p className="subtitle">
          Evento detectado via analise de noticias.
          <AsOfIndicator />
        </p>
      </header>

      <div className="grid grid-4">
        <article className="card metric">
          <div className="metric-label">Tipo</div>
          <div className="metric-value"><Badge tone="neutral">{event.event_type ?? "—"}</Badge></div>
        </article>
        <article className="card metric">
          <div className="metric-label">Direcao</div>
          <div className="metric-value">
            <Badge tone={directionTone(event.direction_hint)}>
              {event.direction_hint === "positive" && <TrendingUp size={14} style={{ marginRight: 4 }} />}
              {event.direction_hint === "negative" && <TrendingDown size={14} style={{ marginRight: 4 }} />}
              {event.direction_hint ?? "—"}
            </Badge>
          </div>
        </article>
        <article className="card metric">
          <div className="metric-label">Materialidade</div>
          <div className="metric-value" style={{ fontFamily: "var(--font-mono)" }}>
            {event.materiality_score !== null ? event.materiality_score.toFixed(2) : "—"}
          </div>
        </article>
        <article className="card metric">
          <div className="metric-label">Horizonte</div>
          <div className="metric-value"><Badge tone="neutral">{event.time_horizon ?? "—"}</Badge></div>
        </article>
      </div>

      <div className="card card-pad">
        <h2 style={{ margin: "0 0 12px" }}>Descricao</h2>
        <p style={{ color: "var(--text)", lineHeight: 1.6 }}>{event.description ?? "Sem descricao disponivel."}</p>
      </div>

      {event.affected_metrics && (
        <div className="card card-pad">
          <h2 style={{ margin: "0 0 12px" }}>Metricas Afetadas</h2>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
            {Array.isArray(event.affected_metrics.metrics)
              ? (event.affected_metrics.metrics as string[]).map((m, i) => (
                  <Badge key={i} tone="neutral">{m}</Badge>
                ))
              : <span className="subtitle">Nenhuma metrica identificada</span>
            }
          </div>
          {Array.isArray(event.affected_metrics.key_claims) && event.affected_metrics.key_claims.length > 0 && (
            <div style={{ marginTop: 16 }}>
              <h3 style={{ margin: "0 0 8px", fontSize: 14 }}>Claims chave</h3>
              <ul style={{ margin: 0, paddingLeft: 20 }}>
                {(event.affected_metrics.key_claims as string[]).map((claim, i) => (
                  <li key={i} style={{ color: "var(--muted)", fontSize: 13, marginBottom: 4 }}>{claim}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      <div className="card card-pad">
        <h2 style={{ margin: "0 0 16px" }}>Impactos em Teses ({event.impacts.length})</h2>
        {event.impacts.length === 0 ? (
          <p className="subtitle">Nenhum impacto registrado para este evento.</p>
        ) : (
          <div style={{ overflowX: "auto" }}>
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
                    <td style={{ fontFamily: "var(--font-mono)", fontSize: 12 }}>
                      {impact.thesis_id ? impact.thesis_id.slice(0, 8) + "..." : "—"}
                    </td>
                    <td>
                      <Badge tone={effectTone(impact.thesis_effect)}>
                        {impact.thesis_effect ?? "—"}
                      </Badge>
                    </td>
                    <td style={{ fontFamily: "var(--font-mono)" }}>
                      {impact.impact_score !== null ? impact.impact_score.toFixed(2) : "—"}
                    </td>
                    <td style={{ fontFamily: "var(--font-mono)" }}>
                      {impact.confidence !== null ? `${(impact.confidence * 100).toFixed(0)}%` : "—"}
                    </td>
                    <td style={{ maxWidth: 320, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", color: "var(--muted)", fontSize: 13 }}>
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
