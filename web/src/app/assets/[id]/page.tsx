import { WorkspacePage } from "@/components/workspace-page";

export default function AssetPage() {
  return (
    <WorkspacePage
      eyebrow="Asset 360"
      title="VALE3 · Vale ON"
      subtitle="B3 · NM · instrumento e listagem válidos no as_of selecionado"
      metrics={[
        { label: "Valor justo", value: "R$ 78,40", note: "DCF ponderado · v4", tone: "positive" },
        { label: "Preço observado", value: "R$ 64,12", note: "fechamento B3" },
        { label: "Margem de segurança", value: "22,3%", note: "cenário base", tone: "positive" },
        { label: "Evidence coverage", value: "100%", note: "18 claims materiais" },
      ]}
      sections={[
        {
          title: "Métricas e provenance",
          status: "Saudável",
          body: "Receita, dívida, margens e caixa exibem definição, linhagem de fatos, status e knowledge cutoff.",
        },
        {
          title: "Tese e valuation",
          status: "Saudável",
          body: "A versão ativa liga assumptions aprovadas, cenários bear/base/bull e gatilhos de invalidação.",
        },
        {
          title: "Eventos e política",
          status: "Atenção",
          body: "Mudança regulatória em consulta pública está separada de norma vigente e aguarda corroboration.",
        },
      ]}
    />
  );
}
