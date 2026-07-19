import { WorkspacePage } from "@/components/workspace-page";

export default function BacktestsPage() {
  return (
    <WorkspacePage
      eyebrow="Backtest lab"
      title="Simulações point-in-time"
      subtitle="Configuração imutável, delay de sinal e execução, custos, impostos e baselines."
      metrics={[
        { label: "Runs concluídos", value: "18", note: "mesmo code version" },
        { label: "PIT gate", value: "100%", note: "anti-look-ahead", tone: "positive" },
        { label: "Sharpe mediano", value: "1,18", note: "out-of-sample" },
        { label: "Reprodutibilidade", value: "18/18", note: "hashes idênticos", tone: "positive" },
      ]}
      sections={[
        {
          title: "Estratégia vs benchmark",
          status: "Saudável",
          body: "Benchmark permanece fora do universo investível e usa série própria.",
        },
        {
          title: "Baselines e ablações",
          status: "Saudável",
          body: "Equal weight, quantitativo sem agents e ablações isolam contribuição incremental.",
        },
        {
          title: "Custos e eventos",
          status: "Atenção",
          body: "Resultados evidenciam efeito de slippage, impostos e corporate actions.",
        },
      ]}
    />
  );
}
