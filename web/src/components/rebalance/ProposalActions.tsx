import type { RebalanceProposal } from "@/hooks/use-rebalance";
import {
  useApproveRebalance,
  useCancelRebalance,
  useCompleteRebalance,
  useExecuteTradeStep,
} from "@/hooks/use-rebalance";

type ApproveMutation = ReturnType<typeof useApproveRebalance>;
type ExecuteMutation = ReturnType<typeof useExecuteTradeStep>;
type CompleteMutation = ReturnType<typeof useCompleteRebalance>;
type CancelMutation = ReturnType<typeof useCancelRebalance>;

export function ProposalActions({
  proposal,
  approve,
  execute,
  complete,
  cancel,
  selectedTradeCount,
  selectedTradeIds,
}: {
  proposal: RebalanceProposal;
  approve: ApproveMutation;
  execute: ExecuteMutation;
  complete: CompleteMutation;
  cancel: CancelMutation;
  selectedTradeCount: number;
  selectedTradeIds: string[];
}) {
  const canApprove = proposal.status === "draft";
  const canExecute = proposal.status === "approved" || proposal.status === "in_progress";
  const canComplete = proposal.status === "in_progress" || proposal.status === "approved";
  const canCancel = !["completed", "cancelled"].includes(proposal.status);

  return (
    <>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 12 }}>
        {canApprove && (
          <button
            onClick={() => approve.mutate({ proposalId: proposal.id })}
            disabled={approve.isPending}
            className="button"
            style={{
              background: "var(--blue)",
              color: "#fff",
              opacity: approve.isPending ? 0.5 : 1,
            }}
          >
            {approve.isPending ? "Aprovando..." : "Aprovar proposta"}
          </button>
        )}
        {canExecute && selectedTradeCount > 0 && (
          <button
            onClick={() => execute.mutate({ proposalId: proposal.id, tradeIds: selectedTradeIds })}
            disabled={execute.isPending}
            className="button"
            style={{ opacity: execute.isPending ? 0.5 : 1 }}
          >
            {execute.isPending ? "Executando..." : `Executar ${selectedTradeCount} trade(s)`}
          </button>
        )}
        {canComplete && (
          <button
            onClick={() => complete.mutate({ proposalId: proposal.id })}
            disabled={complete.isPending}
            className="button secondary"
            style={{
              borderColor: "var(--accent)",
              color: "var(--accent)",
              opacity: complete.isPending ? 0.5 : 1,
            }}
          >
            {complete.isPending ? "Finalizando..." : "Completar rebalanceamento"}
          </button>
        )}
        {canCancel && (
          <button
            onClick={() =>
              cancel.mutate({ proposalId: proposal.id, reason: "Cancelado pelo operador" })
            }
            disabled={cancel.isPending}
            className="button secondary"
            style={{
              borderColor: "var(--red)",
              color: "var(--red)",
              opacity: cancel.isPending ? 0.5 : 1,
            }}
          >
            {cancel.isPending ? "Cancelando..." : "Cancelar proposta"}
          </button>
        )}
      </div>

      {approve.isError && (
        <p style={{ fontSize: 14, color: "var(--red)" }}>
          Erro ao aprovar: {approve.error.message}
        </p>
      )}
      {execute.isError && (
        <p style={{ fontSize: 14, color: "var(--red)" }}>
          Erro ao executar: {execute.error.message}
        </p>
      )}
      {complete.isError && (
        <p style={{ fontSize: 14, color: "var(--red)" }}>
          Erro ao finalizar: {complete.error.message}
        </p>
      )}
      {cancel.isError && (
        <p style={{ fontSize: 14, color: "var(--red)" }}>
          Erro ao cancelar: {cancel.error.message}
        </p>
      )}
    </>
  );
}
