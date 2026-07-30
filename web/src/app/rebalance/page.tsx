"use client";

import { useState } from "react";

import {
  useApproveRebalance,
  useCancelRebalance,
  useCompleteRebalance,
  useDriftSummary,
  useExecuteTradeStep,
  useProposeRebalance,
  useRebalanceProposal,
  useRebalanceProposals,
} from "@/hooks/use-rebalance";
import type {
  DriftItem,
  RebalanceProposal,
  RebalanceTrade,
} from "@/hooks/use-rebalance";
import { usePortfoliosList } from "@/hooks/use-portfolios";

const percent = new Intl.NumberFormat("pt-BR", {
  style: "percent",
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
});
const money = new Intl.NumberFormat("pt-BR", {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 0,
});
const dateTime = new Intl.DateTimeFormat("pt-BR", {
  dateStyle: "short",
  timeStyle: "short",
});

function pct(value: number): string {
  return percent.format(value / 100);
}

function DriftBadge({ severity }: { severity: DriftItem["severity"] }) {
  const tone = severity === "green" ? "good" : severity === "yellow" ? "warn" : "bad";
  return (
    <span className="badge" data-tone={tone}>
      {severity === "green" ? "<1%" : severity === "yellow" ? "1-3%" : ">3%"}
    </span>
  );
}

function SideBadge({ side }: { side: "buy" | "sell" }) {
  return (
    <span className="badge" data-tone={side === "buy" ? "good" : "bad"}>
      {side.toUpperCase()}
    </span>
  );
}

function StatusBadge({ status }: { status: string }) {
  const toneMap: Record<string, string> = {
    draft: "neutral",
    approved: "info",
    in_progress: "warn",
    completed: "good",
    cancelled: "bad",
  };
  return (
    <span className="badge" data-tone={toneMap[status] ?? "neutral"}>
      {status.replaceAll("_", " ")}
    </span>
  );
}

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
      <div className="state-panel" data-state="error" role="alert" style={{ marginTop: 24 }}>
        <strong>Erro</strong>
        {message}
      </div>
    </main>
  );
}

function ProposeForm({
  portfolioId,
  onClose,
}: {
  portfolioId: string;
  onClose: () => void;
}) {
  const propose = useProposeRebalance();
  const [targets, setTargets] = useState("");
  const [rationale, setRationale] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    let parsed: Record<string, number>;
    try {
      parsed = JSON.parse(targets) as Record<string, number>;
    } catch {
      return;
    }
    propose.mutate(
      { portfolioId, targetAllocations: parsed, rationale },
      { onSuccess: () => onClose() },
    );
  };

  return (
    <form onSubmit={handleSubmit} className="card card-pad" style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <div className="card-title"><h3>Nova proposta de rebalanceamento</h3></div>
      <div>
        <label style={{ display: "block", fontSize: 14, color: "var(--muted)" }}>Target allocations (JSON)</label>
        <textarea
          style={{
            marginTop: 4,
            width: "100%",
            borderRadius: 8,
            border: "1px solid var(--line)",
            background: "var(--surface-2)",
            padding: 8,
            fontFamily: "var(--font-mono)",
            fontSize: 14,
            color: "var(--text)",
            resize: "vertical",
          }}
          rows={5}
          placeholder='{"AAPL": 0.25, "GOOGL": 0.15, "MSFT": 0.20}'
          value={targets}
          onChange={(e) => setTargets(e.target.value)}
        />
      </div>
      <div>
        <label style={{ display: "block", fontSize: 14, color: "var(--muted)" }}>Rationale</label>
        <textarea
          style={{
            marginTop: 4,
            width: "100%",
            borderRadius: 8,
            border: "1px solid var(--line)",
            background: "var(--surface-2)",
            padding: 8,
            fontSize: 14,
            color: "var(--text)",
            resize: "vertical",
          }}
          rows={3}
          value={rationale}
          onChange={(e) => setRationale(e.target.value)}
        />
      </div>
      <div style={{ display: "flex", gap: 12 }}>
        <button
          type="submit"
          className="button"
          disabled={propose.isPending || !targets || !rationale}
          style={{ opacity: propose.isPending || !targets || !rationale ? 0.5 : 1 }}
        >
          {propose.isPending ? "Criando..." : "Propor rebalanceamento"}
        </button>
        <button type="button" className="button secondary" onClick={onClose}>
          Cancelar
        </button>
      </div>
      {propose.isError && (
        <p style={{ fontSize: 14, color: "var(--red)" }}>Erro: {propose.error.message}</p>
      )}
    </form>
  );
}

