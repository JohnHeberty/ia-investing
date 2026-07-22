"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import { ArrowLeft, ExternalLink, RefreshCw } from "lucide-react";
import { CandidateStatusBadge } from "@/components/candidates/candidate-status";
import { SourceCompletionForm } from "@/components/candidates/source-completion-form";
import { getCandidate, requestCandidateReanalysis, type CandidateDetail, type SourceKind } from "@/lib/candidate-api";
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

export default function CandidateDetailPage() {
  const params = useParams<{ id: string }>();
  const [detail, setDetail] = useState<CandidateDetail | null>(null);
  const [etag, setEtag] = useState("");
  const [tab, setTab] = useState<Tab>("overview");
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    setError(null);
    try {
      const result = await getCandidate(params.id);
      setDetail(result.data);
      setEtag(result.etag);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Falha ao carregar candidato");
    } finally {
      if (!silent) setLoading(false);
    }
  }, [params.id]);

  useEffect(() => { void load(); }, [load]);

  const openGaps = useMemo(() => detail?.gaps.filter((gap) => gap.status === "open") ?? [], [detail]);
  const sourceByKind = useMemo(() => new Map(detail?.sources.map((source) => [source.kind, source]) ?? []), [detail]);
  const shouldPoll = Boolean(
    detail?.sources.some((source) => source.status === "discovered")
      || detail?.analysis_runs.some((run) => run.status === "queued" || run.status === "running"),
  );

  useEffect(() => {
    if (!shouldPoll) return undefined;
    const timer = window.setInterval(() => { void load(true); }, 10_000);
    return () => window.clearInterval(timer);
  }, [load, shouldPoll]);

  async function reanalyze() {
    if (!detail) return;
    setActionLoading(true);
    setError(null);
    try {
      await requestCandidateReanalysis(detail.candidate.id, etag, false);
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Falha ao solicitar nova análise");
    } finally {
      setActionLoading(false);
    }
  }

  if (loading) return <div className="state-panel"><strong>Carregando investigação</strong>Consultando fontes, lacunas e execuções.</div>;
  if (error && !detail) return <div className="state-panel" data-state="error"><strong>Não foi possível abrir o candidato</strong>{error}</div>;
  if (!detail) return null;

  const candidate = detail.candidate;
  const readinessPercent = Math.round(Number(detail.readiness_score) * 100);
  const requiredKinds: SourceKind[] = ["cvm_profile", "cvm_filings", "b3_listing", "investor_relations", "financial_reports"];

  return (
    <>
      <header className="page-head">
        <div><Link className="breadcrumb" href="/opportunities/candidates"><ArrowLeft size={13} /> Voltar para candidatos</Link><div className="eyebrow" style={{ marginTop: 12 }}>{candidate.origin === "manual" ? "Indicação manual" : "Exploração autônoma"}</div><h1>{candidate.ticker} · {candidate.legal_name ?? "Identidade em resolução"}</h1><p className="subtitle">{candidate.rationale ?? "Investigação completa para decidir elegibilidade de carteira."}</p></div>
        <div className={styles.actions}><CandidateStatusBadge status={candidate.status} /><button className="button" onClick={() => void reanalyze()} disabled={actionLoading || detail.blocking_gap_codes.length > 0}><RefreshCw size={14} /> {actionLoading ? "Solicitando..." : "Analisar novamente"}</button></div>
      </header>

      {error && <div className={styles.error} role="alert">{error}</div>}
      {detail.blocking_gap_codes.length > 0 && <div className="state-panel" data-state="partial" style={{ marginBottom: 14 }}><strong>Análise bloqueada aguardando complemento</strong>Resolva ou forneça as fontes obrigatórias indicadas abaixo. URLs fornecidas passam por validação antes de liberar o fluxo.</div>}

      <section className="grid grid-4">
        <article className="card metric"><div className="metric-label">Prontidão</div><div className={`metric-value ${readinessPercent >= 90 ? "positive" : readinessPercent < 60 ? "warning" : ""}`}>{readinessPercent}%</div><div className="metric-note">não substitui aprovação</div></article>
        <article className="card metric"><div className="metric-label">Lacunas abertas</div><div className={`metric-value ${openGaps.length ? "warning" : "positive"}`}>{openGaps.length}</div><div className="metric-note">{detail.blocking_gap_codes.length} bloqueantes</div></article>
        <article className="card metric"><div className="metric-label">Fontes verificadas</div><div className="metric-value">{detail.sources.filter((source) => source.status === "verified").length}</div><div className="metric-note">de {detail.sources.length} cadastradas</div></article>
        <article className="card metric"><div className="metric-label">Execuções</div><div className="metric-value">{detail.analysis_runs.length}</div><div className="metric-note">última: {detail.analysis_runs[0]?.status ?? "—"}</div></article>
      </section>

      <section className="card card-pad" style={{ marginTop: 14 }}>
        <div className={styles.tabs} role="tablist">
          {(["overview", "sources", "gaps", "analysis", "timeline"] as Tab[]).map((value) => <button key={value} className={`${styles.tab} ${tab === value ? styles.tabActive : ""}`} role="tab" aria-selected={tab === value} onClick={() => setTab(value)}>{({ overview: "Visão geral", sources: "Fontes", gaps: "Lacunas", analysis: "Análises", timeline: "Timeline" } as Record<Tab, string>)[value]}</button>)}
        </div>

        {tab === "overview" && <div className={styles.layout} style={{ marginTop: 16 }}>
          <div className="card-title"><h2>Checklist de fontes bloqueantes</h2><span>liberação determinística</span></div>
          <div className={styles.statusGrid}>{requiredKinds.map((kind) => {
            const source = sourceByKind.get(kind);
            const complete = source?.status === "verified" && source.official;
            return <div key={kind} className={`${styles.statusItem} ${complete ? styles.complete : styles.blocker}`}><strong>{sourceLabels[kind]}</strong><span>{complete ? "VERIFICADA" : source ? `PENDENTE · ${source.status}` : "AUSENTE"}</span></div>;
          })}</div>
          <div className="grid grid-3">
            <div className="card card-pad"><div className="card-title"><h2>Identidade</h2></div><p className="subtitle">CNPJ: {candidate.cnpj ?? "pendente"}</p><p className="subtitle">Código CVM: {candidate.cvm_code ?? "pendente"}</p><p className="subtitle">Instrumento: {candidate.instrument_id ?? "pendente"}</p></div>
            <div className="card card-pad"><div className="card-title"><h2>Decisão</h2></div><p className="subtitle">{candidate.final_decision_reason ?? "Nenhuma decisão final emitida."}</p></div>
            <div className="card card-pad"><div className="card-title"><h2>Elegibilidade</h2></div><p className="subtitle">{candidate.approved_portfolio_eligible ? "Pode ser considerada por uma carteira compatível com o mandato." : "Não pode entrar em carteira neste estado."}</p></div>
          </div>
        </div>}

        {tab === "sources" && <div className="split">
          <div className={styles.sourceList}><div className="card-title"><h2>Fontes encontradas e fornecidas</h2><span>{detail.sources.length}</span></div>{detail.sources.length === 0 ? <div className="state-panel"><strong>Nenhuma fonte registrada</strong>Use o formulário ao lado para complementar.</div> : detail.sources.map((source) => <article key={source.id} className={styles.source}><div className={styles.sourceHeader}><strong>{sourceLabels[source.kind]}</strong><span className="badge" data-tone={source.status === "verified" ? "good" : source.status === "rejected" ? "bad" : "warn"}>{source.status}</span></div><a href={source.url} target="_blank" rel="noreferrer">{source.url} <ExternalLink size={11} /></a><div className={styles.meta}>{source.verification_method} · confiança {Math.round(Number(source.confidence) * 100)}% · {source.official ? "declarada oficial" : "não confirmada"}</div></article>)}</div>
          <aside className="card card-pad"><div className="card-title"><h2>Complementar fonte</h2><span>validação obrigatória</span></div><SourceCompletionForm candidateId={candidate.id} etag={etag} suggestedKind={openGaps.find((gap) => gap.source_kind)?.source_kind ?? null} onSaved={() => void load()} /></aside>
        </div>}

        {tab === "gaps" && <div className={styles.gapList} style={{ marginTop: 16 }}>{detail.gaps.map((gap) => <article key={gap.id} className={`${styles.gap} ${gap.status === "open" && gap.level === "blocking" ? styles.blocker : ""}`}><div className={styles.gapHeader}><strong>{gap.title}</strong><span className="badge" data-tone={gap.status === "resolved" ? "good" : gap.level === "blocking" ? "bad" : "warn"}>{gap.status} · {gap.level}</span></div><p className="subtitle">{gap.description}</p><p className="subtitle"><strong>Ação:</strong> {gap.requested_user_action}</p></article>)}</div>}

        {tab === "analysis" && <div className="table-wrap" style={{ marginTop: 16 }}><table className="table"><thead><tr><th>Execução</th><th>Gatilho</th><th>Estado</th><th>Decisão</th><th>Data de referência</th><th>Bloqueios</th></tr></thead><tbody>{detail.analysis_runs.map((run) => <tr key={run.id}><td>#{run.run_number}</td><td>{run.trigger}</td><td>{run.status}</td><td>{run.decision ?? "—"}</td><td>{new Intl.DateTimeFormat("pt-BR", { dateStyle: "short", timeStyle: "short" }).format(new Date(run.data_as_of))}</td><td>{run.blocker_codes.join(", ") || "—"}</td></tr>)}</tbody></table></div>}

        {tab === "timeline" && <div className={styles.timeline} style={{ marginTop: 16 }}>{detail.timeline.map((event) => <article key={event.id} className={styles.timelineItem}><strong>{event.event_type}</strong><p className="subtitle">{event.actor_type}: {event.actor_id}</p><div className={styles.meta}>{new Intl.DateTimeFormat("pt-BR", { dateStyle: "medium", timeStyle: "medium" }).format(new Date(event.occurred_at))} · versão {event.aggregate_version}</div></article>)}</div>}
      </section>
    </>
  );
}
