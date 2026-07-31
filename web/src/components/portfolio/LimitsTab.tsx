import { Badge } from "@/components/domain";
import { useRiskPolicies } from "@/hooks/use-risk-overview";

interface RiskMetrics {
  maxWeight: number;
  hhi: number;
  top3Weight: number;
}

interface LimitsTabProps {
  riskMetrics: RiskMetrics;
  positionsLength: number;
}

const DEFAULT_LIMITS = {
  max_single_position: 0.25,
  max_hhi: 0.25,
  max_positions: 20,
};

function resolveLimit(limits: Record<string, unknown>, key: string, defaultVal: number): number {
  const val = limits[key];
  if (typeof val === "number") return val;
  if (typeof val === "string") {
    const parsed = parseFloat(val);
    if (!isNaN(parsed)) return parsed;
  }
  return defaultVal;
}

export function LimitsTab({ riskMetrics, positionsLength }: LimitsTabProps) {
  const { policies } = useRiskPolicies();

  const activePolicy = policies.find((p) => p.status === "active") ?? policies[0];
  const limits = activePolicy?.limits ?? {};

  const maxPosLimit = resolveLimit(limits, "max_single_position", DEFAULT_LIMITS.max_single_position);
  const hhiLimit = resolveLimit(limits, "max_hhi", DEFAULT_LIMITS.max_hhi);
  const maxPositions = resolveLimit(limits, "max_positions", DEFAULT_LIMITS.max_positions);

  const rows = [
    {
      name: "Concentração por Ativo",
      current: riskMetrics.maxWeight,
      limit: maxPosLimit,
      format: (v: number) => `${(v * 100).toFixed(1)}%`,
      limitFormat: (v: number) => `${(v * 100).toFixed(0)}%`,
    },
    {
      name: "HHI",
      current: riskMetrics.hhi,
      limit: hhiLimit,
      format: (v: number) => `${(v * 10000).toFixed(0)}`,
      limitFormat: (v: number) => `${(v * 10000).toFixed(0)}`,
    },
    {
      name: "Número de Posições",
      current: positionsLength,
      limit: maxPositions,
      format: (v: number) => String(v),
      limitFormat: (v: number) => String(v),
    },
  ];

  return (
    <div className="card card-pad">
      <div className="card-title">
        <h2>Limites de Risco</h2>
        {activePolicy && (
          <Badge tone="neutral">Policy v{activePolicy.version}</Badge>
        )}
      </div>
      {activePolicy && (
        <p style={{ fontSize: 11, color: "var(--muted)", marginTop: 4 }}>
          Methodology: {activePolicy.methodology_version}
        </p>
      )}
      {!activePolicy && (
        <p style={{ fontSize: 11, color: "var(--amber)", marginTop: 4 }}>
          Nenhuma policy configurada — usando limites padrão. Configure em Risk → Policies.
        </p>
      )}
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
          {rows.map((row) => {
            const violated = row.current > row.limit;
            return (
              <tr key={row.name}>
                <td style={{ fontWeight: 500 }}>{row.name}</td>
                <td style={{ fontFamily: "var(--font-mono)", color: violated ? "var(--red)" : undefined }}>
                  {row.format(row.current)}
                </td>
                <td style={{ fontFamily: "var(--font-mono)", color: "var(--muted)" }}>
                  {row.limitFormat(row.limit)}
                </td>
                <td>
                  <Badge tone={violated ? "bad" : "good"}>
                    {violated ? "Violação" : "OK"}
                  </Badge>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
