import type { RebalanceProposal } from "@/hooks/use-rebalance";

export function ProposalProgress({ progress }: { progress: NonNullable<RebalanceProposal["execution_progress"]> }) {
  return (
    <section className="card card-pad">
      <div className="card-title"><h3>Progresso</h3></div>
      <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
        <div style={{ height: 8, flex: 1, overflow: "hidden", borderRadius: 999, background: "var(--surface-3)" }}>
          <div
            style={{ height: "100%", borderRadius: 999, background: "var(--accent)", transition: "all 0.3s", width: `${progress.percent_complete}%` }}
          />
        </div>
        <span style={{ fontSize: 14, color: "var(--muted)" }}>
          {progress.executed}/{progress.total}
        </span>
      </div>
      <div style={{ marginTop: 8, display: "flex", gap: 16, fontSize: 12, color: "var(--muted-2)" }}>
        <span>{progress.executed} executadas</span>
        <span>{progress.skipped} puladas</span>
        <span>{progress.failed} falhas</span>
      </div>
    </section>
  );
}
