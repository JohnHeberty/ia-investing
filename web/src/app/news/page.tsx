"use client";

import { Suspense, useState } from "react";
import { Newspaper, TrendingUp, TrendingDown, Plus, Check, X, Pencil, Trash2 } from "lucide-react";
import Link from "next/link";
import type { Route } from "next";
import {
  NewsDataContext,
  useNewsData,
  useNewsValue,
  useSourceMutations,
} from "@/hooks/use-news";
import type { NewsDataValue, NewsSource } from "@/hooks/use-news";
import { directionTone } from "@/lib/news-helpers";
import { AsOfIndicator, Badge, DomainTabs, Metric } from "@/components/domain";
import { DataStatePanel, LoadingSkeleton } from "@/components/data-state-components";
import { SourceFormModal } from "@/components/source-form-modal";

function FeedTab() {
  const { items, totalItems, totalEvents, processedCount, unprocessedCount, positiveEvents, negativeEvents } =
    useNewsData();

  return (
    <>
      <section className="grid grid-4 section-gap" aria-label="Metricas do feed">
        <Metric label="Itens coletados" value={String(totalItems)} note="noticias persistidas" />
        <Metric label="Eventos detectados" value={String(totalEvents)} note="classificados por LLM" />
        <Metric label="Processados" value={String(processedCount)} note={`${unprocessedCount} pendentes`} />
        <Metric
          label="Sentimento"
          value={`${positiveEvents} / ${negativeEvents}`}
          note="positivos / negativos"
        />
      </section>

      <div className="card card-pad section-gap">
        <h2 style={{ margin: "0 0 16px" }}>Itens Recentes</h2>
        {items.length === 0 ? (
          <div className="subtitle">Nenhum item coletado ainda.</div>
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
                      {item.url && /^https?:\/\//.test(item.url) ? (
                        <a href={item.url} target="_blank" rel="noopener noreferrer" style={{ color: "var(--accent)" }}>
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
      <section className="grid grid-4 section-gap" aria-label="Metricas de eventos">
        <Metric label="Total" value={String(totalEvents)} note="eventos detectados" />
        <Metric label="Positivos" value={String(positiveEvents)} note="direction_hint=positive" />
        <Metric label="Negativos" value={String(negativeEvents)} note="direction_hint=negative" />
        <Metric
          label="Neutros"
          value={String(totalEvents - positiveEvents - negativeEvents)}
          note="demais classificacoes"
        />
      </section>

      <div className="card card-pad section-gap">
        <h2 style={{ margin: "0 0 16px" }}>Todos os Eventos</h2>
        {events.length === 0 ? (
          <div className="subtitle">Nenhum evento detectado ainda.</div>
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
                {events.map((event) => (
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
                      {event.materiality_score !== null && Number.isFinite(event.materiality_score) ? event.materiality_score.toFixed(2) : "—"}
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
    </>
  );
}

function SourcesTab() {
  const { sources, stats } = useNewsData();
  const { createMutation, updateMutation, deleteMutation } = useSourceMutations();

  const [modalOpen, setModalOpen] = useState(false);
  const [editingSource, setEditingSource] = useState<NewsSource | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const handleCreate = () => {
    setEditingSource(null);
    setModalOpen(true);
  };

  const handleEdit = (source: NewsSource) => {
    setEditingSource(source);
    setModalOpen(true);
  };

  const handleDelete = async (id: string, name: string) => {
    if (!confirm(`Excluir a fonte "${name}"?`)) return;
    setDeletingId(id);
    try {
      await deleteMutation.mutateAsync(id);
    } finally {
      setDeletingId(null);
    }
  };

  const handleSubmit = (data: { name: string; source_type?: string; url_pattern?: string; trust_level?: number }) => {
    if (editingSource) {
      updateMutation.mutate({ id: editingSource.id, ...data }, { onSuccess: () => setModalOpen(false) });
    } else {
      createMutation.mutate(data, { onSuccess: () => setModalOpen(false) });
    }
  };

  const activeMutation = editingSource ? updateMutation : createMutation;

  const trustBadge = (level: number | null) => {
    if (level === null) return <Badge tone="neutral">—</Badge>;
    if (level <= 2) return <Badge tone="good">Alta ({level})</Badge>;
    if (level <= 3) return <Badge tone="neutral">Media ({level})</Badge>;
    return <Badge tone="warn">Baixa ({level})</Badge>;
  };

  return (
    <>
      {stats && (
        <section className="grid grid-4 section-gap" aria-label="Metricas de fontes">
          <Metric label="Fontes ativas" value={String(stats.active_sources)} note="RSS configuradas" />
          <Metric label="Itens coletados" value={String(stats.total_items)} note={`${stats.unprocessed_items} pendentes`} />
          <Metric label="Eventos" value={String(stats.total_events)} note={`${stats.positive_events} pos / ${stats.negative_events} neg`} />
          <Metric label="Impactos" value={String(stats.total_impacts)} note="em teses ativas" />
        </section>
      )}

      <div className="card card-pad section-gap">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
          <h2 style={{ margin: 0 }}>Fontes Cadastradas</h2>
          <button className="button" onClick={handleCreate} type="button">
            <Plus size={14} /> Nova Fonte
          </button>
        </div>

        {sources.length === 0 ? (
          <div className="subtitle">Nenhuma fonte cadastrada. Clique em &quot;Nova Fonte&quot; para adicionar.</div>
        ) : (
          <div style={{ overflowX: "auto" }}>
            <table className="table">
              <thead>
                <tr>
                  <th>Nome</th>
                  <th>Tipo</th>
                  <th>Confianca</th>
                  <th>Status</th>
                  <th>Criado em</th>
                  <th style={{ width: 80 }}></th>
                </tr>
              </thead>
              <tbody>
                {sources.map((source) => (
                  <tr key={source.id}>
                    <td style={{ fontWeight: 500 }}>{source.name}</td>
                    <td><Badge tone="neutral">{source.source_type ?? "—"}</Badge></td>
                    <td>{trustBadge(source.trust_level)}</td>
                    <td>
                      <Badge tone={source.is_active === true ? "good" : source.is_active === false ? "bad" : "neutral"}>
                        {source.is_active === true ? <><Check size={12} /> Ativo</> : source.is_active === false ? <><X size={12} /> Inativo</> : "Desconhecido"}
                      </Badge>
                    </td>
                    <td>
                      {source.created_at
                        ? new Date(source.created_at).toLocaleDateString("pt-BR")
                        : "—"}
                    </td>
                    <td>
                      <div style={{ display: "flex", gap: 4, justifyContent: "flex-end" }}>
                        <button
                          className="button"
                          onClick={() => handleEdit(source)}
                          disabled={deleteMutation.isPending}
                          type="button"
                          title="Editar"
                          style={{ padding: "4px 8px" }}
                        >
                          <Pencil size={12} />
                        </button>
                        <button
                          className="button"
                          onClick={() => handleDelete(source.id, source.name)}
                          disabled={deletingId === source.id}
                          type="button"
                          title="Excluir"
                          style={{ padding: "4px 8px", color: "var(--red)" }}
                        >
                          <Trash2 size={12} />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <SourceFormModal
        open={modalOpen}
        onOpenChange={setModalOpen}
        source={editingSource}
        onSubmit={handleSubmit}
        isPending={activeMutation.isPending}
        error={activeMutation.error instanceof Error ? activeMutation.error : null}
      />
    </>
  );
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
