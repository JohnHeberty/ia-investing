"use client";

import { Suspense } from "react";
import { Newspaper, TrendingUp, TrendingDown } from "lucide-react";
import Link from "next/link";
import type { Route } from "next";
import { useNews } from "@/hooks/use-news";
import { AsOfIndicator, Badge, Metric } from "@/components/domain";
import { DataStatePanel, LoadingSkeleton } from "@/components/data-state-components";

function NewsContent() {
  const {
    items,
    events,
    totalItems,
    totalEvents,
    processedCount,
    unprocessedCount,
    positiveEvents,
    negativeEvents,
    isLoading,
    isError,
    error,
  } = useNews();

  if (isLoading) {
    return <LoadingSkeleton lines={8} />;
  }

  if (isError) {
    return <DataStatePanel state="error" title="Erro ao carregar noticias" detail={String(error ?? "Erro desconhecido")} />;
  }

  const directionTone = (hint: string | null) => {
    if (hint === "positive") return "good";
    if (hint === "negative") return "bad";
    return "neutral";
  };

  return (
    <div className="section-gap">
      <header className="page-head">
        <div className="eyebrow">
          <Newspaper size={14} /> Fontes &amp; Impacto
          <Link href={"/news/sources" as Route} style={{ marginLeft: 16, color: "var(--accent)", fontSize: 13 }}>
            Gerenciar fontes
          </Link>
        </div>
        <h1>Noticias</h1>
        <p className="subtitle">
          Coleta automatica de RSS, classificacao de impacto e monitoramento de tese.
          <AsOfIndicator />
        </p>
      </header>

      <div className="grid grid-4">
        <Metric label="Itens coletados" value={String(totalItems)} note="noticias persistidas" />
        <Metric label="Eventos detectados" value={String(totalEvents)} note="classificados por LLM" />
        <Metric label="Processados" value={String(processedCount)} note={`${unprocessedCount} pendentes`} />
        <Metric
          label="Sentimento"
          value={`${positiveEvents} / ${negativeEvents}`}
          note="positivos / negativos"
        />
      </div>

      <div className="card card-pad">
        <h2 style={{ margin: "0 0 16px" }}>Itens Recentes</h2>
        {items.length === 0 ? (
          <p className="subtitle">Nenhum item coletado ainda. Use POST /api/v1/news/fetch/:issuer_id para iniciar.</p>
        ) : (
          <div style={{ overflowX: "auto" }}>
            <table className="table">
              <thead>
                <tr>
                  <th>Titulo</th>
                  <th>Fonte</th>
                  <th>Publicado</th>
                  <th>Sentimento</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {items.slice(0, 50).map((item) => (
                  <tr key={item.id}>
                    <td>
                      {item.url ? (
                        <a href={item.url} target="_blank" rel="noopener noreferrer" style={{ color: "var(--accent)" }}>
                          {item.title ?? "—"}
                        </a>
                      ) : (
                        item.title ?? "—"
                      )}
                    </td>
                    <td>{item.source_id.slice(0, 8)}...</td>
                    <td>
                      {item.published_at
                        ? new Date(item.published_at).toLocaleDateString("pt-BR", { day: "2-digit", month: "short" })
                        : "—"}
                    </td>
                    <td>
                      {item.sentiment_score !== null ? (
                        <Badge tone={item.sentiment_score > 0.1 ? "good" : item.sentiment_score < -0.1 ? "bad" : "neutral"}>
                          {item.sentiment_score.toFixed(2)}
                        </Badge>
                      ) : (
                        "—"
                      )}
                    </td>
                    <td>
                      <Badge tone={item.is_processed ? "good" : "warn"}>
                        {item.is_processed ? "Processado" : "Pendente"}
                      </Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="card card-pad">
        <h2 style={{ margin: "0 0 16px" }}>Eventos Detectados</h2>
        {events.length === 0 ? (
          <p className="subtitle">Nenhum evento detectado ainda.</p>
        ) : (
          <div style={{ overflowX: "auto" }}>
            <table className="table">
              <thead>
                <tr>
                  <th>Tipo</th>
                  <th>Direcao</th>
                  <th>Materialidade</th>
                  <th>Horizonte</th>
                  <th>Descricao</th>
                </tr>
              </thead>
              <tbody>
                {events.slice(0, 50).map((event) => (
                  <tr key={event.id}>
                    <td>
                      <Link href={`/news/events/${event.id}` as Route} style={{ color: "var(--accent)", textDecoration: "none" }}>
                        <Badge tone="neutral">{event.event_type ?? "—"}</Badge>
                      </Link>
                    </td>
                    <td>
                      <Badge tone={directionTone(event.direction_hint)}>
                        {event.direction_hint === "positive" && <TrendingUp size={12} style={{ marginRight: 4 }} />}
                        {event.direction_hint === "negative" && <TrendingDown size={12} style={{ marginRight: 4 }} />}
                        {event.direction_hint ?? "—"}
                      </Badge>
                    </td>
                    <td style={{ fontFamily: "var(--font-mono)" }}>
                      {event.materiality_score !== null ? event.materiality_score.toFixed(2) : "—"}
                    </td>
                    <td>
                      <Badge tone="neutral">{event.time_horizon ?? "—"}</Badge>
                    </td>
                    <td style={{ maxWidth: 320, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {event.description ?? "—"}
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

export default function NewsPage() {
  return (
    <Suspense fallback={<LoadingSkeleton lines={8} />}>
      <NewsContent />
    </Suspense>
  );
}
