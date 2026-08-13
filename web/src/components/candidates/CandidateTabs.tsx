"use client";

import { ExternalLink } from "lucide-react";
import { SourceCompletionForm } from "@/components/candidates/source-completion-form";
import { GapCard } from "@/components/candidates/GapCard";
import type { CandidateDetail, SourceKind } from "@/lib/candidate-api";
import styles from "@/components/candidates/candidate-intelligence.module.css";

type Tab = "overview" | "sources" | "gaps" | "analysis" | "timeline";

const sourceLabels: Record<SourceKind, string> = {
  company_website: "Site oficial",
  investor_relations: "Relações com investidores",
  financial_reports: "Relatórios e resultados",
  cvm_profile: "Cadastro CVM",
  cvm_filings: "Documentos CVM",
  b3_listing: "Listagem B3",
  governance: "Governança",
  newsroom: "Notícias oficiais",
  regulator: "Regulador",
  market_data: "Dados de mercado",
};

const TAB_LABELS: Record<Tab, string> = {
  overview: "Visão geral",
  sources: "Fontes",
  gaps: "Lacunas",
  analysis: "Análises",
  timeline: "Timeline",
};

const REQUIRED_KINDS: SourceKind[] = [
  "cvm_profile",
  "cvm_filings",
  "b3_listing",
  "investor_relations",
  "financial_reports",
];

function OverviewPanel({
  candidate,
  sourceByKind,
}: {
  candidate: CandidateDetail["candidate"];
  sourceByKind: Map<SourceKind, CandidateDetail["sources"][number]>;
}) {
  return (
    <div
      id="panel-overview"
      role="tabpanel"
      aria-labelledby="tab-overview"
      className={`${styles.layout} tab-panel`}
    >
      <div className="card-title">
        <h2>Checklist de fontes bloqueantes</h2>
        <span>liberação determinística</span>
      </div>
      <div className={styles.statusGrid}>
        {REQUIRED_KINDS.map((kind) => {
          const source = sourceByKind.get(kind);
          const complete = source?.status === "verified" && source.official;
          return (
            <div
              key={kind}
              className={`${styles.statusItem} ${complete ? styles.complete : styles.blocker}`}
            >
              <strong>{sourceLabels[kind]}</strong>
              <span>
                {complete ? "VERIFICADA" : source ? `PENDENTE · ${source.status}` : "AUSENTE"}
              </span>
            </div>
          );
        })}
      </div>
      <div className="grid grid-3">
        <div className="card card-pad">
          <div className="card-title">
            <h2>Identidade</h2>
          </div>
          <p className="subtitle">CNPJ: {candidate.cnpj ?? "pendente"}</p>
          <p className="subtitle">Código CVM: {candidate.cvm_code ?? "pendente"}</p>
          <p className="subtitle">Instrumento: {candidate.instrument_id ?? "pendente"}</p>
        </div>
        <div className="card card-pad">
          <div className="card-title">
            <h2>Decisão</h2>
          </div>
          <p className="subtitle">
            {candidate.final_decision_reason ?? "Nenhuma decisão final emitida."}
          </p>
        </div>
        <div className="card card-pad">
          <div className="card-title">
            <h2>Elegibilidade</h2>
          </div>
          <p className="subtitle">
            {candidate.approved_portfolio_eligible
              ? "Pode ser considerada por uma carteira compatível com o mandato."
              : "Não pode entrar em carteira neste estado."}
          </p>
        </div>
      </div>
    </div>
  );
}

function SourcesPanel({
  detail,
  candidate,
  openGaps,
  etag,
  load,
}: {
  detail: CandidateDetail;
  candidate: CandidateDetail["candidate"];
  openGaps: CandidateDetail["gaps"];
  etag: string;
  load: () => Promise<void>;
}) {
  return (
    <div id="panel-sources" role="tabpanel" aria-labelledby="tab-sources" className="split">
      <div className={styles.sourceList}>
        <div className="card-title">
          <h2>Fontes encontradas e fornecidas</h2>
          <span>{detail.sources.length}</span>
        </div>
        {detail.sources.length === 0 ? (
          <div className="state-panel">
            <strong>Nenhuma fonte registrada</strong>Use o formulário ao lado para complementar.
          </div>
        ) : (
          detail.sources.map((source) => (
            <article key={source.id} className={styles.source}>
              <div className={styles.sourceHeader}>
                <strong>{sourceLabels[source.kind]}</strong>
                <span
                  className="badge"
                  data-tone={
                    source.status === "verified"
                      ? "good"
                      : source.status === "rejected"
                        ? "bad"
                        : "warn"
                  }
                >
                  {source.status}
                </span>
              </div>
              <a href={source.url} target="_blank" rel="noreferrer">
                {source.url} <ExternalLink size={11} />
              </a>
              <div className={styles.meta}>
                {source.verification_method} · confiança{" "}
                {Math.round(Number(source.confidence) * 100)}% ·{" "}
                {source.official ? "declarada oficial" : "não confirmada"}
              </div>
            </article>
          ))
        )}
      </div>
      <aside className="card card-pad">
        <div className="card-title">
          <h2>Complementar fonte</h2>
          <span>validação obrigatória</span>
        </div>
        <SourceCompletionForm
          candidateId={candidate.id}
          etag={etag}
          suggestedKind={
            (openGaps.find((gap) => gap.source_kind)?.source_kind as SourceKind) ?? null
          }
          onSaved={() => void load()}
        />
      </aside>
    </div>
  );
}

