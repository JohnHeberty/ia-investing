"use client";

import { useEffect, useRef } from "react";

declare global {
  interface HTMLDivElement {
    __echartsCleanup?: () => void;
  }
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type EChartOption = Record<string, any>;

let echartsMod: typeof import("echarts") | null = null;

async function getEcharts() {
  if (!echartsMod) {
    echartsMod = await import("echarts");
  }
  return echartsMod;
}

/**
 * Shared hook for ECharts with proper synchronous cleanup.
 * No memory leaks: chart is disposed and resize listener removed on every unmount/update.
 */
export function useEchart(buildOption: () => EChartOption | null, deps: unknown[]) {
  const chartRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = chartRef.current;
    if (!el) return;

    const option = buildOption();
    if (!option) return;

    let disposed = false;

    getEcharts().then((mod) => {
      if (disposed || !el) return;

      const chart = mod.init(el);
      chart.setOption(option);

      const handleResize = () => chart.resize();
      window.addEventListener("resize", handleResize);

      el.__echartsCleanup = () => {
        window.removeEventListener("resize", handleResize);
        chart.dispose();
      };
    }).catch((err: unknown) => {
      console.error("[useEchart] Failed to load echarts:", err);
    });

    return () => {
      disposed = true;
      el.__echartsCleanup?.();
      el.__echartsCleanup = undefined;
    };
  }, deps);

  return chartRef;
}
