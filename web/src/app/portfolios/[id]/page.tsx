"use client";

import { useParams, useRouter } from "next/navigation";
import { Suspense, useState } from "react";
import Link from "next/link";

import { AddPositionForm } from "@/components/add-position-form";
import { AllocationChart } from "@/components/allocation-chart";
import { PerformanceChart } from "@/components/performance-chart";
import { AsOfIndicator, Badge, DomainTabs, Metric, StatePanel } from "@/components/domain";
import {
  LoadingSkeleton,
} from "@/components/data-state-components";
import { usePortfolioDetail, usePortfolioRecommendations, useDeletePortfolio, useUpdatePosition, useDeletePosition } from "@/hooks/use-portfolios";
import { useAuditLogs } from "@/hooks/use-audit-logs";

function computeRiskMetrics(positions: Array<{
  ticker_symbol: string;
  quantity: number;
  avg_cost_per_share: number;
  current_price: number | null;
}>, totalValue: number) {
  const weights = positions.map((p) => {
    const price = p.current_price ?? p.avg_cost_per_share;
    return totalValue > 0 ? (p.quantity * price) / totalValue : 0;
  });
  const maxWeight = weights.length > 0 ? Math.max(...weights) : 0;
  const hhi = weights.reduce((sum, w) => sum + w * w, 0);
  const top3Weight = [...weights].sort((a, b) => b - a).slice(0, 3).reduce((s, w) => s + w, 0);
  return { maxWeight, hhi, top3Weight };
}

const actionLabels: Record<string, string> = {
  create: "Criação",
  update: "Atualização",
  delete: "Exclusão",
  transition: "Transição",
  "mandate.create": "Criação de Mandato",
  "portfolio.create": "Criação de Carteira",
  "portfolio.update": "Atualização de Carteira",
};

