import type { Meta, StoryObj } from "@storybook/nextjs-vite";
import { WorkspacePage } from "./workspace-page";

const meta: Meta<typeof WorkspacePage> = {
  title: "Layout/WorkspacePage",
  component: WorkspacePage,
  tags: ["autodocs"],
};
export default meta;

type Story = StoryObj<typeof WorkspacePage>;

export const MissionControl: Story = {
  args: {
    eyebrow: "Missão",
    title: "Mission Control",
    subtitle: "Visão consolidada do portfólio institucional",
    metrics: [
      { label: "NAV Total", value: "R$ 142,8bi", note: "+2,3% no mês", tone: "positive" },
      { label: "Retorno esperado", value: "14,2%", note: "12m forward" },
      { label: "Risco ativo", value: "3,8%", note: "Dentro do limite" },
      { label: "Saúde evidências", value: "92%", note: "Citação coverage" },
    ],
    sections: [
      {
        title: "Top Carteiras",
        status: "Saudável",
        body: "Ranking consolidado por categoria. Aurora Quality lidera com Sharpe 1.42.",
      },
      {
        title: "Eventos Críticos",
        status: "Atenção",
        body: "3 materiais pendentes: aprovação rebalance, waiver concentração, atualização tese.",
      },
      {
        title: "Funil de Pesquisa",
        body: "12 oportunidades ativas, 4 com alta materialidade, 2 aguardando valuation.",
      },
    ],
  },
};
