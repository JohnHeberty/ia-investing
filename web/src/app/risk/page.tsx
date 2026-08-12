"use client";

import { Suspense } from "react";

import { AsOfIndicator, Badge, Metric } from "@/components/domain";
import {
  DataStatePanel,
  LoadingSkeleton,
  StaleWarning,
} from "@/components/data-state-components";
import { ScenarioWaterfall, type ScenarioEntry } from "@/components/decision-components";
import { useSourceHealthSummary } from "@/hooks/use-source-health-summary";
import { useRiskOverview } from "@/hooks/use-risk-overview";

function RiskContent() {
  const {
    sources,
    staleCount,
    healthyCount,
    totalSources,
    isLoading: sourceLoading,
    isError: sourceError,
    dataState,
  } = useSourceHealthSummary();

  const {
    overview,
    isLoading: riskLoading,
    isError: riskError,
  } = useRiskOverview();

  const isLoading = sourceLoading || riskLoading;
  const isError = sourceError || riskError;

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

  const breaches = overview?.breaches ?? [];
  const hardBreaches = breaches.filter((b) => b.limit_type === "hard" && b.status === "open");
  const softBreaches = breaches.filter((b) => b.limit_type === "soft" && b.status === "open");

  const stressScenarios: ScenarioEntry[] = (overview?.stress_scenarios ?? []).map((s) => ({
    name: s.name,
    impact: s.nav_impact_ratio ?? s.pnl_impact ?? 0,
    cumulative: 0,
  }));

  const scenarios = stressScenarios.length > 0
    ? stressScenarios.reduce<ScenarioEntry[]>((acc, s, i) => {
        const cumulative = i === 0 ? s.impact : (acc[i - 1]?.cumulative ?? 0) + s.impact;
        acc.push({ ...s, cumulative });
        return acc;
      }, [])
    : [];

  const volatility = overview?.latest_volatility;
  const drawdown = overview?.latest_drawdown;

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
        <div className="section-gap">
          <StaleWarning source="sources/health" />
        </div>
      )}

      {staleCount > 0 && totalSources > 0 && (
        <div className="section-gap">
          <div className="card card-pad">
            <div className="card-title">
              <h2>Cobertura de Dados</h2>
              <Badge tone={healthyCount > 0 ? "good" : "warn"}>
                {Math.round((healthyCount / totalSources) * 100)}% fontes institucionais
              </Badge>
            </div>
            <p style={{ fontSize: 13, color: "var(--muted)", marginTop: 8 }}>
              Dados de mercado (preços, fundamentais) são fornecidos via <strong>yfinance</strong> e estão disponíveis em tempo real.
              As fontes institucionais abaixo aguardam ativação do Temporal Worker para ingestão automática.
            </p>
            <div style={{ marginTop: 12, display: "flex", flexWrap: "wrap", gap: 6 }}>
              {sources.filter((s) => s.status !== "healthy").map((s) => (
                <span key={String(s.code ?? s.name)} className="badge" data-tone="warn">
                  {String(s.name ?? s.code ?? "")}
                </span>
              ))}
            </div>
          </div>
        </div>
      )}

      <section className="grid grid-4 section-gap" aria-label="Indicadores de risco" aria-live="polite">
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
          value={totalSources > 0 ? `${healthyCount}/${totalSources}` : "\u2014"}
          note="SLAs dentro da janela"
        />
        <Metric
          label="Fontes desatualizadas"
          value={String(staleCount)}
          note={staleCount > 0 ? "requer atenção" : "todas atualizadas"}
          tone={staleCount > 0 ? "warning" : "positive"}
        />
      </section>

      <section className="grid grid-3 section-gap">
        <article className="card card-pad">
          <div className="card-title">
            <h2>Concentração</h2>
            <Badge tone={hardBreaches.length > 0 ? "bad" : "good"}>
              {hardBreaches.length > 0 ? "Atenção" : "Saudável"}
            </Badge>
          </div>
          <p style={{ color: "var(--muted)", fontSize: 12, lineHeight: 1.65 }}>
            {hardBreaches.length > 0
              ? `${hardBreaches.length} exposição(ões) ultrapassou(ram) o hard limit.`
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
          {hardBreaches.length === 0 && (
            <div style={{ marginTop: 8, fontSize: 11, color: "var(--muted)" }}>
              {overview?.total_snapshots ?? 0} snapshots de risco registrados
            </div>
          )}
        </article>
        <article className="card card-pad">
          <div className="card-title">
            <h2>Liquidez</h2>
            <Badge tone={overview?.snapshots?.[0]?.liquidity ? "good" : "neutral"}>
              {overview?.snapshots?.[0]?.liquidity ? "Dados disponíveis" : "Sem dados"}
            </Badge>
          </div>
          <p style={{ color: "var(--muted)", fontSize: 12, lineHeight: 1.65 }}>
            {overview?.snapshots?.[0]?.liquidity
              ? `Dados de liquidez preservados no snapshot.`
              : "Dados de liquidez serão exibidos após execução de assessment de risco."}
          </p>
        </article>
        <article className="card card-pad">
          <div className="card-title">
            <h2>Volatilidade</h2>
            {volatility !== null && volatility !== undefined && (
              <Badge tone={volatility > 0.25 ? "bad" : volatility > 0.15 ? "warn" : "good"}>
                {volatility > 0.25 ? "Alta" : volatility > 0.15 ? "Moderada" : "Baixa"}
              </Badge>
            )}
          </div>
          <p style={{ color: "var(--muted)", fontSize: 12, lineHeight: 1.65 }}>
            {volatility !== null && volatility !== undefined
              ? <>Volatilidade: <strong>{(volatility * 100).toFixed(1)}%</strong> anualizada</>
              : "Dados de volatilidade serão exibidos após execução de assessment de risco."}
          </p>
          {drawdown !== null && drawdown !== undefined && (
            <p style={{ color: "var(--red)", fontSize: 12, marginTop: 4 }}>
              Max drawdown: {(drawdown * 100).toFixed(1)}%
            </p>
          )}
        </article>
      </section>

      {scenarios.length > 0 && (
        <div className="section-gap">
          <ScenarioWaterfall scenarios={scenarios} />
        </div>
      )}

      {scenarios.length === 0 && (
        <div className="section-gap">
          <DataStatePanel
            state="missing"
            title="Cenários de stress"
            detail="Cenários de stress testing aparecerão aqui após execução de assessment de risco institucional."
          />
        </div>
      )}

      {breaches.length > 0 && (
        <section className="card card-pad section-gap" aria-live="polite">
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
