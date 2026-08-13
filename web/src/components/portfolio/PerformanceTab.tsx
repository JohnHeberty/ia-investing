import { PerformanceChart } from "@/components/performance-chart";
import type { PortfolioPosition } from "@/hooks/use-portfolios";

interface PerformanceTabProps {
  positions: PortfolioPosition[];
  totalValue: number;
  totalCost: number;
  totalPnl: number;
  totalPnlPercent: number;
  currency: string;
  fmt: Intl.NumberFormat;
}

export function PerformanceTab({
  positions,
  totalValue,
  totalCost,
  totalPnl,
  totalPnlPercent,
  currency,
  fmt,
}: PerformanceTabProps) {
  return (
    <div>
      <div className="card card-pad mb-16">
        <div className="card-title">
          <h2>Resumo de Performance</h2>
        </div>
        <div className="stat-grid">
          <div>
            <div className="stat-label">Valor Investido</div>
            <div className="stat-value">{fmt.format(totalCost)}</div>
          </div>
          <div>
            <div className="stat-label">Valor Atual</div>
            <div className="stat-value">{fmt.format(totalValue)}</div>
          </div>
          <div>
            <div className="stat-label">Retorno</div>
            <div
              className="stat-value"
              style={{ color: totalPnl >= 0 ? "var(--accent)" : "var(--red)" }}
            >
              {totalPnlPercent >= 0 ? "+" : ""}
              {totalPnlPercent.toFixed(2)}%
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
  );
}
