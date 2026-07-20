"use client";

import { Suspense } from "react";
import { ShieldCheck } from "lucide-react";

import { AsOfIndicator, Badge, Metric } from "@/components/domain";
import {
  DataStatePanel,
  LoadingSkeleton,
  StaleWarning,
} from "@/components/data-state-components";
import { ApprovalCard } from "@/components/decision-components";
import { useCommittee } from "@/hooks/use-committee";

function CommitteeContent() {
  const {
    decisions,
    pendingDecisions,
    approvedToday,
    totalConflicts,
    quorumRequired,
    quorumCurrent,
    isLoading,
    isError,
    dataState,
  } = useCommittee();

  if (isLoading) {
    return (
      <>
        <div className="page-head">
          <div>
            <div className="eyebrow">Committee room</div>
            <h1>Agenda de decisões</h1>
            <p className="subtitle">
              Decision packs congelados, quórum, dissenso, condições e assinaturas verificáveis.
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
            <div className="eyebrow">Committee room</div>
            <h1>Agenda de decisões</h1>
          </div>
        </div>
        <DataStatePanel
          state="error"
          title="Erro ao carregar dados do comitê"
          detail="Não foi possível acessar os decision packs. Verifique a conexão com a API."
        />
      </>
    );
  }

  const quorumMet = quorumCurrent >= quorumRequired;

  return (
    <>
      <div className="page-head">
        <div>
          <div className="eyebrow">Committee room</div>
          <h1>Agenda de decisões</h1>
          <p className="subtitle">
            Decision packs congelados, quórum, dissenso, condições e assinaturas verificáveis.
          </p>
        </div>
        <AsOfIndicator
          freshness={dataState === "stale" ? "Desatualizado" : "Atual"}
        />
      </div>

      {dataState === "stale" && (
        <div style={{ marginBottom: 14 }}>
          <StaleWarning lastUpdated={new Date().toISOString()} source="readiness/decision-packs" />
        </div>
      )}

      <section className="grid grid-4" aria-label="Indicadores do comitê">
        <Metric
          label="Na agenda"
          value={String(pendingDecisions.length)}
          note={`${pendingDecisions.length} pendente${pendingDecisions.length !== 1 ? "s" : ""}`}
        />
        <Metric
          label="Quórum"
          value={`${quorumCurrent}/${quorumRequired}`}
          note={quorumMet ? "confirmado" : "mínimo não atingido"}
          tone={quorumMet ? "positive" : "warning"}
        />
        <Metric
          label="Conflitos declarados"
          value={String(totalConflicts)}
          note={totalConflicts > 0 ? "membro impedido" : "nenhum"}
          tone={totalConflicts > 0 ? "warning" : undefined}
        />
        <Metric
          label="Decisões hoje"
          value={String(approvedToday.length)}
          note="assinadas"
        />
      </section>

      {/* Quorum status */}
      <section className="card card-pad" style={{ marginTop: 14 }}>
        <div className="card-title">
          <h2>Quórum e governança</h2>
          <Badge tone={quorumMet ? "good" : "warn"}>
            {quorumMet ? "Quórum OK" : "Quórum pendente"}
          </Badge>
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 12,
              padding: "8px 0",
              borderTop: "1px solid var(--line-soft)",
              fontSize: 12,
            }}
          >
            <ShieldCheck
              size={14}
              style={{ color: quorumMet ? "var(--accent)" : "var(--amber)" }}
            />
            <span style={{ color: "var(--muted)" }}>
              {quorumMet
                ? `Quórum de ${quorumRequired} membros confirmado (${quorumCurrent} votos).`
                : `Quórum mínimo de ${quorumRequired} membros — ${quorumCurrent} voto${quorumCurrent !== 1 ? "s" : ""} computado${quorumCurrent !== 1 ? "s" : ""}.`}
            </span>
          </div>
          {totalConflicts > 0 && (
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 12,
                padding: "8px 0",
                borderTop: "1px solid var(--line-soft)",
                fontSize: 12,
              }}
            >
              <span style={{ color: "var(--amber)" }}>⚠</span>
              <span style={{ color: "var(--muted)" }}>
                {totalConflicts} conflito{totalConflicts !== 1 ? "s" : ""} declarado{totalConflicts !== 1 ? "s" : ""} —
                membro{totalConflicts !== 1 ? "s" : ""} impedido{totalConflicts !== 1 ? "s" : ""} de votar na pauta relacionada.
              </span>
            </div>
          )}
        </div>
      </section>

      {/* Decision packs */}
      {decisions.length === 0 ? (
        <div style={{ marginTop: 14 }}>
          <DataStatePanel
            state="empty"
            title="Nenhum decision pack na agenda"
            detail="Não há decisões pendentes no comitê no momento. Decision packs são criados quando cases atingem o estágio 'ready_for_committee'."
          />
        </div>
      ) : (
        <section style={{ marginTop: 14, display: "flex", flexDirection: "column", gap: 12 }}>
          {decisions.map((d) => (
            <ApprovalCard
              key={d.id}
              title={d.title}
              description={d.description || "Decision pack congelado com tese, valuation, risco e proposta."}
              status={d.status}
              requestedBy={d.requestedBy}
              requestedAt={d.requestedAt}
              decidedBy={d.decidedBy}
              decidedAt={d.decidedAt}
              reason={d.reason}
              conditions={d.conditions}
            />
          ))}
        </section>
      )}

      {/* Governance sections */}
      <section className="grid grid-3" style={{ marginTop: 14 }}>
        <article className="card card-pad">
          <div className="card-title">
            <h2>Decision pack</h2>
            <Badge tone="good">Saudável</Badge>
          </div>
          <p style={{ color: "var(--muted)", fontSize: 12, lineHeight: 1.65 }}>
            Tese, valuation, risco, proposta e evidence hashes foram congelados na versão
            submetida.
          </p>
        </article>
        <article className="card card-pad">
          <div className="card-title">
            <h2>Votos e dissenso</h2>
            <Badge tone={totalConflicts > 0 ? "warn" : "good"}>
              {totalConflicts > 0 ? "Atenção" : "Saudável"}
            </Badge>
          </div>
          <p style={{ color: "var(--muted)", fontSize: 12, lineHeight: 1.65 }}>
            {totalConflicts > 0
              ? `${totalConflicts} voto${totalConflicts !== 1 ? "s" : ""} condicionado${totalConflicts !== 1 ? "s" : ""} requer${totalConflicts === 1 ? "" : "em"} limite adicional antes da ativação paper.`
              : "Todos os votos seguem o fluxo padrão sem conflitos declarados."}
          </p>
        </article>
        <article className="card card-pad">
          <div className="card-title">
            <h2>Four-eyes</h2>
            <Badge tone="good">Saudável</Badge>
          </div>
          <p style={{ color: "var(--muted)", fontSize: 12, lineHeight: 1.65 }}>
            Autores não podem aprovar a própria proposta e votos após encerramento são rejeitados.
          </p>
        </article>
      </section>
    </>
  );
}

export default function CommitteePage() {
  return (
    <Suspense
      fallback={
        <>
          <div className="page-head">
            <div>
              <div className="eyebrow">Committee room</div>
              <h1>Agenda de decisões</h1>
            </div>
          </div>
          <LoadingSkeleton lines={6} />
        </>
      }
    >
      <CommitteeContent />
    </Suspense>
  );
}
