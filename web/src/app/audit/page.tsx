import { WorkspacePage } from "@/components/workspace-page";

export default function AuditPage() {
  return (
    <WorkspacePage
      eyebrow="Audit trail"
      title="Linha do tempo verificável"
      subtitle="Atores, versões, hashes, razões e correlation IDs sem payload sensível em claro."
      metrics={[
        { label: "Eventos hoje", value: "2.481", note: "append-only" },
        { label: "Correlacionados", value: "100%", note: "workflow e domínio", tone: "positive" },
        { label: "Overrides", value: "1", note: "expiração registrada", tone: "warning" },
        { label: "Falhas de integridade", value: "0", note: "últimos 30 dias", tone: "positive" },
      ]}
      sections={[
        {
          title: "Pesquisa",
          status: "Saudável",
          body: "Cases, claims, evidence, reviews e teses preservam before/after hashes.",
        },
        {
          title: "Carteiras",
          status: "Saudável",
          body: "Mandatos, proposals, decisões e NAV revisions são rastreáveis por organização.",
        },
        {
          title: "Agents e dados",
          status: "Saudável",
          body: "Artefatos imutáveis, tool calls e incidentes mantêm versões originais.",
        },
      ]}
    />
  );
}
