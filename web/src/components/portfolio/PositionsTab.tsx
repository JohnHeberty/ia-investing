import type { UseMutationResult } from "@tanstack/react-query";
import { AddPositionForm } from "@/components/add-position-form";
import type { PortfolioPosition } from "@/hooks/use-portfolios";

interface PositionsTabProps {
  positions: PortfolioPosition[];
  totalValue: number;
  currency: string;
  portfolioId: string;
  editingPosition: string | null;
  editForm: { ticker_symbol: string; quantity: string; avg_cost_per_share: string; current_price: string };
  setEditingPosition: (id: string | null) => void;
  setEditForm: (form: { ticker_symbol: string; quantity: string; avg_cost_per_share: string; current_price: string }) => void;
  needsRecalc: boolean;
  setNeedsRecalc: (v: boolean) => void;
  updatePosition: UseMutationResult<{ deleted: boolean }, Error, {
    portfolioId: string;
    positionId: string;
    ticker_symbol?: string;
    quantity?: number;
    avg_cost_per_share?: number;
    current_price?: number;
  }, unknown>;
  deletePosition: UseMutationResult<{ deleted: boolean }, Error, { portfolioId: string; positionId: string }, unknown>;
  showAddPosition: boolean;
  setShowAddPosition: (v: boolean) => void;
  editError: string | null;
  setEditError: (v: string | null) => void;
  refetchRecommendations: () => void;
  fmt: Intl.NumberFormat;
}

export function PositionsTab({
  positions,
  totalValue,
  portfolioId,
  editingPosition,
  editForm,
  setEditingPosition,
  setEditForm,
  needsRecalc,
  setNeedsRecalc,
  updatePosition,
  deletePosition,
  showAddPosition,
  setShowAddPosition,
  editError,
  setEditError,
  refetchRecommendations,
  fmt,
}: PositionsTabProps) {
  return (
    <div>
      {showAddPosition && (
        <div className="mb-16">
          <AddPositionForm portfolioId={portfolioId} onClose={() => setShowAddPosition(false)} />
        </div>
      )}

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
              <th>Preço Compra</th>
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
                        aria-label="Preço Compra"
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
                            const qty = parseFloat(editForm.quantity);
                            if (isNaN(qty) || qty <= 0) {
                              setEditError("Quantidade inválida");
                              return;
                            }
                            setEditError(null);
                            await updatePosition.mutateAsync({
                              portfolioId,
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
                          onClick={() => { setEditingPosition(null); setEditError(null); }}
                        >
                          Cancelar
                        </button>
                      </div>
                      {editError && (
                        <div style={{ fontSize: 11, color: "var(--red)", marginTop: 4 }}>{editError}</div>
                      )}
                    </td>
                  </tr>
                );
              }

              return (
                <tr key={pos.id}>
                  <td style={{ fontWeight: 500 }}>{pos.ticker_symbol}</td>
                  <td>{new Intl.NumberFormat("pt-BR").format(pos.quantity)}</td>
                  <td className="mono">
                    {fmt.format(pos.avg_cost_per_share)}
                  </td>
                  <td className="mono">
                    {fmt.format(currentPrice)}
                  </td>
                  <td className="mono">
                    {fmt.format(cost)}
                  </td>
                  <td className="mono">
                    {fmt.format(value)}
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
                          await deletePosition.mutateAsync({ portfolioId, positionId: pos.id });
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
  );
}
