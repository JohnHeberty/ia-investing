"use client";

import { ArrowUpRight, CircleAlert, FileText, ShieldCheck, Filter } from "lucide-react";
import { Suspense, useMemo } from "react";

import { AsOfIndicator, Badge, Metric } from "@/components/domain";
import {
  DataStatePanel,
  LoadingSkeleton,
  StaleWarning,
} from "@/components/data-state-components";
import { ConfidenceBar } from "@/components/evidence-tags";
import { useAgentRuns } from "@/hooks/use-agent-runs";
import { usePortfolios } from "@/hooks/use-portfolios";
import { useResearchCases } from "@/hooks/use-research-cases";
import { useRiskAssessments } from "@/hooks/use-risk-assessments";
import { useUrlState, filterPresets } from "@/hooks/use-url-state";

export function MissionControlContent() {
  const [filters, setFilters] = useUrlState(filterPresets.missionControl);

  const { portfolios, isLoading: portfoliosLoading, dataState: portfoliosState, count: portfolioCount } =
    usePortfolios({ state: filters.status ?? undefined });
  const { assessment, sources, staleCount, healthyCount, totalSources, isLoading: riskLoading, dataState: riskState } =
    useRiskAssessments();
  const { runs, completedRuns, totalCost, isLoading: agentsLoading, dataState: agentsState, count: runCount } =
    useAgentRuns({ status: filters.status ?? undefined });
  const { cases, openCases, researchCases, readyForCommittee, isLoading: casesLoading, dataState: casesState } =
    useResearchCases();

  const isLoading = portfoliosLoading || riskLoading || agentsLoading || casesLoading;
  const hasError = portfoliosState === "error" || riskState === "error" || agentsState === "error" || casesState === "error";
  const isStale = portfoliosState === "stale" || riskState === "stale" || agentsState === "stale" || casesState === "stale";

  // Filter eligible portfolios: only show eligible ones, same currency (BRL), and matching category
  const eligiblePortfolios = useMemo(() => {
    return portfolios.filter((p) => {
      // Only show BRL portfolios for comparison (currency consistency)
      if (p.base_currency !== "BRL") return false;
      // Filter by category if set
      if (filters.category && p.category !== filters.category) return false;
      // Filter by eligibility
      const isEligible = p.eligible !== false;
      if (filters.eligibility === "eligible" && !isEligible) return false;
      if (filters.eligibility === "ineligible" && isEligible) return false;
      // "all" shows everything that passes currency/category filter
      return true;
    });
  }, [portfolios, filters.category, filters.eligibility]);

  if (isLoading) {
    return (
      <>
        <div className="page-head">
          <div>
            <div className="eyebrow">Mission control</div>
            <h1>Decisões com contexto, não ruído.</h1>
            <p className="subtitle">
              Visão consolidada das carteiras-modelo, riscos materiais e trabalho pendente da equipe.
            </p>
          </div>
          <LoadingSkeleton lines={2} style={{ minWidth: 200 }} />
        </div>
        <section className="grid grid-4" aria-label="Indicadores principais">
          <LoadingSkeleton lines={4} />
          <LoadingSkeleton lines={4} />
          <LoadingSkeleton lines={4} />
          <LoadingSkeleton lines={4} />
        </section>
      </>
    );
  }

  if (hasError) {
    return (
      <>
        <div className="page-head">
          <div>
            <div className="eyebrow">Mission control</div>
            <h1>Decisões com contexto, não ruído.</h1>
          </div>
        </div>
        <DataStatePanel
          state="error"
          title="Erro ao carregar dados"
          detail="Não foi possível acessar um ou mais endpoints. Verifique a conexão com a API."
        />
      </>
    );
  }

  const breachesCount = assessment.breaches?.length ?? 0;
  const hardBreaches = assessment.breaches?.filter((b) => b.limit_type === "hard").length ?? 0;
  const softBreaches = breachesCount - hardBreaches;

  return (
    <>
      <div className="page-head">
        <div>
          <div className="eyebrow">Mission control</div>
          <h1>Decisões com contexto, não ruído.</h1>
          <p className="subtitle">
            Visão consolidada das carteiras-modelo, riscos materiais e trabalho pendente da equipe.
          </p>
        </div>
        <AsOfIndicator
          value={new Date().toLocaleString("pt-BR", { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" })}
          freshness={isStale ? "Desatualizado" : "Atual"}
        />
      </div>

      {isStale && (
        <div style={{ marginBottom: 14 }}>
          <StaleWarning
            lastUpdated={new Date().toISOString()}
            source="model-portfolios"
          />
        </div>
      )}

      <section className="grid grid-4" aria-label="Indicadores principais">
        <Metric
          label="Carteiras ativas"
          value={String(eligiblePortfolios.length)}
          note={`${eligiblePortfolios.length} elegível${eligiblePortfolios.length !== 1 ? "s" : ""} de ${portfolioCount} total`}
        />
        <Metric
          label="Runs concluídos"
          value={String(completedRuns)}
          note={`${runCount} execuções no total`}
          tone="positive"
        />
        <Metric
          label="Risco ativo"
          value={`${breachesCount} limite${breachesCount !== 1 ? "s" : ""}`}
          note={`${hardBreaches} hard · ${softBreaches} soft`}
          tone={breachesCount > 0 ? "warning" : undefined}
        />
        <Metric
          label="Fontes saudáveis"
          value={`${healthyCount}/${totalSources}`}
          note={`${staleCount} desatualizada${staleCount !== 1 ? "s" : ""}`}
          tone={staleCount === 0 ? "positive" : "warning"}
        />
      </section>

      <div className="split">
        <section className="card card-pad">
          <div className="card-title">
            <h2>Carteiras elegíveis · Top comparável</h2>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span>BRL · 12–24 meses</span>
              <div style={{ position: "relative" }}>
                <label htmlFor="eligibility-filter" className="sr-only">Filtrar por elegibilidade</label>
                <select
                  id="eligibility-filter"
                  value={filters.eligibility ?? "eligible"}
                  onChange={(e) => setFilters({ eligibility: e.target.value || undefined })}
                  style={{
                    appearance: "none",
                    background: "var(--surface-2)",
                    border: "1px solid var(--line)",
                    borderRadius: 6,
                    padding: "4px 24px 4px 8px",
                    fontSize: 11,
                    color: "var(--text)",
                    cursor: "pointer",
                    backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%238eaaa0' stroke-width='2'%3E%3Cpath d='M6 9l6 6 6-6'/%3E%3C/svg%3E")`,
                    backgroundRepeat: "no-repeat",
                    backgroundPosition: "right 6px center",
                  }}
                  aria-label="Filtrar por elegibilidade"
                >
                  <option value="eligible">Elegíveis</option>
                  <option value="all">Todas</option>
                  <option value="ineligible">Inelegíveis</option>
                </select>
              </div>
            </div>
          </div>
          {eligiblePortfolios.length === 0 ? (
            <DataStatePanel
              state="missing"
              title="Nenhuma carteira encontrada"
              detail="Nenhuma carteira-modelo elegível está registrada no sistema."
            />
          ) : (
            <div className="table-wrap">
              <table className="table" role="table" aria-label="Carteiras elegíveis para comparação">
                <thead>
                  <tr>
                    <th scope="col">#</th>
                    <th scope="col">Carteira</th>
                    <th scope="col">Estado</th>
                    <th scope="col">Moeda</th>
                    <th scope="col">Ambiente</th>
                  </tr>
                </thead>
                <tbody>
                  {eligiblePortfolios.slice(0, 8).map((item, index) => (
                    <tr key={item.id}>
                      <td className="rank">0{index + 1}</td>
                      <td>
                        <div className="portfolio-name">{item.name}</div>
                        <div className="portfolio-meta">{item.mandate_id.slice(0, 8)}…</div>
                      </td>
                      <td>
                        <Badge
                          tone={
                            item.state === "active"
                              ? "good"
                              : item.state === "draft"
                                ? "warn"
                                : "neutral"
                          }
                        >
                          {item.state === "active"
                            ? "Ativa"
                            : item.state === "draft"
                              ? "Rascunho"
                              : item.state}
                        </Badge>
                      </td>
                      <td className="numeric">{item.base_currency}</td>
                      <td>
                        <Badge tone={item.environment === "production" ? "good" : "neutral"}>
                          {item.environment === "production" ? "Prod" : item.environment}
                        </Badge>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        <section className="card card-pad">
          <div className="card-title">
            <h2>Eventos materiais</h2>
            <span>últimas 24h</span>
          </div>
          <div className="timeline">
            {staleCount > 0 && (
              <div className="event">
                <div className="event-icon">
                  <CircleAlert size={12} />
                </div>
                <div>
                  <strong>Fontes desatualizadas</strong>
                  <p>{staleCount} fonte{staleCount !== 1 ? "s" : ""} excedeu a janela de freshness.</p>
                </div>
                <time>
                  {new Date().toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })}
                </time>
              </div>
            )}
            {hardBreaches > 0 && (
              <div className="event">
                <div className="event-icon">
                  <ShieldCheck size={12} />
                </div>
                <div>
                  <strong>Hard breach ativo</strong>
                  <p>{hardBreaches} limite{hardBreaches !== 1 ? "s" : ""} rígido{hardBreaches !== 1 ? "s" : ""} violado{hardBreaches !== 1 ? "s" : ""}.</p>
                </div>
                <time>
                  {new Date().toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })}
                </time>
              </div>
            )}
            {openCases > 0 && (
              <div className="event">
                <div className="event-icon">
                  <FileText size={12} />
                </div>
                <div>
                  <strong>Casos abertos</strong>
                  <p>{openCases} caso{openCases !== 1 ? "s" : ""} aguardando triagem ou análise.</p>
                </div>
                <time>
                  {new Date().toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })}
                </time>
              </div>
            )}
            {staleCount === 0 && hardBreaches === 0 && openCases === 0 && (
              <div className="event">
                <div className="event-icon">
                  <ShieldCheck size={12} />
                </div>
                <div>
                  <strong>Sem eventos críticos</strong>
                  <p>Todos os indicadores dentro dos limites esperados.</p>
                </div>
                <time>
                  {new Date().toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })}
                </time>
              </div>
            )}
          </div>
        </section>
      </div>

      <section className="grid grid-3" style={{ marginTop: 14 }}>
        <article className="card card-pad">
          <div className="card-title">
            <h2>Funil de pesquisa</h2>
            <ArrowUpRight size={14} />
          </div>
          <MetricLine label="Casos abertos" value={String(openCases)} />
          <MetricLine label="Em pesquisa" value={String(researchCases)} />
          <MetricLine label="Prontos para comitê" value={String(readyForCommittee)} />
        </article>
        <article className="card card-pad">
          <div className="card-title">
            <h2>Operação de agents</h2>
            <span>hoje</span>
          </div>
          <MetricLine label="Runs concluídos" value={String(completedRuns)} tone="positive" />
          <MetricLine label="Total de runs" value={String(runCount)} />
          <MetricLine label="Custo acumulado" value={`US$ ${totalCost.toFixed(2)}`} />
        </article>
        <article className="card card-pad">
          <div className="card-title">
            <h2>Qualidade dos dados</h2>
            <span>fontes</span>
          </div>
          <MetricLine label="Fontes saudáveis" value={`${healthyCount}/${totalSources}`} tone="positive" />
          <MetricLine label="Desatualizadas" value={String(staleCount)} tone={staleCount > 0 ? "warning" : undefined} />
          <MetricLine label="Nunca retornaram" value={String(assessment.concentration?.stale_sources ?? 0)} tone="negative" />
        </article>
      </section>
    </>
  );
}

export default function MissionControlPage() {
  return (
    <Suspense
      fallback={
        <>
          <div className="page-head">
            <div>
              <div className="eyebrow">Mission control</div>
              <h1>Decisões com contexto, não ruído.</h1>
            </div>
          </div>
          <LoadingSkeleton lines={6} />
        </>
      }
    >
      <MissionControlContent />
    </Suspense>
  );
}

function MetricLine({ label, value, tone }: { label: string; value: string; tone?: string }) {
  return (
    <div
      style={{
        display: "flex",
        justifyContent: "space-between",
        padding: "11px 0",
        borderTop: "1px solid var(--line-soft)",
        fontSize: 11,
      }}
    >
      <span style={{ color: "var(--muted)" }}>{label}</span>
      <strong className={tone} style={{ fontFamily: "var(--font-mono)" }}>
        {value}
      </strong>
    </div>
  );
}
