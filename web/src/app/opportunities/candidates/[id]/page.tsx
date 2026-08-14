"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, RefreshCw } from "lucide-react";
import { CandidateStatusBadge } from "@/components/candidates/candidate-status";
import { CandidateTabs } from "@/components/candidates/CandidateTabs";
import {
  getCandidate,
  requestCandidateReanalysis,
  runCandidatePipeline,
  resolveCandidateGap,
  type CandidateDetail,
  type PipelineResult,
} from "@/lib/candidate-api";
import styles from "@/components/candidates/candidate-intelligence.module.css";

type Tab = "overview" | "sources" | "gaps" | "analysis" | "timeline";

export default function CandidateDetailPage() {
  const params = useParams<{ id: string }>();
  const queryClient = useQueryClient();
  const [tab, setTab] = useState<Tab>("overview");
  const [actionLoading, setActionLoading] = useState(false);
  const [pipelineLoading, setPipelineLoading] = useState(false);
  const [pipelineResult, setPipelineResult] = useState<PipelineResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [editingGapId, setEditingGapId] = useState<string | null>(null);
  const [resolveNotes, setResolveNotes] = useState("");
  const [resolving, setResolving] = useState(false);

  const candidateQuery = useQuery({
    queryKey: ["candidate", params.id],
    queryFn: async () => {
      const result = await getCandidate(params.id);
      return result;
    },
    staleTime: 30_000,
    enabled: !!params.id,
  });

  const detail = candidateQuery.data?.data ?? null;
  const etag = candidateQuery.data?.etag ?? "";

  const openGaps = useMemo(
    () => (detail?.gaps ?? []).filter((gap) => gap.status === "open") ?? [],
    [detail],
  );

  const shouldPoll = Boolean(
    (detail?.sources ?? []).some((source) => source.status === "discovered") ||
    (detail?.analysis_runs ?? []).some(
      (run) => run.status === "queued" || run.status === "running",
    ),
  );

  useEffect(() => {
    if (!shouldPoll || !params.id) return undefined;
    const timer = window.setInterval(() => {
      void candidateQuery.refetch();
    }, 10_000);
    return () => window.clearInterval(timer);
  }, [shouldPoll, params.id, candidateQuery]);

  async function reanalyze() {
    if (!detail) return;
    setActionLoading(true);
    setError(null);
    try {
      await requestCandidateReanalysis(detail.candidate.id, etag, false);
      await candidateQuery.refetch();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Falha ao solicitar nova análise");
    } finally {
      setActionLoading(false);
    }
  }

  async function runPipeline() {
    if (!detail) return;
    setPipelineLoading(true);
    setPipelineResult(null);
    setError(null);
    try {
      const result = await runCandidatePipeline(detail.candidate.id);
      setPipelineResult(result);
      await candidateQuery.refetch();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Falha ao executar pipeline");
    } finally {
      setPipelineLoading(false);
    }
  }

  async function resolveGap(gapId: string) {
    if (!detail || resolveNotes.length < 3) return;
    setResolving(true);
    setError(null);
    try {
      await resolveCandidateGap(detail.candidate.id, gapId, etag, resolveNotes);
      setEditingGapId(null);
      setResolveNotes("");
      await candidateQuery.refetch();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Falha ao resolver lacuna");
    } finally {
      setResolving(false);
    }
  }

  if (candidateQuery.isLoading)
    return (
      <div className="state-panel">
        <strong>Carregando investigação</strong>Consultando fontes, lacunas e execuções.
      </div>
    );
  if (candidateQuery.isError && !detail)
    return (
      <div className="state-panel" data-state="error">
        <strong>Não foi possível abrir o candidato</strong>
        {candidateQuery.error instanceof Error
          ? candidateQuery.error.message
          : "Erro ao carregar candidato"}
      </div>
    );
  if (!detail) return null;

  const candidate = detail.candidate;
  const readinessPercent = Math.round(Number(detail.readiness_score) * 100);

  return (
    <>
      <header className="page-head">
        <div>
          <Link className="breadcrumb" href="/opportunities/candidates">
            <ArrowLeft size={13} /> Voltar para candidatos
          </Link>
          <div className="eyebrow mt-12">
            {candidate.origin === "manual" ? "Indicação manual" : "Exploração autônoma"}
          </div>
          <h1>
            {candidate.ticker} · {candidate.legal_name ?? "Identidade em resolução"}
          </h1>
          <p className="subtitle">
            {candidate.rationale ?? "Investigação completa para decidir elegibilidade de carteira."}
          </p>
        </div>
        <div className={styles.actions}>
          <CandidateStatusBadge status={candidate.status} />
          <button
            className="button"
            onClick={() => void runPipeline()}
            disabled={pipelineLoading || actionLoading}
          >
            <RefreshCw size={14} className={pipelineLoading ? "animate-spin" : ""} />{" "}
            {pipelineLoading ? "Executando pipeline..." : "Executar Pipeline"}
          </button>
          <button
            className="button"
            onClick={() => void reanalyze()}
            disabled={actionLoading || pipelineLoading}
          >
            <RefreshCw size={14} /> {actionLoading ? "Solicitando..." : "Analisar novamente"}
          </button>
        </div>
      </header>

      {error && (
        <div className={styles.error} role="alert">
          {error}
        </div>
      )}
      {pipelineResult && (
        <div
          className="card card-pad section-gap"
          style={{
            borderLeft: `3px solid ${pipelineResult.final_status === "succeeded" ? "var(--accent)" : pipelineResult.final_status === "blocked" ? "var(--amber)" : "var(--red)"}`,
          }}
        >
          <div className="card-title">
            <h2>Resultado do Pipeline</h2>
            <span
              className="badge"
              data-tone={
                pipelineResult.final_status === "succeeded"
                  ? "good"
                  : pipelineResult.final_status === "blocked"
                    ? "warn"
                    : "bad"
              }
            >
              {pipelineResult.final_status} ({(pipelineResult.total_duration_ms / 1000).toFixed(1)}
              s)
            </span>
          </div>
          <div className="flex flex-col gap-4 mt-8">
            {pipelineResult.stages.map((s) => (
              <div key={s.stage} className="pipeline-stage">
                <span className="pipeline-stage-label">{s.stage}</span>
                <span
                  className="pipeline-stage-status"
                  style={{
                    color:
                      s.status === "blocked"
                        ? "var(--red)"
                        : s.status === "skipped"
                          ? "var(--muted)"
                          : "var(--accent)",
                  }}
                >
                  {s.status} ({s.duration_ms.toFixed(0)}ms)
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
      {detail.blocking_gap_codes.length > 0 && (
        <div className="state-panel mb-14" data-state="partial">
          <strong>Análise bloqueada aguardando complemento</strong>Resolva ou forneça as fontes
          obrigatórias indicadas abaixo. URLs fornecidas passam por validação antes de liberar o
          fluxo.
        </div>
      )}

      <section className="grid grid-4 section-gap" aria-live="polite">
        <article className="card metric">
          <div className="metric-label">Prontidão</div>
          <div
            className={`metric-value ${readinessPercent >= 90 ? "positive" : readinessPercent < 60 ? "warning" : ""}`}
          >
            {readinessPercent}%
          </div>
          <div className="metric-note">não substitui aprovação</div>
        </article>
        <article className="card metric">
          <div className="metric-label">Lacunas abertas</div>
          <div className={`metric-value ${openGaps.length ? "warning" : "positive"}`}>
            {openGaps.length}
          </div>
          <div className="metric-note">{(detail.blocking_gap_codes ?? []).length} bloqueantes</div>
        </article>
        <article className="card metric">
          <div className="metric-label">Fontes verificadas</div>
          <div className="metric-value">
            {(detail.sources ?? []).filter((source) => source.status === "verified").length}
          </div>
          <div className="metric-note">de {(detail.sources ?? []).length} cadastradas</div>
        </article>
        <article className="card metric">
          <div className="metric-label">Execuções</div>
          <div className="metric-value">{(detail.analysis_runs ?? []).length}</div>
          <div className="metric-note">
            última: {(detail.analysis_runs ?? [])[0]?.status ?? "—"}
          </div>
        </article>
      </section>

      <CandidateTabs
        detail={detail}
        etag={etag}
        tab={tab}
        setTab={setTab}
        editingGapId={editingGapId}
        resolveNotes={resolveNotes}
        resolving={resolving}
        onResolveGap={resolveGap}
        onEditGap={(gapId) => {
          setEditingGapId(gapId);
          setResolveNotes("");
        }}
        onCancelEdit={() => {
          setEditingGapId(null);
          setResolveNotes("");
        }}
        onNotesChange={setResolveNotes}
        load={() => candidateQuery.refetch().then(() => undefined)}
      />
    </>
  );
}
