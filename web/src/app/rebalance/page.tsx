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

const DEMO_PORTFOLIOS = [
  { id: "portfolio-1", name: "Brasil Long Only" },
  { id: "portfolio-2", name: "Global Tech" },
  { id: "portfolio-3", name: "Dividend Yield" },
];

function pct(value: number): string {
  return percent.format(value / 100);
}

function DriftBadge({ severity }: { severity: DriftItem["severity"] }) {
  const colors: Record<string, string> = {
    green: "bg-emerald-900/40 text-emerald-300 border-emerald-700",
    yellow: "bg-amber-900/40 text-amber-200 border-amber-700",
    red: "bg-red-900/40 text-red-200 border-red-700",
  };
  return (
    <span className={`rounded-full border px-2 py-0.5 text-xs ${colors[severity]}`}>
      {severity === "green" ? "<1%" : severity === "yellow" ? "1-3%" : ">3%"}
    </span>
  );
}

function SideBadge({ side }: { side: "buy" | "sell" }) {
  return (
    <span
      className={`rounded px-1.5 py-0.5 text-xs font-medium ${
        side === "buy"
          ? "bg-emerald-900/40 text-emerald-300"
          : "bg-red-900/40 text-red-200"
      }`}
    >
      {side.toUpperCase()}
    </span>
  );
}

function StatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    draft: "bg-slate-700 text-slate-200",
    approved: "bg-blue-900/40 text-blue-200",
    in_progress: "bg-amber-900/40 text-amber-200",
    completed: "bg-emerald-900/40 text-emerald-300",
    cancelled: "bg-red-900/40 text-red-200",
  };
  return (
    <span className={`rounded px-1.5 py-0.5 text-xs ${styles[status] || "bg-slate-700 text-slate-200"}`}>
      {status.replaceAll("_", " ")}
    </span>
  );
}

function LoadingSkeleton() {
  return (
    <div className="space-y-4 p-6">
      <div className="h-8 w-64 animate-pulse rounded bg-slate-800" />
      <div className="h-4 w-96 animate-pulse rounded bg-slate-800" />
      <div className="grid gap-4 md:grid-cols-2">
        <div className="h-48 animate-pulse rounded-xl border border-slate-800 bg-slate-900" />
        <div className="h-48 animate-pulse rounded-xl border border-slate-800 bg-slate-900" />
      </div>
    </div>
  );
}

function ErrorState({ message }: { message: string }) {
  return (
    <main className="p-6">
      <h1 className="text-2xl font-semibold text-slate-100">Rebalanceamento</h1>
      <div role="alert" className="mt-6 rounded-xl border border-red-900 bg-red-950/50 p-4 text-red-200">
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
    <form onSubmit={handleSubmit} className="space-y-4 rounded-xl border border-slate-700 bg-slate-900 p-5">
      <h3 className="text-lg font-semibold text-slate-100">Nova proposta de rebalanceamento</h3>
      <div>
        <label className="block text-sm text-slate-400">Target allocations (JSON)</label>
        <textarea
          className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 p-2 font-mono text-sm text-slate-100"
          rows={5}
          placeholder='{"AAPL": 0.25, "GOOGL": 0.15, "MSFT": 0.20}'
          value={targets}
          onChange={(e) => setTargets(e.target.value)}
        />
      </div>
      <div>
        <label className="block text-sm text-slate-400">Rationale</label>
        <textarea
          className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 p-2 text-sm text-slate-100"
          rows={3}
          value={rationale}
          onChange={(e) => setRationale(e.target.value)}
        />
      </div>
      <div className="flex gap-3">
        <button
          type="submit"
          disabled={propose.isPending || !targets || !rationale}
          className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-500 disabled:opacity-50"
        >
          {propose.isPending ? "Criando..." : "Propor rebalanceamento"}
        </button>
        <button type="button" onClick={onClose} className="rounded-lg border border-slate-700 px-4 py-2 text-sm text-slate-300 hover:bg-slate-800">
          Cancelar
        </button>
      </div>
      {propose.isError && (
        <p className="text-sm text-red-300">Erro: {propose.error.message}</p>
      )}
    </form>
  );
}

