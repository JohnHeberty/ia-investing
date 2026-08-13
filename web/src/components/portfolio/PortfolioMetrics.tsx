import { Metric } from "@/components/domain";

interface PortfolioMetricsProps {
  totalValue: number;
  totalPnl: number;
  totalPnlPercent: number;
  positionsLength: number;
  currency: string;
  isPaper: boolean;
  fmt: Intl.NumberFormat;
}

export function PortfolioMetrics({
  totalValue,
  totalPnl,
  totalPnlPercent,
  positionsLength,
  currency,
  isPaper,
  fmt,
}: PortfolioMetricsProps) {
  return (
    <section className="grid grid-4">
      <Metric
        label="Valor Total"
        value={fmt.format(totalValue)}
        note={`${positionsLength} posições`}
      />
      <Metric
        label="P&L Total"
        value={`${totalPnl >= 0 ? "+" : ""}${fmt.format(totalPnl)}`}
        note={`${totalPnlPercent >= 0 ? "+" : ""}${totalPnlPercent.toFixed(2)}%`}
        tone={totalPnl >= 0 ? "positive" : "warning"}
      />
      <Metric label="Moeda" value={currency} note="Moeda base" />
      <Metric label="Tipo" value={isPaper ? "Paper" : "Live"} note="Ambiente de operação" />
    </section>
  );
}
