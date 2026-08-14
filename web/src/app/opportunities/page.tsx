"use client";

import { Suspense, useState } from "react";
import { FolderOpen, Plus } from "lucide-react";

import { AsOfIndicator, Badge, Metric } from "@/components/domain";
import { DataStatePanel, LoadingSkeleton, StaleWarning } from "@/components/data-state-components";
import { CaseCard } from "@/components/opportunities/CaseCard";
import { CreateCaseForm } from "@/components/opportunities/CreateCaseForm";
import { useResearchCases } from "@/hooks/use-research-cases";
import { usePermissions } from "@/hooks/use-permissions";

/* ------------------------------------------------------------------ */
/*  Helper — funnel bar                                                */
/* ------------------------------------------------------------------ */
function FunnelRow({
  label,
  value,
  total,
  tone,
}: {
  label: string;
  value: number;
  total: number;
  tone: "neutral" | "warn" | "good";
}) {
  const pct = total > 0 ? (value / total) * 100 : 0;
  return (
    <div className="funnel-row">
      <span className="funnel-label">{label}</span>
      <div className="funnel-bar">
        <div
          className="h-full rounded-4"
          style={{
            width: `${pct}%`,
            background:
              tone === "good"
                ? "var(--accent)"
                : tone === "warn"
                  ? "var(--amber)"
                  : "var(--muted-2)",
          }}
        />
      </div>
      <span className="funnel-count">{value}</span>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Main page content                                                 */
/* ------------------------------------------------------------------ */
function OpportunitiesContent() {
  const {
    cases,
    openCases,
    researchCases,
    readyForCommittee,
    isLoading,
    isError,
    dataState,
    count,
  } = useResearchCases();
  const { can } = usePermissions();
  const canCreateCase = can("research_cases:create");
  const [showNewCaseForm, setShowNewCaseForm] = useState(false);

  if (isLoading) {
    return (
      <>
        <div className="page-head">
          <div>
            <div className="eyebrow">Research funnel</div>
            <h1>Oportunidades</h1>
            <p className="subtitle">
              Triagem auditável por origem, materialidade e evidência disponível.
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
            <div className="eyebrow">Research funnel</div>
            <h1>Oportunidades</h1>
          </div>
        </div>
        <DataStatePanel
          state="error"
          title="Erro ao carregar oportunidades"
          detail="Não foi possível acessar os casos de pesquisa. Verifique a conexão com a API."
        />
      </>
    );
  }

  const conversionRate = count > 0 ? Math.round((readyForCommittee / count) * 100) : 0;

  return (
    <>
      <div className="page-head">
        <div>
          <div className="eyebrow">Research funnel</div>
          <h1>Oportunidades</h1>
          <p className="subtitle">
            Triagem auditável por origem, materialidade e evidência disponível.
          </p>
        </div>
        <div className="flex items-center gap-12">
          <AsOfIndicator freshness={dataState === "stale" ? "Desatualizado" : "Atual"} />
          {canCreateCase ? (
            <button
              className="button"
              onClick={() => setShowNewCaseForm((prev) => !prev)}
              aria-label="Abrir novo caso de pesquisa"
              aria-expanded={showNewCaseForm}
            >
              <span className="inline-flex items-center gap-6">
                <Plus size={14} />
                Abrir novo caso
              </span>
            </button>
          ) : (
            <Badge tone="neutral">Sem permissão</Badge>
          )}
        </div>
      </div>

      {showNewCaseForm && canCreateCase && (
        <CreateCaseForm onClose={() => setShowNewCaseForm(false)} />
      )}

      {dataState === "stale" && (
        <div className="section-gap">
          <StaleWarning source="research/cases" />
        </div>
      )}

      <section
        className="grid grid-4 section-gap"
        aria-label="Indicadores de oportunidades"
        aria-live="polite"
      >
        <Metric label="Novas" value={String(openCases)} note="abertas ou triadas" />
        <Metric
          label="Em pesquisa"
          value={String(researchCases)}
          note="análise ativa"
          tone={researchCases > 5 ? "warning" : undefined}
        />
        <Metric
          label="Prontas para comitê"
          value={String(readyForCommittee)}
          note="aguardando decisão"
        />
        <Metric label="Convertidas" value={`${conversionRate}%`} note="janela de 30 dias" />
      </section>

      {count === 0 ? (
        <div className="section-gap">
          <DataStatePanel
            state="empty"
            title="Nenhum caso de pesquisa encontrado"
            detail="Não existem oportunidades registradas no sistema. Casos são criados automaticamente a partir de sinais fundamentais, eventos corporativos e macro."
            action={
              canCreateCase ? (
                <button
                  className="button"
                  onClick={() => setShowNewCaseForm(true)}
                  aria-label="Abrir primeiro caso de pesquisa"
                >
                  <span className="inline-flex items-center gap-6">
                    <Plus size={14} />
                    Abrir primeiro caso
                  </span>
                </button>
              ) : (
                <div className="waiting-hint">
                  <FolderOpen size={14} />
                  <span>Aguardando sinais para abertura de casos</span>
                </div>
              )
            }
          />
        </div>
      ) : (
        <>
          <section className="card card-pad section-gap">
            <div className="card-title">
              <h2>Funil de pesquisa</h2>
              <span>
                {count} caso{count !== 1 ? "s" : ""} total
              </span>
            </div>
            <div className="flex flex-col gap-8">
              <FunnelRow label="Abertos / Triados" value={openCases} total={count} tone="neutral" />
              <FunnelRow label="Em pesquisa" value={researchCases} total={count} tone="warn" />
              <FunnelRow
                label="Prontos para comitê"
                value={readyForCommittee}
                total={count}
                tone="good"
              />
            </div>
          </section>

          <section className="card card-pad section-gap" aria-live="polite">
            <div className="card-title">
              <h2>Casos de pesquisa</h2>
              <span>
                {count} registro{count !== 1 ? "s" : ""}
              </span>
            </div>
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>Título</th>
                    <th>Tipo</th>
                    <th>Prioridade</th>
                    <th>Estado</th>
                    <th>Criado por</th>
                  </tr>
                </thead>
                <tbody>
                  {cases.map((c) => (
                    <CaseCard key={c.id} caseItem={c} />
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <section className="grid grid-3 section-gap">
            <article className="card card-pad">
              <div className="card-title">
                <h2>Sinais fundamentais</h2>
                <Badge tone="good">Saudável</Badge>
              </div>
              <p className="signal-card-desc">
                Mudanças de métricas e valuation são calculadas sobre dados point-in-time.
              </p>
            </article>
            <article className="card card-pad">
              <div className="card-title">
                <h2>Eventos corporativos</h2>
                <Badge tone="warn">Atenção</Badge>
              </div>
              <p className="signal-card-desc">
                Fatos relevantes são deduplicados e classificados antes da abertura de caso.
              </p>
            </article>
            <article className="card card-pad">
              <div className="card-title">
                <h2>Macro e política</h2>
                <Badge tone="good">Saudável</Badge>
              </div>
              <p className="signal-card-desc">
                Impactos mostram mecanismo, horizonte, confidence e fontes oficiais.
              </p>
            </article>
          </section>
        </>
      )}
    </>
  );
}

export default function OpportunitiesPage() {
  return (
    <Suspense
      fallback={
        <>
          <div className="page-head">
            <div>
              <div className="eyebrow">Research funnel</div>
              <h1>Oportunidades</h1>
            </div>
          </div>
          <LoadingSkeleton lines={6} />
        </>
      }
    >
      <OpportunitiesContent />
    </Suspense>
  );
}
