import type { Meta, StoryObj } from "@storybook/react";
import { AsOfIndicator, Badge, Metric, StatePanel, DomainTabs } from "./domain";

const meta: Meta = {
  title: "Domain/Base",
  tags: ["autodocs"],
};
export default meta;

/* ── AsOfIndicator ── */
type AsOfStory = StoryObj<typeof AsOfIndicator>;

export const Current: AsOfStory = {
  args: { value: "19 jul 2026 · 14:30 BRT", freshness: "Atual" },
};
export const StaleIndicator: AsOfStory = {
  args: { value: "17 jul 2026 · 10:00 BRT", freshness: "Stale (48h)" },
};

/* ── Badge ── */
type BadgeStory = StoryObj<typeof Badge>;

export const Neutral: BadgeStory = { args: { children: "Simulado", tone: "neutral" } };
export const Good: BadgeStory = { args: { children: "Aprovada", tone: "good" } };
export const Warn: BadgeStory = { args: { children: "Atenção", tone: "warn" } };
export const Bad: BadgeStory = { args: { children: "Inelegível", tone: "bad" } };

/* ── Metric ── */
type MetricStory = StoryObj<typeof Metric>;

export const NAVMetric: MetricStory = {
  args: { label: "NAV Total", value: "R$ 142.8bi", note: "+2,3% no mês", tone: "positive" },
};
export const RiskMetric: MetricStory = {
  args: { label: "VaR 95%", value: "3,2%", note: "Dentro do limite de 5%", tone: "" },
};
export const NegativeMetric: MetricStory = {
  args: { label: "Drawdown", value: "-8,4%", note: "Máx. histórico: -12%", tone: "negative" },
};

/* ── StatePanel ── */
type StatePanelStory = StoryObj<typeof StatePanel>;

export const DefaultPanel: StatePanelStory = {
  args: { title: "Dados carregados", detail: "Todos os filtros aplicados com sucesso.", state: "empty" },
};
export const ErrorPanel: StatePanelStory = {
  args: { title: "Erro de conexão", detail: "O serviço de dados está indisponível.", state: "error" },
};
export const StalePanel: StatePanelStory = {
  args: { title: "Dados desatualizados", detail: "Última atualização há 48 horas.", state: "stale" },
};

/* ── DomainTabs ── */
type TabsStory = StoryObj<typeof DomainTabs>;

export const PortfolioTabs: TabsStory = {
  args: {
    label: "Visão da carteira",
    tabs: [
      { id: "overview", label: "Visão geral", content: <p>Conteúdo da visão geral.</p> },
      { id: "positions", label: "Posições", content: <p>Lista de posições atuais.</p> },
      { id: "risk", label: "Risco", content: <p>Métricas de risco.</p> },
      { id: "audit", label: "Auditoria", content: <p>Histórico de alterações.</p> },
    ],
  },
};
