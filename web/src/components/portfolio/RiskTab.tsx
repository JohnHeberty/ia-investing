import type { PortfolioPosition } from "@/hooks/use-portfolios";

interface RiskMetrics {
  maxWeight: number;
  hhi: number;
  top3Weight: number;
}

interface RiskTabProps {
  positions: PortfolioPosition[];
  totalValue: number;
  riskMetrics: RiskMetrics;
}

export function RiskTab({ positions, totalValue, riskMetrics }: RiskTabProps) {
  return (
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
  );
}
