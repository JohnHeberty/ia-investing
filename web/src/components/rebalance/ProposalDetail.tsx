import { useState } from "react";
import type { RebalanceProposal } from "@/hooks/use-rebalance";
import {
  useApproveRebalance,
  useCancelRebalance,
  useCompleteRebalance,
  useExecuteTradeStep,
} from "@/hooks/use-rebalance";
import { StatusBadge, pct, dateTime } from "./shared";
import { DriftTable } from "./DriftTable";
import { TradesTable } from "./TradesTable";

export function ProposalDetail({
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
