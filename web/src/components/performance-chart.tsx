"use client";

import { useEffect, useRef } from "react";

interface PerformanceChartProps {
  positions: Array<{
    ticker_symbol: string;
    quantity: number;
    avg_cost_per_share: number;
    current_price: number | null;
  }>;
  currency?: string;
}

export function PerformanceChart({ positions, currency = "BRL" }: PerformanceChartProps) {
  const chartRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!chartRef.current || positions.length === 0) return;

    import("echarts").then((echarts) => {
      const chart = echarts.init(chartRef.current!);

      const tickers = positions.map((p) => p.ticker_symbol);
      const pnlValues = positions.map((p) => {
        const price = p.current_price || p.avg_cost_per_share;
        return Number(((p.quantity * price) - (p.quantity * p.avg_cost_per_share)).toFixed(2));
      });
      const pnlPercents = positions.map((p) => {
        const cost = p.quantity * p.avg_cost_per_share;
        const price = p.current_price || p.avg_cost_per_share;
        const value = p.quantity * price;
        return cost > 0 ? Number((((value - cost) / cost) * 100).toFixed(2)) : 0;
      });

      const option = {
        tooltip: {
          trigger: "axis",
          axisPointer: { type: "shadow" },
          formatter: (params: any) => {
            const idx = params[0].dataIndex;
            const val = new Intl.NumberFormat("pt-BR", { style: "currency", currency }).format(pnlValues[idx]);
            return `<strong>${tickers[idx]}</strong><br/>P&L: ${val}<br/>Retorno: ${pnlPercents[idx]}%`;
          },
        },
        grid: { left: 80, right: 20, top: 20, bottom: 40 },
        xAxis: {
          type: "category",
          data: tickers,
          axisLabel: { color: "#8eaaa0", fontSize: 12 },
          axisLine: { lineStyle: { color: "#25443a" } },
        },
        yAxis: {
          type: "value",
          axisLabel: {
            color: "#8eaaa0",
            fontSize: 11,
            formatter: (v: number) => {
              if (Math.abs(v) >= 1000) return `${(v / 1000).toFixed(0)}k`;
              return String(v);
            },
          },
          splitLine: { lineStyle: { color: "#25443a" } },
          axisLine: { lineStyle: { color: "#25443a" } },
        },
        series: [
          {
            type: "bar",
            data: pnlValues.map((v) => ({
              value: v,
              itemStyle: {
                color: v >= 0 ? "#5ee0a4" : "#ff857f",
                borderRadius: [4, 4, 0, 0],
              },
            })),
            barWidth: "50%",
            label: {
              show: true,
              position: "top",
              formatter: (params: any) => `${pnlPercents[params.dataIndex]}%`,
              color: "#edf7f1",
              fontSize: 11,
            },
          },
        ],
      };

      chart.setOption(option);
      const handleResize = () => chart.resize();
      window.addEventListener("resize", handleResize);

      return () => {
        window.removeEventListener("resize", handleResize);
        chart.dispose();
      };
    });
  }, [positions, currency]);

  if (positions.length === 0) {
    return <div style={{ padding: 40, textAlign: "center", color: "var(--muted)" }}>Sem posições para exibir.</div>;
  }

  return <div ref={chartRef} style={{ height: 300, width: "100%" }} />;
}
