import { WorkspacePage } from "@/components/workspace-page";

export default function RiskPage() {
  return (
    <WorkspacePage
      eyebrow="Risk center"
      title="Risco institucional"
      subtitle="Limites, exposures, stress e waivers por snapshot e policy versionada."
      metrics={[
        { label: "Hard breaches", value: "1", note: "bloqueia proposta", tone: "negative" },
        { label: "Soft breaches", value: "2", note: "requer justificativa", tone: "warning" },
        { label: "VaR agregado", value: "2,8%", note: "1 dia · 99%" },
        { label: "Waivers ativos", value: "1", note: "expira em 3 dias" },
      ]}
      sections={[
        {
          title: "Concentração",
          status: "Atenção",
          body: "Uma exposição setorial ultrapassou o soft limit; o hard limit permanece preservado.",
        },
        {
          title: "Liquidez",
          status: "Saudável",
          body: "97% da carteira é liquidável dentro da janela definida pelo mandato.",
        },
        {
          title: "Stress scenarios",
          status: "Saudável",
          body: "Choques de juros, câmbio e commodities são reproduzíveis pelo snapshot de inputs.",
        },
      ]}
    />
  );
}
