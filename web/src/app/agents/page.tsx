import { WorkspacePage } from "@/components/workspace-page";

export default function AgentsPage() {
  return (
    <WorkspacePage
      eyebrow="Agent operations"
      title="Runtime governado"
      subtitle="Runs fixam prompt, schema, modelo, tools, budget e knowledge cutoff."
      metrics={[
        { label: "Runs hoje", value: "146", note: "6 capabilities" },
        { label: "Schema pass", value: "100%", note: "últimos 7 dias", tone: "positive" },
        { label: "Guardrail trips", value: "4", note: "falharam fechados", tone: "warning" },
        { label: "Custo", value: "US$ 18,42", note: "tokens atribuídos" },
      ]}
      sections={[
        {
          title: "Versions e evals",
          status: "Saudável",
          body: "Versões ativas passaram pelos thresholds de schema e citation coverage.",
        },
        {
          title: "Tool calls",
          status: "Saudável",
          body: "Allowlist, argumentos sanitizados, custo e duração permanecem vinculados ao run.",
        },
        {
          title: "Approvals",
          status: "Atenção",
          body: "Dois commands sensíveis aguardam decisão humana independente.",
        },
      ]}
    />
  );
}
