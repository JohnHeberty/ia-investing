import { WorkspacePage } from "@/components/workspace-page";

export default function CommitteePage() {
  return (
    <WorkspacePage
      eyebrow="Committee room"
      title="Agenda de decisões"
      subtitle="Decision packs congelados, quórum, dissenso, condições e assinaturas verificáveis."
      metrics={[
        { label: "Na agenda", value: "3", note: "2 aprovações · 1 revisão" },
        { label: "Quórum confirmado", value: "4/5", note: "mínimo 3" },
        { label: "Conflitos declarados", value: "1", note: "membro impedido", tone: "warning" },
        { label: "Decisões hoje", value: "2", note: "assinadas" },
      ]}
      sections={[
        {
          title: "Decision pack",
          status: "Saudável",
          body: "Tese, valuation, risco, proposta e evidence hashes foram congelados na versão submetida.",
        },
        {
          title: "Votos e dissenso",
          status: "Atenção",
          body: "Um voto condicionado requer limite adicional de concentração antes da ativação paper.",
        },
        {
          title: "Four-eyes",
          status: "Saudável",
          body: "Autores não podem aprovar a própria proposta e votos após encerramento são rejeitados.",
        },
      ]}
    />
  );
}
