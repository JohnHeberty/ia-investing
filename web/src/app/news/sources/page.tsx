"use client";

import { Suspense, useState } from "react";
import { Rss, Plus, Check, X, Pencil, Trash2 } from "lucide-react";
import Link from "next/link";
import type { Route } from "next";
import {
  NewsDataContext,
  useNewsValue,
  useSourceMutations,
} from "@/hooks/use-news";
import type { NewsSource } from "@/hooks/use-news";
import { AsOfIndicator, Badge, Metric } from "@/components/domain";
import { DataStatePanel, LoadingSkeleton } from "@/components/data-state-components";
import { SourceFormModal } from "@/components/source-form-modal";

function SourcesContent() {
  const { sources, stats } = useNewsValue();
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
    <div className="section-gap">
      <header className="page-head">
        <div className="eyebrow">
          <Link href={"/news" as Route} style={{ color: "var(--accent)", textDecoration: "none" }}>
            <Rss size={14} /> Noticias
          </Link>
          {" / Fontes"}
        </div>
        <h1>Fontes de Noticias</h1>
        <div className="subtitle">
          Gerencie fontes RSS e provedores de dados.
          <AsOfIndicator />
        </div>
      </header>

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
    </div>
  );
}

export default function NewsSourcesPage() {
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
      <SourcesContent />
    </NewsDataContext.Provider>
  );
}
