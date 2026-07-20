import type { Meta, StoryObj } from "@storybook/react";
import {
  PortfolioDiff,
  ScenarioWaterfall,
  ApprovalCard,
  type DiffEntry,
  type ScenarioEntry,
} from "./decision-components";

const meta: Meta = {
  title: "Domain/DecisionComponents",
  tags: ["autodocs"],
};
export default meta;

/* ── PortfolioDiff ── */
type DiffStory = StoryObj<typeof PortfolioDiff>;

const sampleEntries: DiffEntry[] = [
  { ticker: "PETR4", name: "Petrobras ON", currentWeight: 12.5, targetWeight: 15.0, action: "buy" },
  { ticker: "VALE3", name: "Vale ON", currentWeight: 10.2, targetWeight: 8.0, action: "sell" },
  { ticker: "ITUB4", name: "Itaú Unibanco ON", currentWeight: 9.8, targetWeight: 9.8, action: "hold" },
  { ticker: "WEGE3", name: "WEG ON", currentWeight: 0, targetWeight: 5.0, action: "new" },
  { ticker: "ABEV3", name: "Ambev ON", currentWeight: 6.0, targetWeight: 0, action: "exit" },
];

export const RebalanceTable: DiffStory = {
  args: { entries: sampleEntries },
};

/* ── ScenarioWaterfall ── */
type WaterfallStory = StoryObj<typeof ScenarioWaterfall>;

const sampleScenarios: ScenarioEntry[] = [
  { name: "Base", impact: 0.12, cumulative: 0.12 },
  { name: "Choque Selic +200bp", impact: -0.045, cumulative: 0.075 },
  { name: "Desaceleração China", impact: -0.032, cumulative: 0.043 },
  { name: "Risco político", impact: -0.02, cumulative: 0.023 },
  { name: "Volatilidade FX", impact: -0.015, cumulative: 0.008 },
];

export const RiskWaterfall: WaterfallStory = {
  args: { scenarios: sampleScenarios },
};

/* ── ApprovalCard ── */
type ApprovalStory = StoryObj<typeof ApprovalCard>;

export const Pending: ApprovalStory = {
  args: {
    title: "Rebalanceamento Q3 — Aurora Quality",
    description: "Aumentar exposição em PETR4 de 12.5% para 15.0% conforme tese de valor intrínseco.",
    status: "pending",
    requestedBy: "Maria Silva (Portfolio Manager)",
    requestedAt: "19/07/2026 09:30",
  },
};

export const Approved: ApprovalStory = {
  args: {
    title: "Rebalanceamento Q3 — Aurora Quality",
    description: "Aumentar exposição em PETR4 de 12.5% para 15.0%.",
    status: "approved",
    requestedBy: "Maria Silva (Portfolio Manager)",
    requestedAt: "19/07/2026 09:30",
    decidedBy: "João Santos (Risk Committee)",
    decidedAt: "19/07/2026 14:15",
    reason: "Tese fundamentada com citation coverage > 90%",
  },
};

export const Rejected: ApprovalStory = {
  args: {
    title: "Solicitação de waiver — Limite de concentração",
    description: "Exceder limite de concentração setorial em 3%.",
    status: "rejected",
    requestedBy: "Pedro Costa (Analyst)",
    requestedAt: "18/07/2026 16:00",
    decidedBy: "Ana Lima (Risk)",
    decidedAt: "19/07/2026 10:00",
    reason: "Risco de concentração inaceitável para o mandato.",
  },
};

export const Conditional: ApprovalStory = {
  args: {
    title: "Nova posição WEGE3",
    description: "Incluir WEGE3 com peso de 5% sujeito a aprovação de valuation.",
    status: "conditional",
    requestedBy: "Maria Silva (Portfolio Manager)",
    requestedAt: "19/07/2026 11:00",
    conditions: [
      "Valuation revisado com citation coverage ≥ 80%",
      "Aprovação de risk antes da execução",
      "Limite de turnover mensal respeitado",
    ],
  },
};
