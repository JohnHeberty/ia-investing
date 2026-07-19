import { WorkspacePage } from "@/components/workspace-page";

export default function OpportunitiesPage() {
  return (
    <WorkspacePage
      eyebrow="Research funnel"
      title="Oportunidades"
      subtitle="Triagem auditável por origem, materialidade e evidência disponível."
      metrics={[
        { label: "Novas", value: "28", note: "últimos 7 dias" },
        { label: "Alta materialidade", value: "6", note: "requer revisão", tone: "warning" },
        { label: "Casos abertos", value: "11", note: "sem duplicidade" },
        { label: "Convertidas", value: "39%", note: "janela de 30 dias" },
      ]}
      sections={[
        {
          title: "Sinais fundamentais",
          status: "Saudável",
          body: "Mudanças de métricas e valuation são calculadas sobre dados point-in-time.",
        },
        {
          title: "Eventos corporativos",
          status: "Atenção",
          body: "Fatos relevantes são deduplicados e classificados antes da abertura de caso.",
        },
        {
          title: "Macro e política",
          status: "Saudável",
          body: "Impactos mostram mecanismo, horizonte, confidence e fontes oficiais.",
        },
      ]}
    />
  );
}
