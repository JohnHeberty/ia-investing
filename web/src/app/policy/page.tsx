"use client";

import { Suspense, useState } from "react";
import { useSearchParams } from "next/navigation";
import { toast } from "sonner";
import { Gavel } from "lucide-react";
import { PolicyDataContext, usePolicyData, usePolicyValue, useAlertMutations, useSourceMutations } from "@/hooks/use-policy";
import { AsOfIndicator, Badge, DomainTabs, Metric, StatePanel } from "@/components/domain";
import { DataStatePanel, LoadingSkeleton, StaleWarning } from "@/components/data-state-components";

function TrackerTab() {
  const { events, materialEvents, monitoredObjects, staleSources } = usePolicyData();

  return (
    <>
      <section className="grid grid-4 section-gap" aria-label="Metricas de politica" aria-live="polite">
        <Metric
          label="Eventos materiais"
          value={String(materialEvents.length)}
          note={materialEvents.length > 0 ? "aguarda revisao" : "dado ausente nao vira zero"}
          tone={materialEvents.length > 0 ? "warning" : undefined}
        />
        <Metric
          label="Objetos monitorados"
          value={String(monitoredObjects)}
          note={`${monitoredObjects} objeto${monitoredObjects !== 1 ? "s" : ""}`}
        />
        <Metric
          label="Com probabilidade"
          value={String(events.filter((e) => e.probability !== "—").length)}
          note="de todos os eventos"
        />
        <Metric
          label="Fontes stale"
          value={String(staleSources)}
          note={staleSources > 0 ? "requer atencao" : "todas atualizadas"}
          tone={staleSources > 0 ? "warning" : "positive"}
        />
      </section>

      <div className="card card-pad section-gap" aria-live="polite">
        <div className="card-title">
          <h2>Legislative tracker</h2>
          <span>estagio != probabilidade != impacto</span>
        </div>
        {events.length === 0 ? (
          <DataStatePanel
            state="missing"
            title="Nenhum evento politico registrado"
            detail="Tracker legislativo vazio. Eventos sao adicionados quando ha materialidade identificada."
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="table">
              <thead>
                <tr>
                  <th>Objeto oficial</th>
                  <th>Estagio juridico</th>
                  <th>Probabilidade</th>
                  <th>Exposicao</th>
                  <th>Controle</th>
                </tr>
              </thead>
              <tbody>
                {events.map((event) => (
                  <tr key={event.id}>
                    <td>{event.object_name || event.title}</td>
                    <td>
                      <Badge tone="neutral">{event.stage}</Badge>
                    </td>
                    <td>
                      <Badge tone="warn">{event.probability}</Badge>
                    </td>
                    <td>{event.exposure}</td>
                    <td>
                      <Badge
                        tone={
                          event.control === "Revisão humana"
                            ? "bad"
                            : event.control === "Monitorar"
                              ? "good"
                              : "neutral"
                        }
                      >
                        {event.control}
                      </Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="section-gap">
        <StatePanel
          title="Sem alteracao automatica"
          detail="Impacto material pausa no Temporal; tese e carteira permanecem imutiveis ate decisao humana autorizada."
        />
      </div>
    </>
  );
}

function AlertsTab() {
  const { alerts, activeAlerts } = usePolicyData();
  const { acknowledge, resolve } = useAlertMutations();
  const [resolveNotes, setResolveNotes] = useState<Record<string, string>>({});

  return (
    <>
      <section className="grid grid-4 section-gap" aria-label="Metricas de alertas" aria-live="polite">
        <Metric label="Total" value={String(alerts.length)} note="alertas emitidos" />
        <Metric
          label="Ativos"
          value={String(activeAlerts)}
          note="requer acao"
          tone={activeAlerts > 0 ? "warning" : undefined}
        />
        <Metric
          label="Reconhecidos"
          value={String(alerts.filter((a) => a.acknowledged_at && !a.resolved_at).length)}
          note="em investigacao"
        />
        <Metric
          label="Resolvidos"
          value={String(alerts.filter((a) => a.resolved_at).length)}
          note="encerrados"
        />
      </section>

      <div className="card card-pad section-gap" aria-live="polite">
        <h2 className="mb-16">Alertas</h2>
        {alerts.length === 0 ? (
          <div className="subtitle">Nenhum alerta emitido ainda.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="table">
              <thead>
                <tr>
                  <th>Titulo</th>
                  <th>Tipo</th>
                  <th>Severidade</th>
                  <th>Disparado em</th>
                  <th>Reconhecido</th>
                  <th>Resolvido</th>
                  <th>Acoes</th>
                </tr>
              </thead>
              <tbody>
                {alerts.map((alert) => (
                  <tr key={alert.id}>
                    <td>{alert.title}</td>
                    <td>
                      <Badge tone="neutral">{alert.alert_type}</Badge>
                    </td>
                    <td>
                      <Badge
                        tone={
                          alert.severity === "critical"
                            ? "bad"
                            : alert.severity === "high"
                              ? "warn"
                              : alert.severity === "medium"
                                ? "warn"
                                : "neutral"
                        }
                      >
                        {alert.severity}
                      </Badge>
                    </td>
                    <td>
                      {alert.fired_at
                        ? new Date(alert.fired_at).toLocaleDateString("pt-BR", {
                            day: "2-digit",
                            month: "short",
                            hour: "2-digit",
                            minute: "2-digit",
                          })
                        : "—"}
                    </td>
                    <td>
                      <Badge tone={alert.acknowledged_at ? "good" : "warn"}>
                        {alert.acknowledged_at ? "Sim" : "Nao"}
                      </Badge>
                    </td>
                    <td>
                      <Badge tone={alert.resolved_at ? "good" : "neutral"}>
                        {alert.resolved_at ? "Sim" : "Nao"}
                      </Badge>
                    </td>
                    <td>
                      <div style={{ display: "flex", gap: 8 }}>
                        {!alert.acknowledged_at && (
                          <button
                            className="btn"
                            type="button"
                            disabled={acknowledge.isPending}
                            onClick={() =>
                              acknowledge.mutate(alert.id, {
                                onError: (error: Error) =>
                                  toast.error(`Falha ao reconhecer: ${error.message}`),
                              })
                            }
                          >
                            Reconhecer
                          </button>
                        )}
                        {!alert.resolved_at && (
                          <div style={{ display: "flex", gap: 4 }}>
                            <input
                              className="input"
                              placeholder="Notas"
                              style={{ fontSize: 12, width: 120 }}
                              value={resolveNotes[alert.id] ?? ""}
                              onChange={(e) =>
                                setResolveNotes((prev) => ({ ...prev, [alert.id]: e.target.value }))
                              }
                            />
                            <button
                              className="btn"
                              type="button"
                              disabled={
                                resolve.isPending ||
                                (resolveNotes[alert.id] ?? "").trim().length < 3
                              }
                              onClick={() =>
                                resolve.mutate(
                                  {
                                    alertId: alert.id,
                                    notes: resolveNotes[alert.id] ?? "",
                                  },
                                  {
                                    onError: (error: Error) =>
                                      toast.error(`Falha ao resolver: ${error.message}`),
                                  },
                                )
                              }
                            >
                              Resolver
                            </button>
                          </div>
                        )}
                      </div>
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

function ForecastsTab() {
  const { forecasts, events } = usePolicyData();

  return (
    <>
      <section className="grid grid-4 section-gap" aria-label="Metricas de previsoes" aria-live="polite">
        <Metric label="Previsoes" value={String(forecasts.length)} note="modelos ativos" />
        <Metric
          label="Prob. media"
          value={
            forecasts.length > 0
              ? `${(forecasts.reduce((s, f) => s + f.probability, 0) / forecasts.length * 100).toFixed(0)}%`
              : "—"
          }
          note="entre todas as previsoes"
        />
      </section>

      <div className="card card-pad section-gap" aria-live="polite">
        <h2 className="mb-16">Previsoes</h2>
        {forecasts.length === 0 ? (
          <div className="subtitle">Nenhuma previsao disponivel.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="table">
              <thead>
                <tr>
                  <th>Objeto</th>
                  <th>Resultado alvo</th>
                  <th>Probabilidade</th>
                  <th>Intervalo</th>
                </tr>
              </thead>
              <tbody>
                {forecasts.map((f) => (
                  <tr key={f.id}>
                    <td>{events.find((e) => e.object_id === f.policy_object_id)?.object_name || f.policy_object_id}</td>
                    <td>{f.target_outcome}</td>
                    <td>
                      <Badge tone={f.probability > 0.6 ? "good" : f.probability > 0.3 ? "warn" : "neutral"}>
                        {(f.probability * 100).toFixed(0)}%
                      </Badge>
                    </td>
                    <td className="mono">
                      {f.interval_low !== null && f.interval_high !== null
                        ? `${(f.interval_low * 100).toFixed(0)}% – ${(f.interval_high * 100).toFixed(0)}%`
                        : "—"}
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

function GraphTab() {
  return (
    <div className="grid grid-3 section-gap">
      <article className="card card-pad">
        <h2>Timeline versionada</h2>
        <p className="subtitle">
          Apresentado {'->'} Comissao. Diff: 1 adicao, 1 remocao. Fonte e knowledge_at preservados.
        </p>
      </article>
      <article className="card card-pad">
        <h2>Matriz de exposicao</h2>
        <p className="subtitle">
          Evento {'->'} setor {'->'} driver {'->'} metrica {'->'} emissor {'->'} tese {'->'} carteira, com confianca por aresta.
        </p>
      </article>
      <article className="card card-pad">
        <h2>Corroboracao</h2>
        <p className="subtitle">
          Materialidade combina exposicao, freshness e fontes corroborantes; ausencia nao reduz chance.
        </p>
      </article>
    </div>
  );
}

function SourcesTab() {
  const { sources } = usePolicyData();
  const { createMutation, deleteMutation } = useSourceMutations();
  const [newName, setNewName] = useState("");
  const [newAuthority, setNewAuthority] = useState("camara");
  const [newType, setNewType] = useState("");
  const [newUrl, setNewUrl] = useState("");
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);

  const activeSources = sources.filter((s) => s.is_active).length;

  const handleCreate = () => {
    if (!newName.trim()) return;
    createMutation.mutate(
      {
        name: newName.trim(),
        authority: newAuthority,
        ...(newType.trim() ? { source_type: newType.trim() } : {}),
        ...(newUrl.trim() ? { url_pattern: newUrl.trim() } : {}),
      },
      {
        onSuccess: () => {
          setNewName("");
          setNewAuthority("camara");
          setNewType("");
          setNewUrl("");
        },
      },
    );
  };

  return (
    <>
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
            <label style={{ fontSize: 12, color: "var(--muted)" }}>Autoridade</label>
            <select
              className="input"
              value={newAuthority}
              onChange={(e) => setNewAuthority(e.target.value)}
            >
              <option value="camara">Câmara</option>
              <option value="senado">Senado</option>
              <option value="dou">DOU</option>
            </select>
          </div>
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
                  <th>Autoridade</th>
                  <th>Tipo</th>
                  <th>URL</th>
                  <th>Ativa</th>
                  <th>Ultima coleta</th>
                  <th>Ultimo erro</th>
                  <th>Acoes</th>
                </tr>
              </thead>
              <tbody>
                {sources.map((source) => (
                  <tr key={source.id}>
                    <td>{source.name}</td>
                    <td>
                      <Badge tone="neutral">{source.authority}</Badge>
                    </td>
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
                      {source.last_fetch_error ? (
                        <span style={{ fontSize: 12, color: "var(--red)" }}>
                          {source.last_fetch_error}
                        </span>
                      ) : (
                        "—"
                      )}
                    </td>
                    <td>
                      <button
                        className="btn"
                        type="button"
                        disabled={deleteMutation.isPending}
                        onClick={() => setConfirmDelete(source.id)}
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

      {confirmDelete && (
        <div className="card card-pad section-gap" style={{ borderColor: "var(--red)" }}>
          <p>Tem certeza que deseja remover esta fonte?</p>
          <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
            <button
              className="btn"
              type="button"
              onClick={async () => {
                try {
                  await deleteMutation.mutateAsync(confirmDelete);
                  setConfirmDelete(null);
                } catch (err) {
                  console.error("Failed to delete source", err);
                }
              }}
            >
              Sim, remover
            </button>
            <button
              className="btn"
              type="button"
              onClick={() => setConfirmDelete(null)}
            >
              Cancelar
            </button>
          </div>
        </div>
      )}
    </>
  );
}

function PolicyContent() {
  const policyValue = usePolicyData();
  const searchParams = useSearchParams();
  const activeTab = searchParams.get("tab") ?? "tracker";

  if (policyValue.isLoading) {
    return <LoadingSkeleton lines={8} />;
  }

  if (policyValue.isError) {
    return (
      <DataStatePanel
        state="error"
        title="Erro ao carregar dados de politica"
        detail={
          policyValue.error instanceof Error
            ? policyValue.error.message
            : String(policyValue.error ?? "Erro desconhecido")
        }
      />
    );
  }

  return (
    <div className="section-gap">
      <header className="page-head">
        <div className="eyebrow">
          <Gavel size={14} /> Policy Intelligence
        </div>
        <h1>Fato, chance e impacto separados.</h1>
        <div className="subtitle">
          Tracker legislativo versionado, com fonte oficial, diff, intervalo e caminho de exposicao.
          <AsOfIndicator />
        </div>
      </header>

      {policyValue.dataState === "stale" && <StaleWarning source="policy/events" />}

      <DomainTabs
        label="Politica"
        defaultValue={activeTab}
        tabs={[
          { id: "tracker", label: "Tracker", content: <TrackerTab /> },
          { id: "alertas", label: "Alertas", content: <AlertsTab /> },
          { id: "previsoes", label: "Previsoes", content: <ForecastsTab /> },
          { id: "fontes", label: "Fontes", content: <SourcesTab /> },
          { id: "grafo", label: "Grafo", content: <GraphTab /> },
        ]}
      />
    </div>
  );
}

export default function PolicyPage() {
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
      <PolicyContent />
    </PolicyDataContext.Provider>
  );
}
