import { WorkspacePage } from "@/components/workspace-page";

export default function MacroPage() {
  return (
    <WorkspacePage
      eyebrow="Macro intelligence · demo"
      title="Regime e séries macro"
      subtitle="Séries BCB/SIDRA preservam data efetiva, publicação, knowledge cutoff e revisão conhecida no as_of."
      metrics={[
        { label: "SELIC", value: "—", note: "dado ausente não vira zero" },
        { label: "IPCA", value: "—", note: "aguardando observação válida" },
        { label: "USD/BRL", value: "—", note: "freshness não confirmada", tone: "warning" },
        { label: "Séries stale", value: "3", note: "alerta de qualidade", tone: "negative" },
      ]}
      sections={[
        {
          title: "Revisões point-in-time",
          status: "Atenção",
          body: "Cada revisão cria nova observação; valores anteriormente conhecidos permanecem reproduzíveis.",
        },
        {
          title: "Cenário base",
          status: "Atenção",
          body: "Nenhum cenário é publicado enquanto séries obrigatórias estiverem stale ou missing.",
        },
        {
          title: "Lineage",
          status: "Saudável",
          body: "Definição da série, transformação, raw object e knowledge_at acompanham cada resultado.",
        },
      ]}
    />
  );
}
