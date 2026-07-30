"use client";

import { useEffect, useRef } from "react";

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
  const chartRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!chartRef.current || positions.length === 0) return;

    // Dynamic import echarts
    import("echarts").then((echarts) => {
      const chart = echarts.init(chartRef.current!);

      // Calculate values
      const data = positions.map((pos) => {
        const price = pos.current_price || pos.avg_cost_per_share;
        return {
          name: pos.ticker_symbol,
          value: pos.quantity * price,
        };
      });

      const total = data.reduce((sum, item) => sum + item.value, 0);

      const option = {
        tooltip: {
          trigger: "item",
          formatter: (params: any) => {
            const value = new Intl.NumberFormat("pt-BR", {
              style: "currency",
              currency,
            }).format(params.value);
            const percent = ((params.value / total) * 100).toFixed(1);
            return `<strong>${params.name}</strong><br/>${value} (${percent}%)`;
          },
        },
        series: [
          {
            type: "pie",
            radius: ["40%", "70%"],
            avoidLabelOverlap: false,
            itemStyle: {
              borderRadius: 10,
              borderColor: "#0d1916",
              borderWidth: 2,
            },
            label: {
              show: true,
              formatter: "{b}\n{d}%",
              fontSize: 11,
              color: "#edf7f1",
            },
            emphasis: {
              label: {
                show: true,
                fontSize: 14,
                fontWeight: "bold",
              },
            },
            data: data.map((item, index) => ({
              ...item,
              itemStyle: {
                color: ["#5ee0a4", "#76b6ff", "#f4bd63", "#ff857f", "#9b59b6", "#1abc9c"][index % 6],
              },
            })),
          },
        ],
      };

      chart.setOption(option);

      // Cleanup
      return () => {
        chart.dispose();
      };
    });
  }, [positions, currency]);

  if (positions.length === 0) {
    return (
      <div className="card card-pad">
        <div className="card-title">
          <h2>Alocação</h2>
        </div>
        <div style={{ padding: 40, textAlign: "center", color: "var(--muted)" }}>
          Adicione posições para ver o gráfico de alocação.
        </div>
      </div>
    );
  }

  return (
    <div className="card card-pad">
      <div className="card-title">
        <h2>Alocação</h2>
      </div>
      <div ref={chartRef} style={{ height: 300, width: "100%" }} />
    </div>
  );
}