function DriftTable({ items }: { items: DriftItem[] }) {
  if (items.length === 0) {
    return <p className="text-sm text-slate-400">Nenhum desvio detectado.</p>;
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
            <td className="font-medium text-slate-100">{item.ticker}</td>
            <td>{pct(item.current_weight)}</td>
            <td>{pct(item.target_weight)}</td>
            <td className="font-mono">{pct(item.drift)}</td>
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
    return <p className="text-sm text-slate-400">Nenhuma trade calculada.</p>;
  }
  return (
    <table className="table">
      <thead>
        <tr>
          <th className="w-10" />
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
                  className="h-4 w-4 accent-emerald-500"
                />
              )}
            </td>
            <td className="text-center text-xs text-slate-500">{trade.execution_order}</td>
            <td className="font-medium text-slate-100">{trade.ticker}</td>
            <td><SideBadge side={trade.side} /></td>
            <td>
              {pct(trade.current_weight)} → {pct(trade.target_weight)}
            </td>
            <td className={`font-mono ${trade.delta > 0 ? "text-emerald-300" : "text-red-200"}`}>
              {trade.delta > 0 ? "+" : ""}{pct(trade.delta)}
            </td>
            <td className="font-mono text-slate-100">{money.format(trade.estimated_value)}</td>
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
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <button onClick={onBack} className="text-sm text-blue-400 hover:underline">
          &larr; Voltar para lista
        </button>
        <StatusBadge status={proposal.status} />
      </div>

      <div className="rounded-xl border border-slate-800 bg-slate-950 p-5">
        <h2 className="text-lg font-semibold text-slate-100">
          Proposta {proposal.id.slice(0, 8)}
        </h2>
        <p className="mt-2 text-sm text-slate-400">{proposal.rationale}</p>
        <div className="mt-4 flex flex-wrap gap-4 text-xs text-slate-500">
          <span>Criada por: {proposal.created_by}</span>
          <span>Em: {dateTime.format(new Date(proposal.created_at))}</span>
          {proposal.approved_by && <span>Aprovada por: {proposal.approved_by}</span>}
        </div>
      </div>

      {proposal.drift_analysis && (
        <section className="rounded-xl border border-slate-800 bg-slate-950 p-5">
          <h3 className="mb-4 text-sm font-semibold text-slate-100">Análise de desvio</h3>
          <div className="mb-4 flex gap-6 text-sm">
            <div>
              <span className="text-slate-400">Desvio máximo: </span>
              <span className="font-mono text-slate-100">{pct(proposal.drift_analysis.max_drift)}</span>
            </div>
            <div>
              <span className="text-slate-400">Desvio total: </span>
              <span className="font-mono text-slate-100">{pct(proposal.drift_analysis.total_drift)}</span>
            </div>
          </div>
          <DriftTable items={proposal.drift_analysis.items} />
        </section>
      )}

      <section className="rounded-xl border border-slate-800 bg-slate-950 p-5">
        <h3 className="mb-4 text-sm font-semibold text-slate-100">Trades</h3>
        <TradesTable trades={proposal.trades} selected={selectedTrades} onToggle={toggleTrade} />
      </section>

      {proposal.execution_progress && (
        <section className="rounded-xl border border-slate-800 bg-slate-950 p-5">
          <h3 className="mb-4 text-sm font-semibold text-slate-100">Progresso</h3>
          <div className="flex items-center gap-4">
            <div className="h-2 flex-1 overflow-hidden rounded-full bg-slate-800">
              <div
                className="h-full rounded-full bg-emerald-500 transition-all"
                style={{ width: `${proposal.execution_progress.percent_complete}%` }}
              />
            </div>
            <span className="text-sm text-slate-400">
              {proposal.execution_progress.executed}/{proposal.execution_progress.total}
            </span>
          </div>
          <div className="mt-2 flex gap-4 text-xs text-slate-500">
            <span>{proposal.execution_progress.executed} executadas</span>
            <span>{proposal.execution_progress.skipped} puladas</span>
            <span>{proposal.execution_progress.failed} falhas</span>
          </div>
        </section>
      )}

      <div className="flex flex-wrap gap-3">
        {canApprove && (
          <button
            onClick={() => approve.mutate({ proposalId: proposal.id })}
            disabled={approve.isPending}
            className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-500 disabled:opacity-50"
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
            className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-500 disabled:opacity-50"
          >
            {execute.isPending ? "Executando..." : `Executar ${selectedTrades.size} trade(s)`}
          </button>
        )}
        {canComplete && (
          <button
            onClick={() => complete.mutate({ proposalId: proposal.id })}
            disabled={complete.isPending}
            className="rounded-lg border border-emerald-700 px-4 py-2 text-sm text-emerald-300 hover:bg-emerald-950"
          >
            {complete.isPending ? "Finalizando..." : "Completar rebalanceamento"}
          </button>
        )}
        {canCancel && (
          <button
            onClick={() => cancel.mutate({ proposalId: proposal.id, reason: "Cancelado pelo operador" })}
            disabled={cancel.isPending}
            className="rounded-lg border border-red-800 px-4 py-2 text-sm text-red-300 hover:bg-red-950"
          >
            {cancel.isPending ? "Cancelando..." : "Cancelar proposta"}
          </button>
        )}
      </div>

      {approve.isError && (
        <p className="text-sm text-red-300">Erro ao aprovar: {approve.error.message}</p>
      )}
      {execute.isError && (
        <p className="text-sm text-red-300">Erro ao executar: {execute.error.message}</p>
      )}
    </div>
  );
}

