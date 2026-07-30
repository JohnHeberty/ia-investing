import { Badge } from "@/components/domain";

interface RiskMetrics {
  maxWeight: number;
  hhi: number;
  top3Weight: number;
}

interface LimitsTabProps {
  riskMetrics: RiskMetrics;
  positionsLength: number;
}

export function LimitsTab({ riskMetrics, positionsLength }: LimitsTabProps) {
  return (
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
            <td style={{ fontFamily: "var(--font-mono)" }}>{positionsLength}</td>
            <td>20</td>
            <td>
              <Badge tone={positionsLength > 20 ? "bad" : "good"}>
                {positionsLength > 20 ? "Violação" : "OK"}
              </Badge>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  );
}
