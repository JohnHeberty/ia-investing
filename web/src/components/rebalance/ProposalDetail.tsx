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
import { ProposalActions } from "./ProposalActions";
import { ProposalProgress } from "./ProposalProgress";

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

      {proposal.execution_progress && <ProposalProgress progress={proposal.execution_progress} />}

      <ProposalActions
        proposal={proposal}
        approve={approve}
        execute={execute}
        complete={complete}
        cancel={cancel}
        selectedTradeCount={selectedTrades.size}
        selectedTradeIds={Array.from(selectedTrades)}
      />
    </div>
  );
}