function GapsPanel({
  detail,
  editingGapId,
  resolveNotes,
  resolving,
  onResolveGap,
  onEditGap,
  onCancelEdit,
  onNotesChange,
}: {
  detail: CandidateDetail;
  editingGapId: string | null;
  resolveNotes: string;
  resolving: boolean;
  onResolveGap: (gapId: string) => void;
  onEditGap: (gapId: string) => void;
  onCancelEdit: () => void;
  onNotesChange: (value: string) => void;
}) {
  return (
    <div
      id="panel-gaps"
      role="tabpanel"
      aria-labelledby="tab-gaps"
      className={`${styles.gapList} tab-panel`}
    >
      {detail.gaps.map((gap) => (
        <GapCard
          key={gap.id}
          gap={gap}
          editingGapId={editingGapId}
          resolveNotes={resolveNotes}
          resolving={resolving}
          onResolveGap={onResolveGap}
          onEdit={onEditGap}
          onCancelEdit={onCancelEdit}
          onNotesChange={onNotesChange}
        />
      ))}
    </div>
  );
}

function AnalysisPanel({ runs }: { runs: CandidateDetail["analysis_runs"] }) {
  return (
    <div
      id="panel-analysis"
      role="tabpanel"
      aria-labelledby="tab-analysis"
      className="table-wrap tab-panel"
    >
      <table className="table">
        <thead>
          <tr>
            <th>Execução</th>
            <th>Gatilho</th>
            <th>Estado</th>
            <th>Decisão</th>
            <th>Data de referência</th>
            <th>Bloqueios</th>
          </tr>
        </thead>
        <tbody>
          {runs.map((run) => (
            <tr key={run.id}>
              <td>#{run.run_number}</td>
              <td>{run.trigger}</td>
              <td>{run.status}</td>
              <td>{run.decision ?? "—"}</td>
              <td>
                {new Intl.DateTimeFormat("pt-BR", {
                  dateStyle: "short",
                  timeStyle: "short",
                }).format(new Date(run.data_as_of))}
              </td>
              <td>{run.blocker_codes.join(", ") || "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function TimelinePanel({ events }: { events: CandidateDetail["timeline"] }) {
  return (
    <div
      id="panel-timeline"
      role="tabpanel"
      aria-labelledby="tab-timeline"
      className={`${styles.timeline} tab-panel`}
    >
      {events.map((event) => (
        <article key={event.id} className={styles.timelineItem}>
          <strong>{event.event_type}</strong>
          <p className="subtitle">
            {event.actor_type}: {event.actor_id}
          </p>
          <div className={styles.meta}>
            {new Intl.DateTimeFormat("pt-BR", { dateStyle: "medium", timeStyle: "medium" }).format(
              new Date(event.occurred_at),
            )}{" "}
            · versão {event.aggregate_version}
          </div>
        </article>
      ))}
    </div>
  );
}

export function CandidateTabs({
  detail,
  etag,
  tab,
  setTab,
  editingGapId,
  resolveNotes,
  resolving,
  onResolveGap,
  onEditGap,
  onCancelEdit,
  onNotesChange,
  load,
}: {
  detail: CandidateDetail;
  etag: string;
  tab: Tab;
  setTab: (tab: Tab) => void;
  editingGapId: string | null;
  resolveNotes: string;
  resolving: boolean;
  onResolveGap: (gapId: string) => void;
  onEditGap: (gapId: string) => void;
  onCancelEdit: () => void;
  onNotesChange: (value: string) => void;
  load: () => Promise<void>;
}) {
  const candidate = detail.candidate;
  const openGaps = (detail.gaps ?? []).filter((gap) => gap.status === "open");
  const sourceByKind = new Map((detail.sources ?? []).map((source) => [source.kind, source]));

  const handleKeyDown = (e: React.KeyboardEvent, value: Tab) => {
    const tabs: Tab[] = ["overview", "sources", "gaps", "analysis", "timeline"];
    const idx = tabs.indexOf(value);
    if (e.key === "ArrowRight") {
      e.preventDefault();
      setTab(tabs[(idx + 1) % tabs.length]);
    } else if (e.key === "ArrowLeft") {
      e.preventDefault();
      setTab(tabs[(idx - 1 + tabs.length) % tabs.length]);
    }
  };

  return (
    <section className="card card-pad section-gap" aria-live="polite">
      <div className={styles.tabs} role="tablist" aria-label="Detalhes do candidato">
        {(Object.keys(TAB_LABELS) as Tab[]).map((value) => (
          <button
            key={value}
            id={`tab-${value}`}
            className={`${styles.tab} ${tab === value ? styles.tabActive : ""}`}
            role="tab"
            aria-selected={tab === value}
            aria-controls={`panel-${value}`}
            onClick={() => setTab(value)}
            onKeyDown={(e) => handleKeyDown(e, value)}
          >
            {TAB_LABELS[value]}
          </button>
        ))}
      </div>

      {tab === "overview" && <OverviewPanel candidate={candidate} sourceByKind={sourceByKind} />}
      {tab === "sources" && (
        <SourcesPanel
          detail={detail}
          candidate={candidate}
          openGaps={openGaps}
          etag={etag}
          load={load}
        />
      )}
      {tab === "gaps" && (
        <GapsPanel
          detail={detail}
          editingGapId={editingGapId}
          resolveNotes={resolveNotes}
          resolving={resolving}
          onResolveGap={onResolveGap}
          onEditGap={onEditGap}
          onCancelEdit={onCancelEdit}
          onNotesChange={onNotesChange}
        />
      )}
      {tab === "analysis" && <AnalysisPanel runs={detail.analysis_runs} />}
      {tab === "timeline" && <TimelinePanel events={detail.timeline} />}
    </section>
  );
}
