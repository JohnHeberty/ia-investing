import { Badge, StatePanel } from "@/components/domain";
import type { PortfolioRecommendations } from "@/hooks/use-portfolios";

interface RecommendationsTabProps {
  recommendations: PortfolioRecommendations | null;
}

export function RecommendationsTab({ recommendations }: RecommendationsTabProps) {
  if (!recommendations) {
    return (
      <StatePanel
        title="Recomendações dos Agents"
        detail="Recomendações de compra, venda e rebalanceamento geradas pelos agents de IA serão exibidas aqui."
      />
    );
  }

  return (
    <div>
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
    </div>
  );
}
