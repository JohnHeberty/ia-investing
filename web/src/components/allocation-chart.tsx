"use client";

import { useEchart } from "@/hooks/use-echart";

interface AllocationChartProps {
  positions: Array<{
    ticker_symbol: string;
    quantity: number;
    avg_cost_per_share: number;
    current_price: number | null;
  }>;
  currency?: string;
}

export function AllocationChart({ positions, currency = "BRL" }: AllocationChartProps) {
  const chartRef = useEchart(() => {
    if (positions.length === 0) return null;

    const total = positions.reduce((sum, p) => {
      const price = p.current_price ?? p.avg_cost_per_share;
      return sum + p.quantity * price;
    }, 0);

    if (total <= 0) return null;

    const data = positions.map((p) => {
      const price = p.current_price ?? p.avg_cost_per_share;
      const value = p.quantity * price;
      return { name: p.ticker_symbol, value: Number(value.toFixed(2)) };
    });

    const colors = ["#5ee0a4", "#76b6ff", "#f4bd63", "#ff857f", "#9b59b6", "#1abc9c"];

    return {
      tooltip: {
        trigger: "item",
        formatter: (params: { name: string; value: number; percent: number }) =>
          `${params.name}: ${new Intl.NumberFormat("pt-BR", { style: "currency", currency }).format(params.value)} (${params.percent}%)`,
      },
      color: colors,
      series: [
        {
          type: "pie",
          radius: ["40%", "70%"],
          avoidLabelOverlap: false,
          label: {
            show: true,
            formatter: "{b}: {d}%",
            color: "#edf7f1",
            fontSize: 11,
          },
          emphasis: {
            label: { show: true, fontSize: 14, fontWeight: "bold" },
          },
          data,
        },
      ],
    };
  }, [positions, currency]);

  if (positions.length === 0) {
    return (
      <div style={{ padding: 40, textAlign: "center", color: "var(--muted)" }}>
        Sem posições para exibir.
      </div>
    );
  }

  return <div ref={chartRef} style={{ height: 300, width: "100%" }} />;
}
