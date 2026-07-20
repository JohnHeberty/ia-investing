"use client";

import { Suspense } from "react";

import { AsOfIndicator, Badge, Metric } from "@/components/domain";
import {
  DataStatePanel,
  LoadingSkeleton,
  StaleWarning,
} from "@/components/data-state-components";
import { useAudit } from "@/hooks/use-audit";

function AuditContent() {
  const {
    auditEvents,
    totalEvents,
    correlatedEvents,
    correlationRate,
    overrides,
    integrityFailures,
    isLoading,
    isError,
    dataState,
  } = useAudit();

  if (isLoading) {
    return (
      <>
        <div className="page-head">
          <div>
            <div className="eyebrow">Audit trail</div>
            <h1>Linha do tempo verificável</h1>
            <p className="subtitle">
              Atores, versões, hashes, razões e correlation IDs sem payload sensível em claro.
            </p>
          </div>
        </div>
        <section className="grid grid-4">
          <LoadingSkeleton lines={4} />
          <LoadingSkeleton lines={4} />
          <LoadingSkeleton lines={4} />
          <LoadingSkeleton lines={4} />
        </section>
      </>
    );
  }

  if (isError) {
    return (
      <>
        <div className="page-head">
          <div>
            <div className="eyebrow">Audit trail</div>
            <h1>Erro ao carregar trilha de auditoria</h1>
          </div>
        </div>
        <DataStatePanel
          state="error"
          title="Erro ao carregar audit trail"
          detail="Não foi possível acessar os eventos de auditoria. Verifique a conexão com a API."
        />
      </>
    );
  }

  const formattedCount = totalEvents > 0
    ? totalEvents.toLocaleString("pt-BR")
    : "—";

  return (
    <>
      <div className="page-head">
        <div>
          <div className="eyebrow">Audit trail</div>
          <h1>Linha do tempo verificável</h1>
          <p className="subtitle">
            Atores, versões, hashes, razões e correlation IDs sem payload sensível em claro.
          </p>
        </div>
        <AsOfIndicator
          freshness={dataState === "stale" ? "Desatualizado" : "Atual"}
        />
      </div>

      {dataState === "stale" && (
        <div style={{ marginBottom: 14 }}>
          <StaleWarning lastUpdated={new Date().toISOString()} source="agents/runs" />
        </div>
      )}

      <section className="grid grid-4" aria-label="Métricas de auditoria">
        <Metric
          label="Eventos hoje"
          value={formattedCount}
          note="append-only"
        />
        <Metric
          label="Correlacionados"
          value={`${correlationRate}%`}
          note="workflow e domínio"
          tone={correlationRate >= 90 ? "positive" : undefined}
        />
        <Metric
          label="Overrides"
          value={String(overrides)}
          note={overrides > 0 ? "expiração registrada" : "nenhum"}
          tone={overrides > 0 ? "warning" : undefined}
        />
        <Metric
          label="Falhas de integridade"
          value={String(integrityFailures)}
          note={integrityFailures > 0 ? "requer investigação" : "últimos 30 dias"}
          tone={integrityFailures === 0 ? "positive" : "negative"}
        />
      </section>

      {/* Audit events table */}
      {auditEvents.length > 0 ? (
        <section className="card card-pad" style={{ marginTop: 14 }}>
          <div className="card-title">
            <h2>Eventos recentes</h2>
            <span>{auditEvents.length} evento{auditEvents.length !== 1 ? "s" : ""}</span>
          </div>
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Tipo</th>
                  <th>Ator</th>
                  <th>Alvo</th>
                  <th>Correlation ID</th>
                  <th>Timestamp</th>
                  <th>Integridade</th>
                </tr>
              </thead>
              <tbody>
                {auditEvents.slice(0, 15).map((event) => (
                  <tr key={event.id}>
                    <td>
                      <Badge
                        tone={
                          event.type === "succeeded"
                            ? "good"
                            : event.type === "failed"
                              ? "bad"
                              : event.type === "source_health"
                                ? "warn"
                                : "neutral"
                        }
                      >
                        {event.type === "succeeded"
                          ? "Sucesso"
                          : event.type === "failed"
                            ? "Falha"
                            : event.type === "source_health"
                              ? "Fonte"
                              : event.type}
                      </Badge>
                    </td>
                    <td style={{ fontSize: 12 }}>{event.actor}</td>
                    <td style={{ fontSize: 12, color: "var(--muted)" }}>{event.target}</td>
                    <td
                      style={{
                        fontFamily: "var(--font-mono)",
                        fontSize: 11,
                        color: "var(--muted)",
                      }}
                    >
                      {event.correlationId.slice(0, 12)}…
                    </td>
                    <td style={{ fontSize: 12, color: "var(--muted)" }}>
                      {event.timestamp
                        ? new Date(event.timestamp).toLocaleString("pt-BR", {
                            day: "2-digit",
                            month: "short",
                            hour: "2-digit",
                            minute: "2-digit",
                          })
                        : "—"}
                    </td>
                    <td>
                      <Badge tone={event.integrity === "ok" ? "good" : "bad"}>
                        {event.integrity === "ok" ? "OK" : "Falha"}
                      </Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ) : (
        <div style={{ marginTop: 14 }}>
          <DataStatePanel
            state="empty"
            title="Nenhum evento de auditoria"
            detail="A trilha de auditoria é populada automaticamente a partir de runs de agent e mudanças de fonte."
          />
        </div>
      )}

      <section className="grid grid-3" style={{ marginTop: 14 }}>
        <article className="card card-pad">
          <div className="card-title">
            <h2>Pesquisa</h2>
            <Badge tone="good">Saudável</Badge>
          </div>
          <p style={{ color: "var(--muted)", fontSize: 12, lineHeight: 1.65 }}>
            Cases, claims, evidence, reviews e teses preservam before/after hashes.
          </p>
        </article>
        <article className="card card-pad">
          <div className="card-title">
            <h2>Carteiras</h2>
            <Badge tone="good">Saudável</Badge>
          </div>
          <p style={{ color: "var(--muted)", fontSize: 12, lineHeight: 1.65 }}>
            Mandatos, proposals, decisões e NAV revisions são rastreáveis por organização.
          </p>
        </article>
        <article className="card card-pad">
          <div className="card-title">
            <h2>Agents e dados</h2>
            <Badge tone={integrityFailures > 0 ? "warn" : "good"}>
              {integrityFailures > 0 ? "Atenção" : "Saudável"}
            </Badge>
          </div>
          <p style={{ color: "var(--muted)", fontSize: 12, lineHeight: 1.65 }}>
            Artefatos imutáveis, tool calls e incidentes mantêm versões originais.
          </p>
        </article>
      </section>
    </>
  );
}

export default function AuditPage() {
  return (
    <Suspense
      fallback={
        <>
          <div className="page-head">
            <div>
              <div className="eyebrow">Audit trail</div>
              <h1>Linha do tempo verificável</h1>
            </div>
          </div>
          <LoadingSkeleton lines={6} />
        </>
      }
    >
      <AuditContent />
    </Suspense>
  );
}
