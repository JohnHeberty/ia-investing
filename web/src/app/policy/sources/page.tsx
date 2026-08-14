"use client";

import { Suspense } from "react";
import { Gavel } from "lucide-react";
import Link from "next/link";
import type { Route } from "next";
import { PolicyDataContext, usePolicyData, usePolicyValue, useSourceMutations } from "@/hooks/use-policy";
import { AsOfIndicator, Badge, Metric } from "@/components/domain";
import { LoadingSkeleton } from "@/components/data-state-components";
import { useState } from "react";

function SourcesContent() {
  const { sources } = usePolicyData();
  const { createMutation, deleteMutation } = useSourceMutations();
  const [newName, setNewName] = useState("");
  const [newType, setNewType] = useState("");
  const [newUrl, setNewUrl] = useState("");

  const activeSources = sources.filter((s) => s.is_active).length;

  const handleCreate = () => {
    if (!newName.trim()) return;
    createMutation.mutate(
      {
        name: newName.trim(),
        ...(newType.trim() ? { source_type: newType.trim() } : {}),
        ...(newUrl.trim() ? { url_pattern: newUrl.trim() } : {}),
      },
      {
        onSuccess: () => {
          setNewName("");
          setNewType("");
          setNewUrl("");
        },
      },
    );
  };

  return (
    <div className="section-gap">
      <header className="page-head">
        <div className="eyebrow">
          <Link href={"/policy" as Route} className="text-accent">
            <Gavel size={14} /> Politica
          </Link>
          {" / Fontes"}
        </div>
        <h1>Fontes de Politica</h1>
        <div className="subtitle">
          Gerencie fontes de dados legislativos e regulatórios.
          <AsOfIndicator />
        </div>
      </header>

      <section className="grid grid-4 section-gap" aria-label="Metricas de fontes" aria-live="polite">
        <Metric label="Total" value={String(sources.length)} note="fontes cadastradas" />
        <Metric label="Ativas" value={String(activeSources)} note="coletando dados" />
        <Metric
          label="Inativas"
          value={String(sources.length - activeSources)}
          note="pausadas"
        />
      </section>

      <div className="card card-pad section-gap">
        <h2 className="mb-16">Nova Fonte</h2>
        <div style={{ display: "flex", gap: 8, alignItems: "flex-end", flexWrap: "wrap" }}>
          <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            <label style={{ fontSize: 12, color: "var(--muted)" }}>Nome</label>
            <input
              className="input"
              placeholder="Ex: DOU"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
            />
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            <label style={{ fontSize: 12, color: "var(--muted)" }}>Tipo</label>
            <input
              className="input"
              placeholder="Ex: gazette"
              value={newType}
              onChange={(e) => setNewType(e.target.value)}
            />
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            <label style={{ fontSize: 12, color: "var(--muted)" }}>URL padrao</label>
            <input
              className="input"
              placeholder="https://..."
              value={newUrl}
              onChange={(e) => setNewUrl(e.target.value)}
            />
          </div>
          <button
            className="btn"
            type="button"
            disabled={!newName.trim() || createMutation.isPending}
            onClick={handleCreate}
          >
            Adicionar
          </button>
        </div>
      </div>

      <div className="card card-pad section-gap" aria-live="polite">
        <h2 className="mb-16">Fontes</h2>
        {sources.length === 0 ? (
          <div className="subtitle">Nenhuma fonte cadastrada.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="table">
              <thead>
                <tr>
                  <th>Nome</th>
                  <th>Tipo</th>
                  <th>URL</th>
                  <th>Ativa</th>
                  <th>Ultima coleta</th>
                  <th>Acoes</th>
                </tr>
              </thead>
              <tbody>
                {sources.map((source) => (
                  <tr key={source.id}>
                    <td>{source.name}</td>
                    <td>
                      <Badge tone="neutral">{source.source_type ?? "—"}</Badge>
                    </td>
                    <td className="max-w-320 truncate mono" style={{ fontSize: 12 }}>
                      {source.url_pattern ?? "—"}
                    </td>
                    <td>
                      <Badge tone={source.is_active ? "good" : "neutral"}>
                        {source.is_active ? "Sim" : "Nao"}
                      </Badge>
                    </td>
                    <td>
                      {source.last_fetched_at
                        ? new Date(source.last_fetched_at).toLocaleDateString("pt-BR", {
                            day: "2-digit",
                            month: "short",
                          })
                        : "—"}
                    </td>
                    <td>
                      <button
                        className="btn"
                        type="button"
                        disabled={deleteMutation.isPending}
                        onClick={() => {
                          if (confirm(`Remover fonte "${source.name}"?`)) {
                            deleteMutation.mutate(source.id);
                          }
                        }}
                      >
                        Remover
                      </button>
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

export default function PolicySourcesPage() {
  return (
    <Suspense fallback={<LoadingSkeleton lines={8} />}>
      <PolicyDataProvider />
    </Suspense>
  );
}

function PolicyDataProvider() {
  const value = usePolicyValue();
  return (
    <PolicyDataContext.Provider value={value}>
      <SourcesContent />
    </PolicyDataContext.Provider>
  );
}
