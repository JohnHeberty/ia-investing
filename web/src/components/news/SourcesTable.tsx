"use client";

import { useState } from "react";
import { Plus, Check, X, Pencil, Trash2 } from "lucide-react";
import { useSourceMutations } from "@/hooks/use-news";
import type { NewsSource } from "@/hooks/use-news";
import { Badge, Metric } from "@/components/domain";
import { SourceFormModal } from "@/components/source-form-modal";

type SourceStats = {
  active_sources: number;
  total_items: number;
  unprocessed_items: number;
  total_events: number;
  positive_events: number;
  negative_events: number;
  total_impacts: number;
};

function trustBadge(level: number | null) {
  if (level === null) return <Badge tone="neutral">—</Badge>;
  if (level <= 2) return <Badge tone="good">Alta ({level})</Badge>;
  if (level <= 3) return <Badge tone="neutral">Media ({level})</Badge>;
  return <Badge tone="warn">Baixa ({level})</Badge>;
}

export function SourcesTable({ sources, stats }: { sources: NewsSource[]; stats: SourceStats | null | undefined }) {
  const { createMutation, updateMutation, deleteMutation } = useSourceMutations();
  const [modalOpen, setModalOpen] = useState(false);
  const [editingSource, setEditingSource] = useState<NewsSource | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const handleCreate = () => { setEditingSource(null); setModalOpen(true); };
  const handleEdit = (source: NewsSource) => { setEditingSource(source); setModalOpen(true); };

  const handleDelete = async (id: string, name: string) => {
    if (!confirm(`Excluir a fonte "${name}"?`)) return;
    setDeletingId(id);
    try { await deleteMutation.mutateAsync(id); } finally { setDeletingId(null); }
  };

  const handleSubmit = (data: { name: string; source_type?: string; url_pattern?: string; trust_level?: number }) => {
    if (editingSource) {
      updateMutation.mutate({ id: editingSource.id, ...data }, { onSuccess: () => setModalOpen(false) });
    } else {
      createMutation.mutate(data, { onSuccess: () => setModalOpen(false) });
    }
  };

  const activeMutation = editingSource ? updateMutation : createMutation;

  return (
    <>
      {stats && (
        <section className="grid grid-4 section-gap" aria-label="Metricas de fontes" aria-live="polite">
          <Metric label="Fontes ativas" value={String(stats.active_sources)} note="RSS configuradas" />
          <Metric label="Itens coletados" value={String(stats.total_items)} note={`${stats.unprocessed_items} pendentes`} />
          <Metric label="Eventos" value={String(stats.total_events)} note={`${stats.positive_events} pos / ${stats.negative_events} neg`} />
          <Metric label="Impactos" value={String(stats.total_impacts)} note="em teses ativas" />
        </section>
      )}

      <div className="card card-pad section-gap" aria-live="polite">
        <div className="flex justify-between items-center mb-16">
          <h2>Fontes Cadastradas</h2>
          <button className="button" onClick={handleCreate} type="button">
            <Plus size={14} /> Nova Fonte
          </button>
        </div>

        {sources.length === 0 ? (
          <div className="subtitle">Nenhuma fonte cadastrada. Clique em &quot;Nova Fonte&quot; para adicionar.</div>
        ) : (
          <div className="overflow-x-auto">
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
                    <td className="fw-500">{source.name}</td>
                    <td><Badge tone="neutral">{source.source_type ?? "—"}</Badge></td>
                    <td>{trustBadge(source.trust_level)}</td>
                    <td>
                      <Badge tone={source.is_active === true ? "good" : source.is_active === false ? "bad" : "neutral"}>
                        {source.is_active === true ? <><Check size={12} /> Ativo</> : source.is_active === false ? <><X size={12} /> Inativo</> : "Desconhecido"}
                      </Badge>
                    </td>
                    <td>{source.created_at ? new Date(source.created_at).toLocaleDateString("pt-BR") : "—"}</td>
                    <td>
                      <div className="flex gap-4 justify-end">
                        <button className="button" onClick={() => handleEdit(source)} disabled={deleteMutation.isPending} type="button" title="Editar" style={{ padding: "4px 8px" }}>
                          <Pencil size={12} />
                        </button>
                        <button className="button" onClick={() => handleDelete(source.id, source.name)} disabled={deletingId === source.id} type="button" title="Excluir" style={{ padding: "4px 8px", color: "var(--red)" }}>
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
