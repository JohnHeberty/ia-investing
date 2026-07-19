import { DomainTabs, StatePanel } from "@/components/domain";
import { WorkspacePage } from "@/components/workspace-page";

export default function PortfolioPage() {
  return (
    <>
      <WorkspacePage
        eyebrow="Portfolio 360"
        title="Aurora Quality"
        subtitle="Carteira-modelo long only · versão 12 aprovada · mandato BR-QUALITY v3"
        metrics={[
          { label: "NAV reconciliado", value: "R$ 18,7 mi", note: "metodologia nav-v1" },
          {
            label: "Retorno esperado",
            value: "18,4%",
            note: "cenário ponderado",
            tone: "positive",
          },
          { label: "Volatilidade", value: "11,2%", note: "modelo risk-v2" },
          { label: "Caixa", value: "4,8%", note: "mandato 2–10%" },
        ]}
        sections={[
          {
            title: "Posições e performance",
            status: "Saudável",
            body: "14 posições resolvidas pelo instrumento e preço point-in-time. NAV, benchmark e atribuição usam o mesmo snapshot.",
          },
          {
            title: "Risco e stress",
            status: "Saudável",
            body: "Nenhum hard breach aberto. Stress de juros e commodities permanece dentro do risk budget aprovado.",
          },
          {
            title: "Teses e rebalanceamento",
            status: "Atenção",
            body: "Duas teses vencem em sete dias. A proposta seguinte permanece bloqueada até revisão independente.",
          },
        ]}
      />
      <DomainTabs
        label="Detalhes da carteira"
        tabs={[
          {
            id: "positions",
            label: "Posições",
            content: (
              <StatePanel title="14 posições" detail="Snapshot point-in-time reconciliado." />
            ),
          },
          {
            id: "performance",
            label: "Performance",
            content: (
              <StatePanel
                title="NAV e benchmark"
                detail="Metodologia nav-v1, mesma moeda e mesmo cutoff."
              />
            ),
          },
          {
            id: "risk",
            label: "Risco",
            content: (
              <StatePanel
                title="Sem hard breach"
                detail="Limites e stresses calculados no backend."
              />
            ),
          },
          {
            id: "theses",
            label: "Teses",
            content: (
              <StatePanel
                state="stale"
                title="Duas revisões pendentes"
                detail="Nova proposta permanece bloqueada."
              />
            ),
          },
          {
            id: "audit",
            label: "Auditoria",
            content: (
              <StatePanel
                title="Lineage disponível"
                detail="Mandato, snapshots, decisão e publicação vinculados."
              />
            ),
          },
        ]}
      />
    </>
  );
}