function Timeline({ items }: { items: RebalanceProposal[] }) {
  if (items.length === 0) {
    return <p className="text-sm text-slate-400">Nenhum rebalanceamento anterior.</p>;
  }
  return (
    <div className="space-y-3">
      {items.map((item) => (
        <div key={item.id} className="flex items-center justify-between rounded-lg border border-slate-800 p-3">
          <div>
            <div className="text-sm font-medium text-slate-100">
              Proposta {item.id.slice(0, 8)}
            </div>
            <div className="mt-1 text-xs text-slate-500">
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
  const [selectedPortfolioId, setSelectedPortfolioId] = useState<string>(DEMO_PORTFOLIOS[0].id);
  const [showProposeForm, setShowProposeForm] = useState(false);
  const [selectedProposalId, setSelectedProposalId] = useState<string | null>(null);

  const driftQuery = useDriftSummary(selectedPortfolioId);
  const proposalsQuery = useRebalanceProposals(selectedPortfolioId);
  const proposalDetailQuery = useRebalanceProposal(selectedProposalId ?? undefined);
  const historyQuery = useRebalanceProposals(selectedPortfolioId);

  if (driftQuery.isError && proposalsQuery.isError) {
    return <ErrorState message={driftQuery.error?.message ?? proposalsQuery.error?.message ?? "Erro desconhecido"} />;
  }

  const isLoading =
    (driftQuery.isPending && driftQuery.fetchStatus !== "idle") ||
    (proposalsQuery.isPending && proposalsQuery.fetchStatus !== "idle");

  if (selectedProposalId && proposalDetailQuery.data) {
    return (
      <main className="space-y-6 p-6">
        <header>
          <p className="text-xs uppercase tracking-[0.2em] text-slate-500">Portfolio Intelligence</p>
          <h1 className="mt-2 text-3xl font-semibold text-slate-100">Rebalanceamento</h1>
        </header>
        <ProposalDetail proposal={proposalDetailQuery.data} onBack={() => setSelectedProposalId(null)} />
      </main>
    );
  }

  return (
    <main className="space-y-8 p-6">
      <header>
        <p className="text-xs uppercase tracking-[0.2em] text-slate-500">Portfolio Intelligence</p>
        <h1 className="mt-2 text-3xl font-semibold text-slate-100">Rebalanceamento de carteiras</h1>
        <p className="mt-2 max-w-3xl text-sm text-slate-400">
          Monitore desvios de alocação, proponha e execute rebalanceamentos, e acompanhe o histórico.
        </p>
      </header>

      <div className="flex flex-wrap items-center gap-4">
        <select
          className="rounded-lg border border-slate-700 bg-slate-950 px-4 py-2 text-sm text-slate-100"
          value={selectedPortfolioId}
          onChange={(e) => {
            setSelectedPortfolioId(e.target.value);
            setSelectedProposalId(null);
            setShowProposeForm(false);
          }}
        >
          {DEMO_PORTFOLIOS.map((p) => (
            <option key={p.id} value={p.id}>{p.name}</option>
          ))}
        </select>
        <button
          onClick={() => setShowProposeForm(true)}
          className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-500"
        >
          Propor rebalanceamento
        </button>
      </div>

      {isLoading && <LoadingSkeleton />}

      {!isLoading && showProposeForm && (
        <ProposeForm portfolioId={selectedPortfolioId} onClose={() => setShowProposeForm(false)} />
      )}

      {!isLoading && driftQuery.data && (
        <section className="rounded-xl border border-slate-800 bg-slate-950 p-5">
          <h2 className="mb-4 text-lg font-semibold text-slate-100">Desvios atuais vs. alvo</h2>
          <div className="mb-4 flex gap-6 text-sm">
            <div>
              <span className="text-slate-400">Desvio máximo: </span>
              <span className="font-mono text-slate-100">{pct(driftQuery.data.max_drift)}</span>
            </div>
            <div>
              <span className="text-slate-400">Desvio total: </span>
              <span className="font-mono text-slate-100">{pct(driftQuery.data.total_drift)}</span>
            </div>
          </div>
          <DriftTable items={driftQuery.data.items} />
        </section>
      )}

      {!isLoading && proposalsQuery.data && (
        <section className="rounded-xl border border-slate-800 bg-slate-950 p-5">
          <h2 className="mb-4 text-lg font-semibold text-slate-100">Propostas</h2>
          {proposalsQuery.data.length === 0 ? (
            <p className="text-sm text-slate-400">Nenhuma proposta de rebalanceamento para esta carteira.</p>
          ) : (
            <div className="space-y-2">
              {proposalsQuery.data.map((p) => (
                <button
                  key={p.id}
                  onClick={() => setSelectedProposalId(p.id)}
                  className="flex w-full items-center justify-between rounded-lg border border-slate-800 p-3 text-left hover:bg-slate-900"
                >
                  <div>
                    <div className="text-sm font-medium text-slate-100">
                      Proposta {p.id.slice(0, 8)}
                    </div>
                    <div className="mt-1 text-xs text-slate-500">
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
        <section className="rounded-xl border border-slate-800 bg-slate-950 p-5">
          <h2 className="mb-4 text-lg font-semibold text-slate-100">Histórico de rebalanceamentos</h2>
          <Timeline items={historyQuery.data ?? []} />
        </section>
      )}
    </main>
  );
}