export function PortfolioContent({ id }: { id: string }) {
  const { portfolio, isLoading, isError } = usePortfolioDetail(id);
  const { recommendations, refetch: refetchRecommendations } = usePortfolioRecommendations(id);
  const { entries: auditEntries, isLoading: auditLoading } = useAuditLogs("portfolio", id);
  const [showAddPosition, setShowAddPosition] = useState(false);
  const [showConfirmDelete, setShowConfirmDelete] = useState(false);
  const [editingPosition, setEditingPosition] = useState<string | null>(null);
  const [editForm, setEditForm] = useState<{ ticker_symbol: string; quantity: string; avg_cost_per_share: string; current_price: string }>({ ticker_symbol: "", quantity: "", avg_cost_per_share: "", current_price: "" });
  const [needsRecalc, setNeedsRecalc] = useState(false);
  const deletePortfolio = useDeletePortfolio();
  const updatePosition = useUpdatePosition();
  const deletePosition = useDeletePosition();
  const router = useRouter();

  if (isLoading) {
    return (
      <>
        <div className="page-head">
          <div>
            <div className="eyebrow">Portfolio 360</div>
            <h1>Carregando...</h1>
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

  if (isError || !portfolio) {
    return (
      <>
        <div className="page-head">
          <div>
            <div className="eyebrow">Portfolio 360</div>
            <h1>Carteira não encontrada</h1>
          </div>
        </div>
        <div className="state-panel" data-state="error">
          <strong>Erro ao carregar carteira</strong>
          <p>Não foi possível acessar os dados desta carteira. Verifique o ID ou tente novamente.</p>
        </div>
        <div className="mt-16">
          <Link href="/portfolios" className="button secondary">
            ← Voltar para Carteiras
          </Link>
        </div>
      </>
    );
  }

  const name = portfolio.name || "Carteira";
  const currency = portfolio.base_currency || "BRL";
  const isPaper = portfolio.is_paper_trading;
  const positions = portfolio.positions || [];

  const totalValue = positions.reduce((sum, pos) => {
    const price = pos.current_price ?? pos.avg_cost_per_share;
    return sum + (pos.quantity * price);
  }, 0);

  const totalCost = positions.reduce((sum, pos) => {
    return sum + (pos.quantity * pos.avg_cost_per_share);
  }, 0);

  const totalPnl = totalValue - totalCost;
  const totalPnlPercent = totalCost > 0 ? (totalPnl / totalCost) * 100 : 0;
  const riskMetrics = computeRiskMetrics(positions, totalValue);

  return (
    <>
      <div className="page-head">
        <div>
          <div className="eyebrow">Portfolio 360</div>
          <h1>{name}</h1>
          <p className="subtitle">
            {isPaper ? "Carteira Paper" : "Carteira Live"} · {currency} · {positions.length} posições
          </p>
        </div>
        <div className="flex items-center gap-12">
          <Badge tone={isPaper ? "warn" : "good"}>
            {isPaper ? "Paper" : "Live"}
          </Badge>
          <AsOfIndicator
            value={new Date().toLocaleString("pt-BR")}
            freshness="Atual"
          />
          <button
            className="button danger sm"
            onClick={() => setShowConfirmDelete(true)}
          >
            Excluir
          </button>
        </div>
      </div>

      {showConfirmDelete && (
        <div
          className="modal-overlay"
          onClick={() => setShowConfirmDelete(false)}
        >
          <div
            className="card card-pad modal-content"
            onClick={(e) => e.stopPropagation()}
          >
            <h3>Excluir Carteira</h3>
            <p className="mt-8">
              Tem certeza que deseja excluir <strong>{name}</strong>? Esta ação é irreversível.
              Todas as posições, transações e dados vinculados serão removidos permanentemente.
            </p>
            {deletePortfolio.isError && (
              <div className="mt-8" style={{ fontSize: 12, color: "var(--red)" }}>
                {(deletePortfolio.error as Error)?.message || "Erro ao excluir"}
              </div>
            )}
            <div className="flex gap-8 mt-16" style={{ justifyContent: "flex-end" }}>
              <button
                className="button secondary"
                onClick={() => setShowConfirmDelete(false)}
                disabled={deletePortfolio.isPending}
              >
                Cancelar
              </button>
              <button
                className="button danger"
                disabled={deletePortfolio.isPending}
                onClick={async () => {
                  await deletePortfolio.mutateAsync(id);
                  router.push("/portfolios");
                }}
              >
                {deletePortfolio.isPending ? "Excluindo..." : "Excluir Carteira"}
              </button>
            </div>
          </div>
        </div>
      )}

      <section className="grid grid-4">
        <Metric
          label="Valor Total"
          value={new Intl.NumberFormat("pt-BR", { style: "currency", currency }).format(totalValue)}
          note={`${positions.length} posições`}
        />
        <Metric
          label="P&L Total"
          value={`${totalPnl >= 0 ? "+" : ""}${new Intl.NumberFormat("pt-BR", { style: "currency", currency }).format(totalPnl)}`}
          note={`${totalPnlPercent >= 0 ? "+" : ""}${totalPnlPercent.toFixed(2)}%`}
          tone={totalPnl >= 0 ? "positive" : "warning"}
        />
        <Metric
          label="Moeda"
          value={currency}
          note="Moeda base"
        />
        <Metric
          label="Tipo"
          value={isPaper ? "Paper" : "Live"}
          note="Ambiente de operação"
        />
      </section>

      {showAddPosition && (
        <div className="mb-16">
          <AddPositionForm portfolioId={id} onClose={() => setShowAddPosition(false)} />
        </div>
      )}

      <DomainTabs
        label="Detalhes da carteira"
        tabs={[
          {
            id: "positions",
            label: "Posições",
            content: (
              <div>
                {needsRecalc && (
                  <div className="banner warn mb-16">
                    <span>Posições alteradas. Clique em <strong>Recalcular</strong> para atualizar as recomendações.</span>
                    <button
                      className="button sm"
                      onClick={() => { refetchRecommendations(); setNeedsRecalc(false); }}
                    >
                      🔄 Recalcular
                    </button>
                  </div>
                )}
                <div className="flex gap-8 mb-16" style={{ justifyContent: "flex-end" }}>
                  <button className="button" onClick={() => setShowAddPosition(true)}>
                    + Adicionar Posição
                  </button>
                </div>
                {positions.length === 0 ? (
                  <div className="state-panel" data-state="empty">
                    <strong>Nenhuma posição</strong>
                    <p>Adicione posições para começar a acompanhar sua carteira.</p>
                  </div>
                ) : (
                  <table className="table">
                    <thead>
                      <tr>
                        <th>Ticker</th>
                        <th>Quantidade</th>
                        <th>Preço Médio</th>
                        <th>Preço Atual</th>
                        <th>Valor Investido</th>
                        <th>Valor Atual</th>
                        <th>P&L</th>
                        <th style={{ width: 80 }}>Ações</th>
                      </tr>
                    </thead>
                    <tbody>
                      {positions.map((pos) => {
                        const isEditing = editingPosition === pos.id;
                        const currentPrice = pos.current_price ?? pos.avg_cost_per_share;
                        const value = pos.quantity * currentPrice;
                        const cost = pos.quantity * pos.avg_cost_per_share;
                        const pnl = value - cost;
                        const pnlPercent = cost > 0 ? (pnl / cost) * 100 : 0;
                        const weight = totalValue > 0 ? (value / totalValue) * 100 : 0;

                        if (isEditing) {
                          return (
                            <tr key={pos.id} data-editing>
                              <td>
                                <input
                                  className="form-input"
                                  style={{ width: 80 }}
                                  aria-label="Ticker"
                                  value={editForm.ticker_symbol}
                                  onChange={(e) => setEditForm({ ...editForm, ticker_symbol: e.target.value })}
                                />
                              </td>
                              <td>
                                <input
                                  className="form-input mono"
                                  type="number"
                                  style={{ width: 80 }}
                                  aria-label="Quantidade"
                                  value={editForm.quantity}
                                  onChange={(e) => setEditForm({ ...editForm, quantity: e.target.value })}
                                />
                              </td>
                              <td>
                                <input
                                  className="form-input mono"
                                  type="number"
                                  step="0.01"
                                  style={{ width: 90 }}
                                  aria-label="Preço Médio"
                                  value={editForm.avg_cost_per_share}
                                  onChange={(e) => setEditForm({ ...editForm, avg_cost_per_share: e.target.value })}
                                />
                              </td>
                              <td>
                                <input
                                  className="form-input mono"
                                  type="number"
                                  step="0.01"
                                  style={{ width: 90 }}
                                  aria-label="Preço Atual"
                                  value={editForm.current_price}
                                  onChange={(e) => setEditForm({ ...editForm, current_price: e.target.value })}
                                />
                              </td>
                              <td colSpan={3} />
                              <td>
                                <div className="flex gap-4">
                                  <button
                                    className="button sm"
                                    disabled={updatePosition.isPending}
                                    onClick={async () => {
                                      await updatePosition.mutateAsync({
                                        portfolioId: id,
                                        positionId: pos.id,
                                        ticker_symbol: editForm.ticker_symbol,
                                        quantity: parseFloat(editForm.quantity),
                                        avg_cost_per_share: parseFloat(editForm.avg_cost_per_share),
                                        current_price: parseFloat(editForm.current_price) || undefined,
                                      });
                                      setEditingPosition(null);
                                      setNeedsRecalc(true);
                                    }}
                                  >
                                    {updatePosition.isPending ? "..." : "Salvar"}
                                  </button>
                                  <button
                                    className="button secondary sm"
                                    onClick={() => setEditingPosition(null)}
                                  >
                                    Cancelar
                                  </button>
                                </div>
                              </td>
                            </tr>
                          );
                        }

                        return (
                          <tr key={pos.id}>
                            <td style={{ fontWeight: 500 }}>{pos.ticker_symbol}</td>
                            <td>{new Intl.NumberFormat("pt-BR").format(pos.quantity)}</td>
                            <td className="mono">
                              {new Intl.NumberFormat("pt-BR", { style: "currency", currency }).format(pos.avg_cost_per_share)}
                            </td>
                            <td className="mono">
                              {new Intl.NumberFormat("pt-BR", { style: "currency", currency }).format(currentPrice)}
                            </td>
                            <td className="mono">
                              {new Intl.NumberFormat("pt-BR", { style: "currency", currency }).format(cost)}
                            </td>
                            <td className="mono">
                              {new Intl.NumberFormat("pt-BR", { style: "currency", currency }).format(value)}
                            </td>
                            <td className="mono" style={{ color: pnl >= 0 ? "var(--accent)" : "var(--red)" }}>
                              {pnl >= 0 ? "+" : ""}{pnlPercent.toFixed(2)}%
                              <span className="text-xs muted" style={{ marginLeft: 4 }}>({weight.toFixed(1)}%)</span>
                            </td>
                            <td>
                              <div className="flex gap-4">
                                <button
                                  className="button secondary sm"
                                  onClick={() => {
                                    setEditingPosition(pos.id);
                                    setEditForm({
                                      ticker_symbol: pos.ticker_symbol,
                                      quantity: String(pos.quantity),
                                      avg_cost_per_share: String(pos.avg_cost_per_share),
                                      current_price: pos.current_price ? String(pos.current_price) : "",
                                    });
                                  }}
                                >
                                  ✏️
                                </button>
                                <button
                                  className="button secondary sm"
                                  style={{ color: "var(--red)" }}
                                  onClick={async () => {
                                    if (!confirm(`Excluir posição ${pos.ticker_symbol}?`)) return;
                                    await deletePosition.mutateAsync({ portfolioId: id, positionId: pos.id });
                                    setNeedsRecalc(true);
                                  }}
                                >
                                  🗑️
                                </button>
                              </div>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                )}
              </div>
            ),
          },
          {
            id: "performance",
            label: "Performance",
            content: (
              <div>
                <div className="card card-pad mb-16">
                  <div className="card-title">
                    <h2>Resumo de Performance</h2>
                  </div>
                  <div className="stat-grid">
                    <div>
                      <div className="stat-label">Valor Investido</div>
                      <div className="stat-value">
                        {new Intl.NumberFormat("pt-BR", { style: "currency", currency }).format(totalCost)}
                      </div>
                    </div>
                    <div>
                      <div className="stat-label">Valor Atual</div>
                      <div className="stat-value">
                        {new Intl.NumberFormat("pt-BR", { style: "currency", currency }).format(totalValue)}
                      </div>
                    </div>
                    <div>
                      <div className="stat-label">Retorno</div>
                      <div className="stat-value" style={{ color: totalPnl >= 0 ? "var(--accent)" : "var(--red)" }}>
                        {totalPnlPercent >= 0 ? "+" : ""}{totalPnlPercent.toFixed(2)}%
                      </div>
                    </div>
                  </div>
                </div>
                <div className="card card-pad">
                  <div className="card-title">
                    <h2>P&L por Ativo</h2>
                  </div>
                  <PerformanceChart positions={positions} currency={currency} />
                </div>
              </div>
            ),
          },
          {
            id: "risk",
            label: "Risco",
            content: (
              <div>
                <div className="card card-pad mb-16">
                  <div className="card-title">
                    <h2>Métricas de Risco</h2>
                  </div>
                  <div className="stat-grid">
                    <div>
                      <div className="stat-label">HHI (Concentração)</div>
                      <div className="stat-value">
                        {(riskMetrics.hhi * 10000).toFixed(0)}
                      </div>
                      <div className="stat-detail" style={{ color: riskMetrics.hhi > 0.25 ? "var(--red)" : riskMetrics.hhi > 0.15 ? "var(--amber)" : "var(--accent)" }}>
                        {riskMetrics.hhi > 0.25 ? "Alta concentração" : riskMetrics.hhi > 0.15 ? "Concentração moderada" : "Diversificada"}
                      </div>
                    </div>
                    <div>
                      <div className="stat-label">Maior Posição</div>
                      <div className="stat-value">
                        {(riskMetrics.maxWeight * 100).toFixed(1)}%
                      </div>
                      <div className="stat-detail" style={{ color: riskMetrics.maxWeight > 0.25 ? "var(--red)" : "var(--accent)" }}>
                        {riskMetrics.maxWeight > 0.25 ? "Acima do limite (25%)" : "Dentro do limite"}
                      </div>
                    </div>
                    <div>
                      <div className="stat-label">Top 3 Posições</div>
                      <div className="stat-value">
                        {(riskMetrics.top3Weight * 100).toFixed(1)}%
                      </div>
                      <div className="stat-detail" style={{ color: riskMetrics.top3Weight > 0.7 ? "var(--red)" : "var(--accent)" }}>
                        {riskMetrics.top3Weight > 0.7 ? "Concentrado" : "Balanceado"}
                      </div>
                    </div>
                  </div>
                </div>
                <div className="card card-pad">
                  <div className="card-title">
                    <h2>Exposição por Ativo</h2>
                  </div>
                  {positions.length > 0 ? (
                    <div className="mt-12">
                      {positions.map((pos) => {
                        const currentPrice = pos.current_price ?? pos.avg_cost_per_share;
                        const value = pos.quantity * currentPrice;
                        const weight = totalValue > 0 ? (value / totalValue) * 100 : 0;
                        return (
                          <div key={pos.id} className="exposure-bar">
                            <span style={{ width: 60, fontWeight: 500 }}>{pos.ticker_symbol}</span>
                            <div className="bar-track">
                              <div
                                className={`bar-fill ${weight > 25 ? "high" : weight > 15 ? "mid" : "low"}`}
                                style={{ width: `${Math.min(weight, 100)}%` }}
                              />
                            </div>
                            <span style={{ width: 50, textAlign: "right", fontSize: 12, fontFamily: "var(--font-mono)" }}>
                              {weight.toFixed(1)}%
                            </span>
                          </div>
                        );
                      })}
                    </div>
                  ) : (
                    <p style={{ color: "var(--muted)", fontSize: 13, padding: 16 }}>Sem posições para exibir exposição.</p>
                  )}
                </div>
              </div>
            ),
          },
          {
            id: "allocation",
            label: "Alocação",
            content: (
              <div>
                <AllocationChart positions={positions} currency={currency} />
                {positions.length > 0 && (
                  <div className="card card-pad mt-16">
                    <div className="card-title">
                      <h2>Distribuição da Carteira</h2>
                    </div>
                    <div className="mt-16">
                      {positions.map((pos, idx) => {
                        const currentPrice = pos.current_price ?? pos.avg_cost_per_share;
                        const value = pos.quantity * currentPrice;
                        const weight = totalValue > 0 ? (value / totalValue) * 100 : 0;
                        const colors = ["var(--accent)", "var(--blue)", "var(--amber)", "var(--red)", "#9b59b6", "#1abc9c"];
                        const colorIndex = idx % colors.length;
                        return (
                          <div key={pos.id} className="flex items-center gap-12" style={{ marginBottom: 12 }}>
                            <div style={{ width: 12, height: 12, borderRadius: 2, background: colors[colorIndex] }} />
                            <span style={{ flex: 1, fontWeight: 500 }}>{pos.ticker_symbol}</span>
                            <span style={{ fontFamily: "var(--font-mono)", fontSize: 13 }}>
                              {new Intl.NumberFormat("pt-BR", { style: "currency", currency }).format(value)}
                            </span>
                            <span style={{ fontFamily: "var(--font-mono)", fontSize: 13, color: "var(--muted)", width: 50, textAlign: "right" }}>
                              {weight.toFixed(1)}%
                            </span>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}
              </div>
            ),
          },
          {
            id: "riskLimits",
            label: "Limites",
            content: (
              <div className="card card-pad">
                <div className="card-title">
                  <h2>Limites de Risco</h2>
                </div>
                <table className="table mt-12">
                  <thead>
                    <tr>
                      <th>Limite</th>
                      <th>Valor Atual</th>
                      <th>Limite Máximo</th>
                      <th>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr>
                      <td>Concentração por Ativo</td>
                      <td style={{ fontFamily: "var(--font-mono)" }}>
                        {(riskMetrics.maxWeight * 100).toFixed(1)}%
                      </td>
                      <td>25%</td>
                      <td>
                        <Badge tone={riskMetrics.maxWeight > 0.25 ? "bad" : "good"}>
                          {riskMetrics.maxWeight > 0.25 ? "Violação" : "OK"}
                        </Badge>
                      </td>
                    </tr>
                    <tr>
                      <td>HHI</td>
                      <td className="mono">{(riskMetrics.hhi * 10000).toFixed(0)}</td>
                      <td>2500</td>
                      <td>
                        <Badge tone={riskMetrics.hhi > 0.25 ? "bad" : "good"}>
                          {riskMetrics.hhi > 0.25 ? "Violação" : "OK"}
                        </Badge>
                      </td>
                    </tr>
                    <tr>
                      <td>Número de Posições</td>
                      <td style={{ fontFamily: "var(--font-mono)" }}>{positions.length}</td>
                      <td>20</td>
                      <td>
                        <Badge tone={positions.length > 20 ? "bad" : "good"}>
                          {positions.length > 20 ? "Violação" : "OK"}
                        </Badge>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            ),
          },
          {
            id: "theses",
            label: "Teses",
            content: (
              <div className="card card-pad">
                <div className="card-title">
                  <h2>Teses de Investimento</h2>
                </div>
                <div style={{ padding: 24 }}>
                  <p style={{ fontSize: 13, color: "var(--muted)", marginBottom: 12 }}>
                    Teses de investimento são gerenciadas pelo workflow institucional.
                    Para vincular teses a esta carteira, é necessário criar um portfolio version
                    e associar as teses durante o processo de aprovação do comitê.
                  </p>
                  <div className="state-panel mt-12" data-state="empty">
                    <strong>Nenhuma tese vinculada</strong>
                    <p>
                      Teses e propostas vinculadas a esta carteira aparecerão aqui
                      quando conectadas ao workflow de aprovação do comitê de investimento.
                    </p>
                  </div>
                </div>
              </div>
            ),
          },
          {
            id: "recommendations",
            label: "Recomendações",
            content: (
              <div>
                {recommendations ? (
                  <>
                    <div className="card card-pad mb-16">
                      <div className="card-title">
                        <h2>Resumo da Análise</h2>
                        <Badge tone={recommendations.overall_risk === "high" ? "bad" : recommendations.overall_risk === "medium" ? "warn" : "good"}>
                          Risco: {recommendations.overall_risk}
                        </Badge>
                      </div>
                      <p className="mt-8">
                        {recommendations.summary}
                      </p>
                      {(recommendations.key_risks?.length ?? 0) > 0 && (
                        <div className="mt-12">
                          <div style={{ fontSize: 12, fontWeight: 500, marginBottom: 4 }}>Riscos Principais:</div>
                          {(recommendations.key_risks ?? []).map((risk, i) => (
                            <div key={i} style={{ fontSize: 12, color: "var(--amber)" }}>⚠️ {risk}</div>
                          ))}
                        </div>
                      )}
                    </div>

                    <div className="card card-pad">
                      <div className="card-title">
                        <h2>Recomendações por Ativo</h2>
                      </div>
                      <table className="table mt-12">
                        <thead>
                          <tr>
                            <th>Ticker</th>
                            <th>Ação</th>
                            <th>Peso Atual</th>
                            <th>Peso Alvo</th>
                            <th>Confiança</th>
                            <th>R/R</th>
                            <th>Razão</th>
                          </tr>
                        </thead>
                        <tbody>
                          {(recommendations.recommendations ?? []).map((rec) => (
                            <tr key={rec.ticker}>
                              <td style={{ fontWeight: 500 }}>{rec.ticker}</td>
                              <td>
                                <Badge tone={
                                  rec.action === "buy" || rec.action === "increase" ? "good" :
                                  rec.action === "sell" || rec.action === "exit" ? "bad" :
                                  rec.action === "reduce" ? "warn" : "neutral"
                                }>
                                  {rec.action.toUpperCase()}
                                </Badge>
                              </td>
                              <td style={{ fontFamily: "var(--font-mono)" }}>{(rec.current_weight * 100).toFixed(1)}%</td>
                              <td style={{ fontFamily: "var(--font-mono)" }}>{(rec.target_weight * 100).toFixed(1)}%</td>
                              <td style={{ fontFamily: "var(--font-mono)" }}>{(rec.confidence * 100).toFixed(0)}%</td>
                              <td style={{ fontFamily: "var(--font-mono)" }}>{rec.risk_reward?.toFixed(1) ?? "—"}</td>
                              <td style={{ fontSize: 12, color: "var(--muted)", maxWidth: 200 }}>{rec.rationale}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </>
                ) : (
                  <StatePanel
                    title="Recomendações dos Agents"
                    detail="Recomendações de compra, venda e rebalanceamento geradas pelos agents de IA serão exibidas aqui."
                  />
                )}
              </div>
            ),
          },
          {
            id: "audit",
            label: "Auditoria",
            content: (
              <div className="card card-pad">
                <div className="card-title">
                  <h2>Trilha de Auditoria</h2>
                  {auditEntries.length > 0 && (
                    <span className="audit-meta">{auditEntries.length} registros</span>
                  )}
                </div>
                {auditLoading ? (
                  <LoadingSkeleton lines={4} />
                ) : auditEntries.length === 0 ? (
                  <div className="state-panel mt-12" data-state="empty">
                    <strong>Nenhum registro</strong>
                    <p>Ações realizadas nesta carteira aparecerão aqui quando conectadas ao ledger de auditoria.</p>
                  </div>
                ) : (
                  <div className="mt-12">
                    {auditEntries.map((entry) => (
                      <div key={entry.id} className="audit-entry">
                        <div
                          className={`audit-dot ${entry.action.includes("create") ? "create" : entry.action.includes("delete") ? "delete" : "update"}`}
                        />
                        <div className="audit-detail">
                          <div className="audit-action">
                            {actionLabels[entry.action] || entry.action}
                          </div>
                          <div className="audit-meta">
                            {entry.resource_type}{entry.resource_id ? ` · ${entry.resource_id.toString().slice(0, 8)}…` : ""}
                          </div>
                          {entry.changes && Object.keys(entry.changes).length > 0 && (
                            <div className="audit-meta" style={{ marginTop: 2, fontFamily: "var(--font-mono)" }}>
                              {Object.entries(entry.changes).map(([key, val]) => (
                                <span key={key} style={{ marginRight: 8 }}>
                                  {key}: {typeof val === "object" && val !== null && "after" in (val as Record<string, unknown>)
                                    ? String((val as Record<string, unknown>).after ?? "—")
                                    : String(val)}
                                </span>
                              ))}
                            </div>
                          )}
                        </div>
                        <div className="audit-time">
                          {new Date(entry.timestamp).toLocaleString("pt-BR", {
                            day: "2-digit",
                            month: "2-digit",
                            year: "2-digit",
                            hour: "2-digit",
                            minute: "2-digit",
                          })}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ),
          },
        ]}
      />

      <footer className="mt-12" style={{ padding: "12px 0", borderTop: "1px solid var(--line-soft)", fontSize: 11, color: "var(--muted)" }}>
        <p>
          <strong>Moeda:</strong> {currency} ·
          <strong> Tipo:</strong> {isPaper ? "Paper Trading" : "Live"} ·
          <strong> Posições:</strong> {positions.length} ·
          <strong> NAV:</strong> {new Intl.NumberFormat("pt-BR", { style: "currency", currency }).format(totalValue)}
        </p>
      </footer>
    </>
  );
}

export default function PortfolioPage() {
  const params = useParams<{ id: string }>();
  const id = params?.id ?? "";

  return (
    <Suspense
      fallback={
        <>
          <div className="page-head">
            <div>
              <div className="eyebrow">Portfolio 360</div>
              <h1>Carregando...</h1>
            </div>
          </div>
          <LoadingSkeleton lines={6} />
        </>
      }
    >
      <PortfolioContent id={id} />
    </Suspense>
  );
}
