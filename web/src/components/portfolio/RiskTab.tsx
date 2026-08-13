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

function computePortfolioStats(positions: PortfolioPosition[], totalValue: number) {
  const weights = positions.map((p) => {
    const price = p.current_price ?? p.avg_cost_per_share;
    return totalValue > 0 ? (p.quantity * price) / totalValue : 0;
  });

  const sectorMap: Record<string, number> = {};
  positions.forEach((p) => {
    const sector = ((p as unknown as Record<string, unknown>)["sector"] as string) || "Outro";
    const price = p.current_price ?? p.avg_cost_per_share;
    const val = totalValue > 0 ? (p.quantity * price) / totalValue : 0;
    sectorMap[sector] = (sectorMap[sector] || 0) + val;
  });

  return { weights, sectorMap };
}

export function RiskTab({ positions, totalValue, riskMetrics }: RiskTabProps) {
  const { sectorMap } = computePortfolioStats(positions, totalValue);

  return (
    <div>
      <div className="card card-pad mb-16">
        <div className="card-title">
          <h2>Métricas de Risco</h2>
        </div>
        <div className="stat-grid">
          <div>
            <div className="stat-label">HHI (Concentração)</div>
            <div className="stat-value">{(riskMetrics.hhi * 10000).toFixed(0)}</div>
            <div
              className="stat-detail"
              style={{
                color:
                  riskMetrics.hhi > 0.25
                    ? "var(--red)"
                    : riskMetrics.hhi > 0.15
                      ? "var(--amber)"
                      : "var(--accent)",
              }}
            >
              {riskMetrics.hhi > 0.25
                ? "Alta concentração"
                : riskMetrics.hhi > 0.15
                  ? "Concentração moderada"
                  : "Diversificada"}
            </div>
          </div>
          <div>
            <div className="stat-label">Maior Posição</div>
            <div className="stat-value">{(riskMetrics.maxWeight * 100).toFixed(1)}%</div>
            <div
              className="stat-detail"
              style={{ color: riskMetrics.maxWeight > 0.25 ? "var(--red)" : "var(--accent)" }}
            >
              {riskMetrics.maxWeight > 0.25 ? "Acima do limite (25%)" : "Dentro do limite"}
            </div>
          </div>
          <div>
            <div className="stat-label">Top 3 Posições</div>
            <div className="stat-value">{(riskMetrics.top3Weight * 100).toFixed(1)}%</div>
            <div
              className="stat-detail"
              style={{ color: riskMetrics.top3Weight > 0.7 ? "var(--red)" : "var(--accent)" }}
            >
              {riskMetrics.top3Weight > 0.7 ? "Concentrado" : "Balanceado"}
            </div>
          </div>
          <div>
            <div className="stat-label">Diversificação</div>
            <div className="stat-value">{Object.keys(sectorMap).length}</div>
            <div className="stat-detail">
              {Object.keys(sectorMap).length > 1 ? "setores" : "setor"}
            </div>
          </div>
        </div>
      </div>

      {Object.keys(sectorMap).length > 1 && (
        <div className="card card-pad mb-16">
          <div className="card-title">
            <h2>Exposição por Setor</h2>
          </div>
          <div className="mt-12">
            {Object.entries(sectorMap)
              .sort((a, b) => b[1] - a[1])
              .map(([sector, weight]) => (
                <div key={sector} className="exposure-bar">
                  <span style={{ width: 100, fontWeight: 500, fontSize: 12 }}>{sector}</span>
                  <div className="bar-track">
                    <div
                      className={`bar-fill ${weight > 0.3 ? "high" : weight > 0.15 ? "mid" : "low"}`}
                      style={{ width: `${Math.min(weight * 100, 100)}%` }}
                    />
                  </div>
                  <span
                    style={{
                      width: 50,
                      textAlign: "right",
                      fontSize: 12,
                      fontFamily: "var(--font-mono)",
                    }}
                  >
                    {(weight * 100).toFixed(1)}%
                  </span>
                </div>
              ))}
          </div>
        </div>
      )}

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
              const costBasis = pos.quantity * pos.avg_cost_per_share;
              const pnl = value - costBasis;
              const pnlPct = costBasis > 0 ? (pnl / costBasis) * 100 : 0;
              return (
                <div
                  key={pos.id}
                  style={{
                    marginBottom: 8,
                    padding: "8px 12px",
                    background: "var(--surface-2)",
                    borderRadius: 8,
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                      marginBottom: 4,
                    }}
                  >
                    <span style={{ fontWeight: 600 }}>{pos.ticker_symbol}</span>
                    <span style={{ fontFamily: "var(--font-mono)", fontSize: 12 }}>
                      {weight.toFixed(1)}%
                    </span>
                  </div>
                  <div className="exposure-bar" style={{ marginBottom: 0 }}>
                    <span style={{ width: 60, fontSize: 11, color: "var(--muted)" }}>Peso</span>
                    <div className="bar-track">
                      <div
                        className={`bar-fill ${weight > 25 ? "high" : weight > 15 ? "mid" : "low"}`}
                        style={{ width: `${Math.min(weight, 100)}%` }}
                      />
                    </div>
                    <span
                      style={{
                        width: 50,
                        textAlign: "right",
                        fontSize: 11,
                        color: pnlPct >= 0 ? "var(--accent)" : "var(--red)",
                      }}
                    >
                      {pnlPct >= 0 ? "+" : ""}
                      {pnlPct.toFixed(1)}%
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <p style={{ color: "var(--muted)", fontSize: 13, padding: 16 }}>
            Sem posições para exibir exposição.
          </p>
        )}
      </div>
    </div>
  );
}
