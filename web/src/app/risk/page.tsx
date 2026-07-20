"use client";

import { Suspense } from "react";

import { AsOfIndicator, Badge, Metric } from "@/components/domain";
import {
  DataStatePanel,
  LoadingSkeleton,
  PartialDataIndicator,
  StaleWarning,
} from "@/components/data-state-components";
import { ScenarioWaterfall, type ScenarioEntry } from "@/components/decision-components";
import { useRiskAssessments } from "@/hooks/use-risk-assessments";
import { useUrlState, filterPresets } from "@/hooks/use-url-state";

function RiskContent() {
  const [urlState] = useUrlState(filterPresets.risk);
  const {
    assessment,
    sources,
    staleCount,
    healthyCount,
    totalSources,
    isLoading,
    isError,
    dataState,
  } = useRiskAssessments();

  if (isLoading) {
    return (
      <>
        <div className="page-head">
          <div>
            <div className="eyebrow">Risk center</div>
            <h1>Risco institucional</h1>
            <p className="subtitle">
              Limites, exposures, stress e waivers por snapshot e policy versionada.
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
            <div className="eyebrow">Risk center</div>
            <h1>Risco institucional</h1>
          </div>
        </div>
        <DataStatePanel
          state="error"
          title="Erro ao carregar dados de risco"
          detail="Não foi possível acessar os dados de risco. Verifique a conexão com a API."
        />
      </>
    );
  }

  const breaches = assessment.breaches ?? [];
  const hardBreaches = breaches.filter((b) => b.limit_type === "hard");
  const softBreaches = breaches.filter((b) => b.limit_type === "soft");

  const scenarios: ScenarioEntry[] = [
    { name: "Choque de juros", impact: -0.012, cumulative: -0.012 },
    { name: "Elevação cambial", impact: -0.008, cumulative: -0.020 },
    { name: "Crise commodities", impact: -0.006, cumulative: -0.026 },
    { name: "Retorno mercado", impact: 0.018, cumulative: -0.008 },
  ];

  return (
    <>
      <div className="page-head">
        <div>
          <div className="eyebrow">Risk center</div>
          <h1>Risco institucional</h1>
          <p className="subtitle">
            Limites, exposures, stress e waivers por snapshot e policy versionada.
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

      {staleCount > 0 && totalSources > 0 && (
        <div style={{ marginBottom: 14 }}>
          <PartialDataIndicator
            coverage={Math.round((healthyCount / totalSources) * 100)}
            missingFields={sources.filter((s) => s.status !== "healthy").map((s) => String(s.name ?? s.code ?? ""))}
          />
        </div>
      )}

      <section className="grid grid-4" aria-label="Indicadores de risco">
        <Metric
          label="Hard breaches"
          value={String(hardBreaches.length)}
          note={hardBreaches.length > 0 ? "bloqueia proposta" : "nenhum ativo"}
          tone={hardBreaches.length > 0 ? "negative" : undefined}
        />
        <Metric
          label="Soft breaches"
          value={String(softBreaches.length)}
          note={softBreaches.length > 0 ? "requer justificativa" : "nenhum ativo"}
          tone={softBreaches.length > 0 ? "warning" : undefined}
        />
        <Metric
          label="Fontes saudáveis"
          value={`${healthyCount}/${totalSources}`}
          note="SLAs dentro da janela"
        />
        <Metric
          label="Fontes desatualizadas"
          value={String(staleCount)}
          note={staleCount > 0 ? "requer atenção" : "todas atualizadas"}
          tone={staleCount > 0 ? "warning" : "positive"}
        />
      </section>

      <section className="grid grid-3" style={{ marginTop: 14 }}>
        <article className="card card-pad">
          <div className="card-title">
            <h2>Concentração</h2>
            <Badge tone={hardBreaches.length > 0 ? "bad" : "good"}>
              {hardBreaches.length > 0 ? "Atenção" : "Saudável"}
            </Badge>
          </div>
          <p style={{ color: "var(--muted)", fontSize: 12, lineHeight: 1.65 }}>
            {hardBreaches.length > 0
              ? `${hardBreaches.length} exposição ultrapassou o hard limit.`
              : "Todos os limites de concentração estão dentro dos parâmetros."}
          </p>
          {hardBreaches.length > 0 && (
            <div style={{ marginTop: 8 }}>
              {hardBreaches.map((b) => (
                <div
                  key={b.id}
                  style={{
                    fontSize: 11,
                    padding: "6px 8px",
                    background: "var(--surface-2)",
                    borderRadius: 6,
                    marginBottom: 4,
                    display: "flex",
                    justifyContent: "space-between",
                  }}
                >
                  <span>{b.limit_name}</span>
                  <span style={{ fontFamily: "var(--font-mono)", color: "var(--red)" }}>
                    {b.observed_value} / {b.limit_value}
                  </span>
                </div>
              ))}
            </div>
          )}
        </article>
        <article className="card card-pad">
          <div className="card-title">
            <h2>Liquidez</h2>
            <Badge tone="good">Saudável</Badge>
          </div>
          <p style={{ color: "var(--muted)", fontSize: 12, lineHeight: 1.65 }}>
            97% da carteira é liquidável dentro da janela definida pelo mandato.
            Dados de liquidez preservados no snapshot de avaliação.
          </p>
        </article>
        <article className="card card-pad">
          <div className="card-title">
            <h2>Volatilidade</h2>
          </div>
          <p style={{ color: "var(--muted)", fontSize: 12, lineHeight: 1.65 }}>
            VaR e volatilidade calculados no backend.
            {assessment.volatility
              ? ` Volatilidade atual: ${assessment.volatility}`
              : " Dados de volatilidade indisponíveis no momento."}
          </p>
        </article>
      </section>

      <div style={{ marginTop: 14 }}>
        <ScenarioWaterfall scenarios={scenarios} />
      </div>

      {breaches.length > 0 && (
        <section className="card card-pad" style={{ marginTop: 14 }}>
          <div className="card-title">
            <h2>Breaches registrados</h2>
            <span>{breaches.length} total</span>
          </div>
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Limite</th>
                  <th>Tipo</th>
                  <th className="numeric">Limite</th>
                  <th className="numeric">Observado</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {breaches.map((b) => (
                  <tr key={b.id}>
                    <td style={{ fontWeight: 600 }}>{b.limit_name}</td>
                    <td>
                      <Badge tone={b.limit_type === "hard" ? "bad" : "warn"}>
                        {b.limit_type}
                      </Badge>
                    </td>
                    <td className="numeric" style={{ fontFamily: "var(--font-mono)" }}>
                      {b.limit_value}
                    </td>
                    <td
                      className="numeric"
                      style={{ fontFamily: "var(--font-mono)", color: "var(--red)" }}
                    >
                      {b.observed_value}
                    </td>
                    <td>
                      <Badge tone={b.status === "open" ? "bad" : "good"}>
                        {b.status === "open" ? "Aberto" : b.status}
                      </Badge>
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

export default function RiskPage() {
  return (
    <Suspense
      fallback={
        <>
          <div className="page-head">
            <div>
              <div className="eyebrow">Risk center</div>
              <h1>Risco institucional</h1>
            </div>
          </div>
          <LoadingSkeleton lines={6} />
        </>
      }
    >
      <RiskContent />
    </Suspense>
  );
}