function DriftTable({ items }: { items: DriftItem[] }) {
  if (items.length === 0) {
    return <p style={{ fontSize: 14, color: "var(--muted)" }}>Nenhum desvio detectado.</p>;
  }
  return (
    <table className="table">
      <thead>
        <tr>
          <th>Ticker</th>
          <th>Atual</th>
          <th>Target</th>
          <th>Desvio</th>
          <th>Severidade</th>
        </tr>
      </thead>
      <tbody>
        {items.map((item) => (
          <tr key={item.ticker}>
            <td style={{ fontWeight: 500, color: "var(--text)" }}>{item.ticker}</td>
            <td>{pct(item.current_weight)}</td>
            <td>{pct(item.target_weight)}</td>
            <td style={{ fontFamily: "var(--font-mono)" }}>{pct(item.drift)}</td>
            <td><DriftBadge severity={item.severity} /></td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function TradesTable({
  trades,
  selected,
  onToggle,
}: {
  trades: RebalanceTrade[];
  selected: Set<string>;
  onToggle: (id: string) => void;
}) {
  if (trades.length === 0) {
    return <p style={{ fontSize: 14, color: "var(--muted)" }}>Nenhuma trade calculada.</p>;
  }
  return (
    <table className="table">
      <thead>
        <tr>
          <th style={{ width: 40 }} />
          <th>Ordem</th>
          <th>Ticker</th>
          <th>Side</th>
          <th>Atual → Target</th>
          <th>Delta</th>
          <th>Valor estimado</th>
          <th>Status</th>
        </tr>
      </thead>
      <tbody>
        {trades.map((trade) => (
          <tr key={trade.id}>
            <td>
              {trade.status === "pending" && (
                <input
                  type="checkbox"
                  checked={selected.has(trade.id)}
                  onChange={() => onToggle(trade.id)}
                  style={{ width: 16, height: 16, accentColor: "var(--accent)" }}
                />
              )}
            </td>
            <td style={{ textAlign: "center", fontSize: 12, color: "var(--muted-2)" }}>{trade.execution_order}</td>
            <td style={{ fontWeight: 500, color: "var(--text)" }}>{trade.ticker}</td>
            <td><SideBadge side={trade.side} /></td>
            <td>
              {pct(trade.current_weight)} → {pct(trade.target_weight)}
            </td>
            <td style={{ fontFamily: "var(--font-mono)", color: trade.delta > 0 ? "var(--accent)" : "var(--red)" }}>
              {trade.delta > 0 ? "+" : ""}{pct(trade.delta)}
            </td>
            <td style={{ fontFamily: "var(--font-mono)", color: "var(--text)" }}>{money.format(trade.estimated_value)}</td>
            <td><StatusBadge status={trade.status} /></td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function ProposalDetail({
  proposal,
  onBack,
}: {
  proposal: RebalanceProposal;
  onBack: () => void;
}) {
  const approve = useApproveRebalance();
  const execute = useExecuteTradeStep();
  const complete = useCompleteRebalance();
  const cancel = useCancelRebalance();
  const [selectedTrades, setSelectedTrades] = useState<Set<string>>(new Set());

  const toggleTrade = (id: string) => {
    const next = new Set(selectedTrades);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    setSelectedTrades(next);
  };

  const canApprove = proposal.status === "draft";
  const canExecute = proposal.status === "approved" || proposal.status === "in_progress";
  const canComplete = proposal.status === "in_progress" || proposal.status === "approved";
  const canCancel = !["completed", "cancelled"].includes(proposal.status);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <button
          onClick={onBack}
          style={{ fontSize: 14, color: "var(--blue)", background: "none", border: "none", cursor: "pointer" }}
        >
          &larr; Voltar para lista
        </button>
        <StatusBadge status={proposal.status} />
      </div>

      <div className="card card-pad">
        <div className="card-title">
          <h2>Proposta {proposal.id.slice(0, 8)}</h2>
        </div>
        <p style={{ marginTop: 8, fontSize: 14, color: "var(--muted)" }}>{proposal.rationale}</p>
        <div style={{ marginTop: 16, display: "flex", flexWrap: "wrap", gap: 16, fontSize: 12, color: "var(--muted-2)" }}>
          <span>Criada por: {proposal.created_by}</span>
          <span>Em: {dateTime.format(new Date(proposal.created_at))}</span>
          {proposal.approved_by && <span>Aprovada por: {proposal.approved_by}</span>}
        </div>
      </div>

      {proposal.drift_analysis && (
        <section className="card card-pad">
          <div className="card-title"><h3>Análise de desvio</h3></div>
          <div style={{ marginBottom: 16, display: "flex", gap: 24, fontSize: 14 }}>
            <div>
              <span style={{ color: "var(--muted)" }}>Desvio máximo: </span>
              <span style={{ fontFamily: "var(--font-mono)", color: "var(--text)" }}>{pct(proposal.drift_analysis.max_drift)}</span>
            </div>
            <div>
              <span style={{ color: "var(--muted)" }}>Desvio total: </span>
              <span style={{ fontFamily: "var(--font-mono)", color: "var(--text)" }}>{pct(proposal.drift_analysis.total_drift)}</span>
            </div>
          </div>
          <DriftTable items={proposal.drift_analysis.items} />
        </section>
      )}

      <section className="card card-pad">
        <div className="card-title"><h3>Trades</h3></div>
        <TradesTable trades={proposal.trades} selected={selectedTrades} onToggle={toggleTrade} />
      </section>

      {proposal.execution_progress && (
        <section className="card card-pad">
          <div className="card-title"><h3>Progresso</h3></div>
          <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
            <div style={{ height: 8, flex: 1, overflow: "hidden", borderRadius: 999, background: "var(--surface-3)" }}>
              <div
                style={{ height: "100%", borderRadius: 999, background: "var(--accent)", transition: "all 0.3s", width: `${proposal.execution_progress.percent_complete}%` }}
              />
            </div>
            <span style={{ fontSize: 14, color: "var(--muted)" }}>
              {proposal.execution_progress.executed}/{proposal.execution_progress.total}
            </span>
          </div>
          <div style={{ marginTop: 8, display: "flex", gap: 16, fontSize: 12, color: "var(--muted-2)" }}>
            <span>{proposal.execution_progress.executed} executadas</span>
            <span>{proposal.execution_progress.skipped} puladas</span>
            <span>{proposal.execution_progress.failed} falhas</span>
          </div>
        </section>
      )}

      <div style={{ display: "flex", flexWrap: "wrap", gap: 12 }}>
        {canApprove && (
          <button
            onClick={() => approve.mutate({ proposalId: proposal.id })}
            disabled={approve.isPending}
            className="button"
            style={{ background: "var(--blue)", color: "#fff", opacity: approve.isPending ? 0.5 : 1 }}
          >
            {approve.isPending ? "Aprovando..." : "Aprovar proposta"}
          </button>
        )}
        {canExecute && selectedTrades.size > 0 && (
          <button
            onClick={() =>
              execute.mutate({
                proposalId: proposal.id,
                tradeIds: Array.from(selectedTrades),
              })
            }
            disabled={execute.isPending}
            className="button"
            style={{ opacity: execute.isPending ? 0.5 : 1 }}
          >
            {execute.isPending ? "Executando..." : `Executar ${selectedTrades.size} trade(s)`}
          </button>
        )}
        {canComplete && (
          <button
            onClick={() => complete.mutate({ proposalId: proposal.id })}
            disabled={complete.isPending}
            className="button secondary"
            style={{ borderColor: "var(--accent)", color: "var(--accent)", opacity: complete.isPending ? 0.5 : 1 }}
          >
            {complete.isPending ? "Finalizando..." : "Completar rebalanceamento"}
          </button>
        )}
        {canCancel && (
          <button
            onClick={() => cancel.mutate({ proposalId: proposal.id, reason: "Cancelado pelo operador" })}
            disabled={cancel.isPending}
            className="button secondary"
            style={{ borderColor: "var(--red)", color: "var(--red)", opacity: cancel.isPending ? 0.5 : 1 }}
          >
            {cancel.isPending ? "Cancelando..." : "Cancelar proposta"}
          </button>
        )}
      </div>

      {approve.isError && (
        <p style={{ fontSize: 14, color: "var(--red)" }}>Erro ao aprovar: {approve.error.message}</p>
      )}
      {execute.isError && (
        <p style={{ fontSize: 14, color: "var(--red)" }}>Erro ao executar: {execute.error.message}</p>
      )}
      {complete.isError && (
        <p style={{ fontSize: 14, color: "var(--red)" }}>Erro ao finalizar: {complete.error.message}</p>
      )}
      {cancel.isError && (
        <p style={{ fontSize: 14, color: "var(--red)" }}>Erro ao cancelar: {cancel.error.message}</p>
      )}
    </div>
  );
}

function Timeline({ items }: { items: RebalanceProposal[] }) {
  if (items.length === 0) {
    return <p style={{ fontSize: 14, color: "var(--muted)" }}>Nenhum rebalanceamento anterior.</p>;
  }
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      {items.map((item) => (
        <div
          key={item.id}
          className="event"
          style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}
        >
          <div>
            <div style={{ fontSize: 14, fontWeight: 500, color: "var(--text)" }}>
              Proposta {item.id.slice(0, 8)}
            </div>
            <div style={{ marginTop: 4, fontSize: 12, color: "var(--muted-2)" }}>
              {dateTime.format(new Date(item.created_at))}
            </div>
          </div>
          <StatusBadge status={item.status} />
        </div>
      ))}
    </div>
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
        <section className="card card-pad">
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
        <section className="card card-pad">
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
          <Timeline items={proposalsQuery.data ?? []} />
        </section>
      )}
    </main>
  );
}
