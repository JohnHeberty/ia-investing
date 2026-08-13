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
    <div className="grid gap-16 p-24">
      <div className="skeleton-bar h-32 w-256" />
      <div className="skeleton-bar h-16 w-384" />
      <div className="grid gap-16" style={{ gridTemplateColumns: "1fr 1fr" }}>
        <div className="skeleton-panel h-192" />
        <div className="skeleton-panel h-192" />
      </div>
    </div>
  );
}

function ErrorState({ message }: { message: string }) {
  return (
    <main>
      <h1 className="text-24 fw-600">Rebalanceamento</h1>
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
    return (
      <ErrorState
        message={driftQuery.error?.message ?? proposalsQuery.error?.message ?? "Erro desconhecido"}
      />
    );
  }

  const isLoading =
    (driftQuery.isPending && driftQuery.fetchStatus !== "idle") ||
    (proposalsQuery.isPending && proposalsQuery.fetchStatus !== "idle");

  if (selectedProposalId && proposalDetailQuery.data) {
    return (
      <main className="flex flex-col gap-24">
        <header className="page-head">
          <div>
            <div className="eyebrow">Portfolio Intelligence</div>
            <h1>Rebalanceamento</h1>
          </div>
        </header>
        <ProposalDetail
          proposal={proposalDetailQuery.data}
          onBack={() => setSelectedProposalId(null)}
        />
      </main>
    );
  }

  return (
    <main className="flex flex-col gap-24">
      <header className="page-head">
        <div>
          <div className="eyebrow">Portfolio Intelligence</div>
          <h1>Rebalanceamento de carteiras</h1>
          <p className="subtitle">
            Monitore desvios de alocação, proponha e execute rebalanceamentos, e acompanhe o
            histórico.
          </p>
        </div>
      </header>

      <div className="flex flex-wrap items-center gap-16">
        <select
          className="select-styled"
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
            <option key={p.id} value={p.id}>
              {p.name}
            </option>
          ))}
        </select>
        <button onClick={() => setShowProposeForm(true)} className="button">
          Propor rebalanceamento
        </button>
      </div>

      {isLoading && <LoadingSkeleton />}

      {!isLoading && showProposeForm && (
        <ProposeForm portfolioId={effectiveId} onClose={() => setShowProposeForm(false)} />
      )}

      {!isLoading && driftQuery.data && (
        <section className="card card-pad" aria-live="polite">
          <div className="card-title">
            <h2>Desvios atuais vs. alvo</h2>
          </div>
          <div className="drift-info">
            <div>
              <span className="text-muted">Desvio máximo: </span>
              <span className="mono">{pct(driftQuery.data.max_drift)}</span>
            </div>
            <div>
              <span className="text-muted">Desvio total: </span>
              <span className="mono">{pct(driftQuery.data.total_drift)}</span>
            </div>
          </div>
          <DriftTable items={driftQuery.data.items} />
        </section>
      )}

      {!isLoading && proposalsQuery.data && (
        <section className="card card-pad" aria-live="polite">
          <div className="card-title">
            <h2>Propostas</h2>
          </div>
          {proposalsQuery.data.length === 0 ? (
            <p className="proposal-empty">
              Nenhuma proposta de rebalanceamento para esta carteira.
            </p>
          ) : (
            <div className="flex flex-col gap-8">
              {proposalsQuery.data.map((p) => (
                <button
                  key={p.id}
                  onClick={() => setSelectedProposalId(p.id)}
                  className="event proposal-btn"
                >
                  <div>
                    <div className="proposal-title">Proposta {p.id.slice(0, 8)}</div>
                    <div className="proposal-meta">
                      {p.rationale.slice(0, 100)}
                      {p.rationale.length > 100 ? "..." : ""}
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
          <div className="card-title">
            <h2>Histórico de rebalanceamentos</h2>
          </div>
          <ProposalTimeline items={proposalsQuery.data ?? []} />
        </section>
      )}
    </main>
  );
}
