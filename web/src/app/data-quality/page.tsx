import { WorkspacePage } from "@/components/workspace-page";

export default function DataQualityPage() {
  return (
    <WorkspacePage
      eyebrow="Data quality center"
      title="Confiança dos dados"
      subtitle="Freshness, completude, quarentena e incidentes sem edição direta de fatos."
      metrics={[
        { label: "Fontes saudáveis", value: "12/14", note: "SLAs dentro da janela" },
        { label: "Incidentes abertos", value: "3", note: "1 material", tone: "warning" },
        { label: "Quarentena", value: "8 objetos", note: "isolados do domínio" },
        { label: "Lineage coverage", value: "99,6%", note: "métricas canônicas", tone: "positive" },
      ]}
      sections={[
        {
          title: "Source registry",
          status: "Atenção",
          body: "Uma fonte macro excedeu freshness e outra está em shadow ingestion.",
        },
        {
          title: "Fatos e métricas",
          status: "Saudável",
          body: "Missing e parse_error permanecem explícitos; zero só representa valor reportado.",
        },
        {
          title: "Incidentes",
          status: "Saudável",
          body: "Transitions exigem autorização, razão, auditoria e waiver com expiração.",
        },
      ]}
    />
  );
}
