"use client";

import { useState } from "react";

import {
  useDriftSummary,
  useRebalanceProposal,
  useRebalanceProposals,
} from "@/hooks/use-rebalance";
import { usePortfoliosList } from "@/hooks/use-portfolios";

import { pct } from "@/components/rebalance/shared";
import { ProposeForm } from "@/components/rebalance/ProposeForm";
import { DriftTable } from "@/components/rebalance/DriftTable";
import { ProposalDetail } from "@/components/rebalance/ProposalDetail";
import { ProposalTimeline } from "@/components/rebalance/ProposalTimeline";
import { StatusBadge } from "@/components/rebalance/shared";

function LoadingSkeleton() {
  return (
    <div style={{ display: "grid", gap: 16, padding: 24 }}>
      <div style={{ height: 32, width: 256, borderRadius: 4, background: "var(--surface-3)", animation: "pulse 2s infinite" }} />
      <div style={{ height: 16, width: 384, borderRadius: 4, background: "var(--surface-3)", animation: "pulse 2s infinite" }} />
      <div style={{ display: "grid", gap: 16, gridTemplateColumns: "1fr 1fr" }}>
        <div style={{ height: 192, borderRadius: 10, border: "1px solid var(--line)", background: "var(--surface)" }} />
        <div style={{ height: 192, borderRadius: 10, border: "1px solid var(--line)", background: "var(--surface)" }} />
      </div>
    </div>
  );
}

function ErrorState({ message }: { message: string }) {
  return (
    <main>
      <h1 style={{ fontSize: 24, fontWeight: 600, color: "var(--text)" }}>Rebalanceamento</h1>
      <div className="state-panel section-gap" data-state="error" role="alert">
        <strong>Erro</strong>
        {message}
      </div>
    </main>
  );
}

export default function RebalancePage() {
  const { portfolios, isLoading: portfoliosLoading } = usePortfoliosList();
  const [selectedPortfolioId, setSelectedPortfolioId] = useState<string>("");
  const [showProposeForm, setShowProposeForm] = useState(false);
  const [selectedProposalId, setSelectedProposalId] = useState<string | null>(null);

  const effectiveId = selectedPortfolioId || portfolios[0]?.id || "";

  const driftQuery = useDriftSummary(effectiveId);
  const proposalsQuery = useRebalanceProposals(effectiveId);
  const proposalDetailQuery = useRebalanceProposal(selectedProposalId ?? undefined);

  if (driftQuery.isError && proposalsQuery.isError) {
    return <ErrorState message={driftQuery.error?.message ?? proposalsQuery.error?.message ?? "Erro desconhecido"} />;
  }

  const isLoading =
    (driftQuery.isPending && driftQuery.fetchStatus !== "idle") ||
    (proposalsQuery.isPending && proposalsQuery.fetchStatus !== "idle");

  if (selectedProposalId && proposalDetailQuery.data) {
    return (
      <main style={{ display: "flex", flexDirection: "column", gap: 24 }}>
        <header className="page-head">
          <div>
            <div className="eyebrow">Portfolio Intelligence</div>
            <h1>Rebalanceamento</h1>
          </div>
        </header>
        <ProposalDetail proposal={proposalDetailQuery.data} onBack={() => setSelectedProposalId(null)} />
      </main>
    );
  }

  return (
    <main style={{ display: "flex", flexDirection: "column", gap: 24 }}>
      <header className="page-head">
        <div>
          <div className="eyebrow">Portfolio Intelligence</div>
          <h1>Rebalanceamento de carteiras</h1>
          <p className="subtitle">
            Monitore desvios de alocação, proponha e execute rebalanceamentos, e acompanhe o histórico.
          </p>
        </div>
      </header>

      <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 16 }}>
        <select
          style={{
            borderRadius: 8,
            border: "1px solid var(--line)",
            background: "var(--surface)",
            padding: "8px 16px",
            fontSize: 14,
            color: "var(--text)",
          }}
          value={effectiveId}
          onChange={(e) => {
            setSelectedPortfolioId(e.target.value);
            setSelectedProposalId(null);
            setShowProposeForm(false);
          }}
        >
          {portfoliosLoading && <option>Carregando...</option>}
          {!portfoliosLoading && portfolios.length === 0 && <option>Nenhuma carteira</option>}
          {portfolios.map((p) => (
            <option key={p.id} value={p.id}>{p.name}</option>
          ))}
        </select>
        <button
          onClick={() => setShowProposeForm(true)}
          className="button"
        >
          Propor rebalanceamento
        </button>
      </div>

      {isLoading && <LoadingSkeleton />}

      {!isLoading && showProposeForm && (
        <ProposeForm portfolioId={effectiveId} onClose={() => setShowProposeForm(false)} />
      )}

      {!isLoading && driftQuery.data && (
        <section className="card card-pad" aria-live="polite">
          <div className="card-title"><h2>Desvios atuais vs. alvo</h2></div>
          <div style={{ marginBottom: 16, display: "flex", gap: 24, fontSize: 14 }}>
            <div>
              <span style={{ color: "var(--muted)" }}>Desvio máximo: </span>
              <span style={{ fontFamily: "var(--font-mono)", color: "var(--text)" }}>{pct(driftQuery.data.max_drift)}</span>
            </div>
            <div>
              <span style={{ color: "var(--muted)" }}>Desvio total: </span>
              <span style={{ fontFamily: "var(--font-mono)", color: "var(--text)" }}>{pct(driftQuery.data.total_drift)}</span>
            </div>
          </div>
          <DriftTable items={driftQuery.data.items} />
        </section>
      )}

      {!isLoading && proposalsQuery.data && (
        <section className="card card-pad" aria-live="polite">
          <div className="card-title"><h2>Propostas</h2></div>
          {proposalsQuery.data.length === 0 ? (
            <p style={{ fontSize: 14, color: "var(--muted)" }}>Nenhuma proposta de rebalanceamento para esta carteira.</p>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {proposalsQuery.data.map((p) => (
                <button
                  key={p.id}
                  onClick={() => setSelectedProposalId(p.id)}
                  className="event"
                  style={{
                    display: "flex",
                    width: "100%",
                    alignItems: "center",
                    justifyContent: "space-between",
                    textAlign: "left",
                    background: "none",
                    cursor: "pointer",
                    color: "inherit",
                  }}
                >
                  <div>
                    <div style={{ fontSize: 14, fontWeight: 500, color: "var(--text)" }}>
                      Proposta {p.id.slice(0, 8)}
                    </div>
                    <div style={{ marginTop: 4, fontSize: 12, color: "var(--muted-2)" }}>
                      {p.rationale.slice(0, 100)}{p.rationale.length > 100 ? "..." : ""}
                    </div>
                  </div>
                  <StatusBadge status={p.status} />
                </button>
              ))}
            </div>
          )}
        </section>
      )}

      {!isLoading && (
        <section className="card card-pad">
          <div className="card-title"><h2>Histórico de rebalanceamentos</h2></div>
          <ProposalTimeline items={proposalsQuery.data ?? []} />
        </section>
      )}
    </main>
  );
}
