"use client";

import { Suspense } from "react";
import { Newspaper } from "lucide-react";
import {
  NewsDataContext,
  useNewsData,
  useNewsValue,
} from "@/hooks/use-news";
import { AsOfIndicator, DomainTabs, Metric } from "@/components/domain";
import { DataStatePanel, LoadingSkeleton } from "@/components/data-state-components";
import { directionTone } from "@/lib/news-helpers";
import { SourcesTable } from "@/components/news/SourcesTable";
import Link from "next/link";
import type { Route } from "next";
import { TrendingUp, TrendingDown } from "lucide-react";
import { Badge } from "@/components/domain";

function FeedTab() {
  const { items, totalItems, totalEvents, processedCount, unprocessedCount, positiveEvents, negativeEvents } =
    useNewsData();

  return (
    <>
      <section className="grid grid-4 section-gap" aria-label="Metricas do feed" aria-live="polite">
        <Metric label="Itens coletados" value={String(totalItems)} note="noticias persistidas" />
        <Metric label="Eventos detectados" value={String(totalEvents)} note="classificados por LLM" />
        <Metric label="Processados" value={String(processedCount)} note={`${unprocessedCount} pendentes`} />
        <Metric
          label="Sentimento"
          value={`${positiveEvents} / ${negativeEvents}`}
          note="positivos / negativos"
        />
      </section>

      <div className="card card-pad section-gap" aria-live="polite">
        <h2 className="mb-16">Itens Recentes</h2>
        {items.length === 0 ? (
          <div className="subtitle">Nenhum item coletado ainda.</div>
        ) : (
          <div className="overflow-x-auto">
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
                      {item.url && /^https?:\/\//.test(item.url) ? (
                        <a href={item.url} target="_blank" rel="noopener noreferrer" className="text-accent">
                          {item.title ?? "—"}
                        </a>
                      ) : (
                        item.title ?? "—"
                      )}
                    </td>
                    <td>{item.source_name ?? "—"}</td>
                    <td>
                      {item.published_at
                        ? new Date(item.published_at).toLocaleDateString("pt-BR", { day: "2-digit", month: "short" })
                        : "—"}
                    </td>
                    <td>
                      {item.sentiment_score !== null && Number.isFinite(item.sentiment_score) ? (
                        <Badge tone={item.sentiment_score > 0.1 ? "good" : item.sentiment_score < -0.1 ? "bad" : "neutral"}>
                          {item.sentiment_score.toFixed(2)}
                        </Badge>
                      ) : (
                        "—"
                      )}
                    </td>
                    <td>
                      <Badge tone={item.is_processed === true ? "good" : item.is_processed === false ? "warn" : "neutral"}>
                        {item.is_processed === true ? "Processado" : item.is_processed === false ? "Pendente" : "Desconhecido"}
                      </Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </>
  );
}

function EventsTab() {
  const { events, totalEvents, positiveEvents, negativeEvents } = useNewsData();

  return (
    <>
      <section className="grid grid-4 section-gap" aria-label="Metricas de eventos" aria-live="polite">
        <Metric label="Total" value={String(totalEvents)} note="eventos detectados" />
        <Metric label="Positivos" value={String(positiveEvents)} note="direction_hint=positive" />
        <Metric label="Negativos" value={String(negativeEvents)} note="direction_hint=negative" />
        <Metric
          label="Neutros"
          value={String(totalEvents - positiveEvents - negativeEvents)}
          note="demais classificacoes"
        />
      </section>

      <div className="card card-pad section-gap" aria-live="polite">
        <h2 className="mb-16">Todos os Eventos</h2>
        {events.length === 0 ? (
          <div className="subtitle">Nenhum evento detectado ainda.</div>
        ) : (
          <div className="overflow-x-auto">
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
                {events.map((event) => (
                  <tr key={event.id}>
                    <td>
                      <Link href={`/news/events/${event.id}` as Route} className="text-accent">
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
                    <td className="mono">
                      {event.materiality_score !== null && Number.isFinite(event.materiality_score) ? event.materiality_score.toFixed(2) : "—"}
                    </td>
                    <td>
                      <Badge tone="neutral">{event.time_horizon ?? "—"}</Badge>
                    </td>
                    <td className="max-w-320 truncate">
                      {event.description ?? "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </>
  );
}

function SourcesTab() {
  const { sources, stats } = useNewsData();
  return <SourcesTable sources={sources} stats={stats} />;
}

function NewsContent() {
  const newsValue = useNewsData();

  if (newsValue.isLoading) {
    return <LoadingSkeleton lines={8} />;
  }

  if (newsValue.isError) {
    return <DataStatePanel state="error" title="Erro ao carregar noticias" detail={newsValue.error instanceof Error ? newsValue.error.message : String(newsValue.error ?? "Erro desconhecido")} />;
  }

  return (
    <div className="section-gap">
      <header className="page-head">
        <div className="eyebrow"><Newspaper size={14} /> Fontes &amp; Impacto</div>
        <h1>Noticias</h1>
        <div className="subtitle">
          Coleta automatica de RSS, classificacao de impacto e monitoramento de tese.
          <AsOfIndicator />
        </div>
      </header>

      <DomainTabs
        label="Noticias"
        tabs={[
          { id: "feed", label: "Feed", content: <FeedTab /> },
          { id: "fontes", label: "Fontes", content: <SourcesTab /> },
          { id: "eventos", label: "Eventos", content: <EventsTab /> },
        ]}
      />
    </div>
  );
}

export default function NewsPage() {
  return (
    <Suspense fallback={<LoadingSkeleton lines={8} />}>
      <NewsDataProvider />
    </Suspense>
  );
}

function NewsDataProvider() {
  const value = useNewsValue();
  return (
    <NewsDataContext.Provider value={value}>
      <NewsContent />
    </NewsDataContext.Provider>
  );
}
