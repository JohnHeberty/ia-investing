"use client";

import { Suspense } from "react";
import { Gavel } from "lucide-react";
import Link from "next/link";
import type { Route } from "next";
import { PolicyDataContext, usePolicyData, usePolicyValue, useAlertMutations } from "@/hooks/use-policy";
import { AsOfIndicator, Badge, Metric } from "@/components/domain";
import { LoadingSkeleton } from "@/components/data-state-components";
import { useState } from "react";

function AlertsContent() {
  const { alerts, activeAlerts } = usePolicyData();
  const { acknowledge, resolve } = useAlertMutations();
  const [resolveNotes, setResolveNotes] = useState<Record<string, string>>({});

  return (
    <div className="section-gap">
      <header className="page-head">
        <div className="eyebrow">
          <Link href={"/policy" as Route} className="text-accent">
            <Gavel size={14} /> Politica
          </Link>
          {" / Alertas"}
        </div>
        <h1>Alertas de Politica</h1>
        <div className="subtitle">
          Monitoramento de mudancas materiais em policy objects.
          <AsOfIndicator />
        </div>
      </header>

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
                            onClick={() => acknowledge.mutate(alert.id)}
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
                              disabled={resolve.isPending}
                              onClick={() =>
                                resolve.mutate({
                                  alertId: alert.id,
                                  notes: resolveNotes[alert.id] ?? "",
                                })
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
    </div>
  );
}

export default function PolicyAlertsPage() {
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
      <AlertsContent />
    </PolicyDataContext.Provider>
  );
}
