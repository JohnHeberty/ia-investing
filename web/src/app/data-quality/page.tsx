"use client";

import { Suspense } from "react";

import { AsOfIndicator, Badge, Metric } from "@/components/domain";
import {
  DataStatePanel,
  LoadingSkeleton,
  StaleWarning,
} from "@/components/data-state-components";
import { FreshnessPill } from "@/components/evidence-tags";
import { useQualityIncidents } from "@/hooks/use-quality-incidents";
import { useUrlState, filterPresets } from "@/hooks/use-url-state";

function DataQualityContent() {
  const [urlState] = useUrlState(filterPresets.dataQuality);
  const {
    incidents,
    sources,
    healthySources,
    staleSources,
    neverSucceededSources,
    totalSources,
    isLoading,
    isError,
    dataState,
    count,
  } = useQualityIncidents();

  if (isLoading) {
    return (
      <>
        <div className="page-head">
          <div>
            <div className="eyebrow">Data quality center</div>
            <h1>Confiança dos dados</h1>
            <p className="subtitle">
              Freshness, completude, quarentena e incidentes sem edição direta de fatos.
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
            <div className="eyebrow">Data quality center</div>
            <h1>Confiança dos dados</h1>
          </div>
        </div>
        <DataStatePanel
          state="error"
          title="Erro ao carregar dados"
          detail="Não foi possível acessar os dados de qualidade. Verifique a conexão com a API."
        />
      </>
    );
  }

  const quarantineCount = incidents.filter((i) => i.status === "open" && i.severity === "high").length;
  const totalIncidents = count;
  const openIncidents = incidents.filter((i) => i.status === "open").length;

  return (
    <>
      <div className="page-head">
        <div>
          <div className="eyebrow">Data quality center</div>
          <h1>Confiança dos dados</h1>
          <p className="subtitle">
            Freshness, completude, quarentena e incidentes sem edição direta de fatos.
          </p>
        </div>
        <AsOfIndicator
          value={new Date().toLocaleString("pt-BR", { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" })}
          freshness={dataState === "stale" ? "Desatualizado" : "Atual"}
        />
      </div>

      {dataState === "stale" && (
        <div style={{ marginBottom: 14 }}>
          <StaleWarning lastUpdated={new Date().toISOString()} source="sources/health" />
        </div>
      )}

      <section className="grid grid-4" aria-label="Métricas de qualidade">
        <Metric
          label="Fontes saudáveis"
          value={`${healthySources}/${totalSources}`}
          note="SLAs dentro da janela"
        />
        <Metric
          label="Incidentes abertos"
          value={String(openIncidents)}
          note={`${totalIncidents} total`}
          tone={openIncidents > 0 ? "warning" : undefined}
        />
        <Metric
          label="Quarentena"
          value={`${quarantineCount} objeto${quarantineCount !== 1 ? "s" : ""}`}
          note="isolados do domínio"
          tone={quarantineCount > 0 ? "warning" : undefined}
        />
        <Metric
          label="Fontes desatualizadas"
          value={String(staleSources)}
          note={staleSources > 0 ? "requer atenção" : "todas atualizadas"}
          tone={staleSources > 0 ? "warning" : "positive"}
        />
      </section>

      <section className="grid grid-3" style={{ marginTop: 14 }}>
        <article className="card card-pad">
          <div className="card-title">
            <h2>Source registry</h2>
            <Badge tone={staleSources > 0 ? "warn" : "good"}>
              {staleSources > 0 ? "Atenção" : "Saudável"}
            </Badge>
          </div>
          <p style={{ color: "var(--muted)", fontSize: 12, lineHeight: 1.65 }}>
            {staleSources > 0
              ? `${staleSources} fonte${staleSources !== 1 ? "s" : ""} excedeu${staleSources !== 1 ? "ram" : ""} a janela de freshness.`
              : "Todas as fontes estão dentro das SLAs de freshness."}
          </p>
          {neverSucceededSources > 0 && (
            <p style={{ color: "var(--red)", fontSize: 11, marginTop: 6 }}>
              {neverSucceededSources} fonte{neverSucceededSources !== 1 ? "s" : ""} nunca retornou sucesso.
            </p>
          )}
        </article>
        <article className="card card-pad">
          <div className="card-title">
            <h2>Fatos e métricas</h2>
            <Badge tone="good">Saudável</Badge>
          </div>
          <p style={{ color: "var(--muted)", fontSize: 12, lineHeight: 1.65 }}>
            Missing e parse_error permanecem explícitos; zero só representa valor reportado.
            Zero nunca substitui dado ausente.
          </p>
        </article>
        <article className="card card-pad">
          <div className="card-title">
            <h2>Incidentes</h2>
            <Badge tone={openIncidents > 0 ? "warn" : "good"}>
              {openIncidents > 0 ? "Abertos" : "Resolvidos"}
            </Badge>
          </div>
          <p style={{ color: "var(--muted)", fontSize: 12, lineHeight: 1.65 }}>
            Transitions exigem autorização, razão, auditoria e waiver com expiração.
            {openIncidents > 0 && ` ${openIncidents} incidente${openIncidents !== 1 ? "s" : ""} aberto${openIncidents !== 1 ? "s" : ""}.`}
          </p>
        </article>
      </section>

      {sources.length > 0 && (
        <section className="card card-pad" style={{ marginTop: 14 }}>
          <div className="card-title">
            <h2>Saúde das fontes</h2>
            <span>{totalSources} fontes</span>
          </div>
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Fonte</th>
                  <th>Código</th>
                  <th>Status</th>
                  <th>Último sucesso</th>
                  <th>Último erro</th>
                  <th>Owner</th>
                </tr>
              </thead>
              <tbody>
                {sources.map((source, index) => {
                  const name = String(source.name ?? source.code ?? `Fonte ${index + 1}`);
                  const code = String(source.code ?? "");
                  const status = String(source.status ?? "unknown") as "healthy" | "stale" | "never_succeeded" | "inactive";
                  const lastSuccess = source.last_success_at ? String(source.last_success_at) : null;
                  const lastFailure = source.last_failure_at ? String(source.last_failure_at) : null;
                  const owner = String(source.owner_role ?? "");

                  return (
                    <tr key={code}>
                      <td style={{ fontWeight: 600 }}>{name}</td>
                      <td className="rank">{code}</td>
                      <td>
                        <Badge
                          tone={
                            status === "healthy"
                              ? "good"
                              : status === "stale"
                                ? "warn"
                                : status === "never_succeeded"
                                  ? "bad"
                                  : "neutral"
                          }
                        >
                          {status === "healthy"
                            ? "Saudável"
                            : status === "stale"
                              ? "Desatualizada"
                              : status === "never_succeeded"
                                ? "Sem sucesso"
                                : "Inativa"}
                        </Badge>
                      </td>
                      <td style={{ fontSize: 11, color: "var(--muted)" }}>
                        {lastSuccess
                          ? new Date(lastSuccess).toLocaleString("pt-BR", {
                              day: "2-digit",
                              month: "short",
                              hour: "2-digit",
                              minute: "2-digit",
                            })
                          : "—"}
                      </td>
                      <td style={{ fontSize: 11, color: lastFailure ? "var(--red)" : "var(--muted)" }}>
                        {lastFailure
                          ? new Date(lastFailure).toLocaleString("pt-BR", {
                              day: "2-digit",
                              month: "short",
                              hour: "2-digit",
                              minute: "2-digit",
                            })
                          : "—"}
                      </td>
                      <td className="rank">{owner}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {incidents.length > 0 && (
        <section className="card card-pad" style={{ marginTop: 14 }}>
          <div className="card-title">
            <h2>Incidentes de qualidade</h2>
            <span>{incidents.length} incidente{incidents.length !== 1 ? "s" : ""}</span>
          </div>
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Severidade</th>
                  <th>Status</th>
                  <th>Impacto</th>
                  <th>Responsável</th>
                  <th>Criado em</th>
                </tr>
              </thead>
              <tbody>
                {incidents.map((incident) => (
                  <tr key={incident.id}>
                    <td className="rank">{incident.id.slice(0, 12)}</td>
                    <td>
                      <Badge
                        tone={
                          incident.severity === "high"
                            ? "bad"
                            : incident.severity === "medium"
                              ? "warn"
                              : "neutral"
                        }
                      >
                        {incident.severity === "high"
                          ? "Alta"
                          : incident.severity === "medium"
                            ? "Média"
                            : "Baixa"}
                      </Badge>
                    </td>
                    <td>
                      <Badge tone={incident.status === "open" ? "warn" : "good"}>
                        {incident.status === "open" ? "Aberto" : incident.status}
                      </Badge>
                    </td>
                    <td style={{ fontSize: 11, color: "var(--muted)", maxWidth: 200 }}>
                      {incident.impact_summary}
                    </td>
                    <td className="rank">{incident.owner_role}</td>
                    <td style={{ fontSize: 11, color: "var(--muted)" }}>
                      {new Date(incident.created_at).toLocaleString("pt-BR", {
                        day: "2-digit",
                        month: "short",
                        hour: "2-digit",
                        minute: "2-digit",
                      })}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </>
  );
}

export default function DataQualityPage() {
  return (
    <Suspense
      fallback={
        <>
          <div className="page-head">
            <div>
              <div className="eyebrow">Data quality center</div>
              <h1>Confiança dos dados</h1>
            </div>
          </div>
          <LoadingSkeleton lines={6} />
        </>
      }
    >
      <DataQualityContent />
    </Suspense>
  );
}
