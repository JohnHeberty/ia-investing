"use client";

import { Suspense } from "react";
import { Newspaper, Plus, Check, X } from "lucide-react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { bffFetch, queryKeys } from "@/lib/api-client";
import { AsOfIndicator, Badge, Metric } from "@/components/domain";
import { DataStatePanel, LoadingSkeleton } from "@/components/data-state-components";

interface NewsSource {
  id: string;
  name: string;
  url_pattern: string | null;
  trust_level: number | null;
  source_type: string | null;
  is_active: boolean | null;
  created_at: string | null;
}

interface NewsStats {
  total_items: number;
  processed_items: number;
  unprocessed_items: number;
  total_events: number;
  positive_events: number;
  negative_events: number;
  neutral_events: number;
  total_impacts: number;
  active_sources: number;
}

function SourcesContent() {
  const queryClient = useQueryClient();

  const sourcesQuery = useQuery({
    queryKey: queryKeys.newsSources(),
    queryFn: () => bffFetch<NewsSource[]>("/api/v1/news/sources"),
    staleTime: 60_000,
  });

  const statsQuery = useQuery({
    queryKey: queryKeys.newsStats(),
    queryFn: () => bffFetch<NewsStats>("/api/v1/news/stats"),
    staleTime: 30_000,
  });

  const createMutation = useMutation({
    mutationFn: (data: { name: string; source_type: string; trust_level: number }) =>
      bffFetch<NewsSource>("/api/v1/news/sources", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.newsSources() });
      queryClient.invalidateQueries({ queryKey: queryKeys.newsStats() });
    },
  });

  if (sourcesQuery.isError || statsQuery.isError) {
    return <DataStatePanel state="error" title="Erro ao carregar fontes" detail="Falha ao buscar dados." />;
  }

  if (sourcesQuery.isLoading || statsQuery.isLoading) {
    return <LoadingSkeleton lines={8} />;
  }

  const sources = sourcesQuery.data ?? [];
  const stats = statsQuery.data;

  const trustBadge = (level: number | null) => {
    if (level === null) return <Badge tone="neutral">—</Badge>;
    if (level <= 2) return <Badge tone="good">Alta ({level})</Badge>;
    if (level <= 3) return <Badge tone="neutral">Media ({level})</Badge>;
    return <Badge tone="warn">Baixa ({level})</Badge>;
  };

  const handleQuickAdd = (name: string, source_type: string) => {
    createMutation.mutate({ name, source_type, trust_level: 3 });
  };

  return (
    <div className="section-gap">
      <header className="page-head">
        <div className="eyebrow"><Newspaper size={14} /> Cadastro</div>
        <h1>Fontes RSS</h1>
        <div className="subtitle">
          Gerencie as fontes de noticias e visualize metricas de coleta.
          <AsOfIndicator />
        </div>
      </header>

      {stats && (
        <div className="grid grid-4">
          <Metric label="Fontes ativas" value={String(stats.active_sources)} note="RSS configuradas" />
          <Metric label="Itens coletados" value={String(stats.total_items)} note={`${stats.unprocessed_items} pendentes`} />
          <Metric label="Eventos" value={String(stats.total_events)} note={`${stats.positive_events} pos / ${stats.negative_events} neg`} />
          <Metric label="Impactos" value={String(stats.total_impacts)} note="em teses ativas" />
        </div>
      )}

      <div className="card card-pad">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
          <h2 style={{ margin: 0 }}>Fontes Cadastradas</h2>
          <div style={{ display: "flex", gap: 8 }}>
            <button
              className="button"
              onClick={() => handleQuickAdd("Google News - Brasil", "rss_google")}
              disabled={createMutation.isPending}
              type="button"
            >
              <Plus size={14} /> Google News
            </button>
            <button
              className="button"
              onClick={() => handleQuickAdd("Reuters - Brasil", "rss_reuters")}
              disabled={createMutation.isPending}
              type="button"
            >
              <Plus size={14} /> Reuters
            </button>
          </div>
        </div>

        {sources.length === 0 ? (
          <p className="subtitle">Nenhuma fonte cadastrada. Use os botoes acima para adicionar.</p>
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

export default function NewsSourcesPage() {
  return (
    <Suspense fallback={<LoadingSkeleton lines={8} />}>
      <SourcesContent />
    </Suspense>
  );
}
