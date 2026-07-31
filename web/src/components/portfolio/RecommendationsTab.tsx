import { Fragment, useState } from "react";
import { Badge, StatePanel } from "@/components/domain";
import type { PortfolioRecommendations } from "@/hooks/use-portfolios";

const SCORE_DIMENSIONS = [
  { key: "fundamental", label: "Fundamental" },
  { key: "momentum", label: "Momentum" },
  { key: "valuation", label: "Valuation" },
  { key: "risk", label: "Risco" },
  { key: "analyst", label: "Analistas" },
  { key: "leverage", label: "Alavanc." },
  { key: "growth", label: "Crescim." },
  { key: "liquidity", label: "Liquidez" },
  { key: "earnings", label: "Earnings" },
] as const;

function scoreColor(score: number): string {
  if (score >= 0.65) return "good";
  if (score >= 0.45) return "neutral";
  return "bad";
}

function ScoreBar({ label, score }: { label: string; score: number }) {
  const pct = Math.round(score * 100);
  const tone = scoreColor(score);
  const color =
    tone === "good" ? "var(--accent)" : tone === "warn" ? "var(--amber)" : "var(--red)";
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 11 }}>
      <span style={{ width: 56, color: "var(--muted)", textAlign: "right" }}>{label}</span>
      <div
        style={{
          flex: 1,
          height: 6,
          borderRadius: 3,
          background: "var(--surface-2)",
          overflow: "hidden",
        }}
      >
        <div
          style={{
            width: `${pct}%`,
            height: "100%",
            background: color,
            borderRadius: 3,
            transition: "width 0.3s",
          }}
        />
      </div>
      <span style={{ width: 28, fontFamily: "var(--font-mono)", fontSize: 10 }}>{pct}%</span>
    </div>
  );
}

interface RecommendationsTabProps {
  recommendations: PortfolioRecommendations | null;
}

export function RecommendationsTab({ recommendations }: RecommendationsTabProps) {
  const [expandedTicker, setExpandedTicker] = useState<string | null>(null);

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
              <div key={i} style={{ fontSize: 12, color: "var(--amber)" }}>{risk}</div>
            ))}
          </div>
        )}
        {recommendations.llm_analysis && (
          <div className="mt-12" style={{ padding: "12px 16px", background: "var(--surface-2)", borderRadius: 8, borderLeft: "3px solid var(--accent)" }}>
            <div style={{ fontSize: 11, fontWeight: 500, color: "var(--accent)", marginBottom: 4 }}>Análise IA</div>
            <div style={{ fontSize: 13, lineHeight: 1.5, color: "var(--text)" }}>{recommendations.llm_analysis}</div>
          </div>
        )}
      </div>

      <div className="card card-pad">
        <div className="card-title">
          <h2>Recomendações por Ativo</h2>
          <span style={{ fontSize: 11, color: "var(--muted)" }}>Clique para ver scores detalhados</span>
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
              <Fragment key={rec.ticker}>
                <tr
                  onClick={() => setExpandedTicker(expandedTicker === rec.ticker ? null : rec.ticker)}
                  style={{ cursor: "pointer" }}
                >
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
                {expandedTicker === rec.ticker && (
                  <tr key={`${rec.ticker}-detail`}>
                    <td colSpan={7} style={{ padding: "12px 16px", background: "var(--surface-2)" }}>
                      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
                        <div>
                          <div style={{ fontSize: 11, fontWeight: 500, marginBottom: 8, color: "var(--muted)" }}>Scores por Dimensão (9)</div>
                          <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                            {rec.scores && SCORE_DIMENSIONS.map(({ key, label }) => (
                              <ScoreBar key={key} label={label} score={rec.scores![key] ?? 0.5} />
                            ))}
                          </div>
                        </div>
                        <div>
                          {rec.llm_analysis ? (
                            <div>
                              <div style={{ fontSize: 11, fontWeight: 500, marginBottom: 8, color: "var(--accent)" }}>Análise IA</div>
                              <div style={{ fontSize: 12, lineHeight: 1.5, color: "var(--text)" }}>{rec.llm_analysis}</div>
                            </div>
                          ) : (
                            <div style={{ fontSize: 12, color: "var(--muted)", fontStyle: "italic" }}>
                              Análise IA indisponível (gateway off-line)
                            </div>
                          )}
                        </div>
                      </div>
                    </td>
                  </tr>
                )}
              </Fragment>            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
