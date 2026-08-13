import type { Meta, StoryObj } from "@storybook/nextjs-vite";
import {
  EvidenceTag,
  ConfidenceBar,
  FreshnessPill,
  MandateBadge,
  QualityIndicator,
} from "./evidence-tags";

const meta: Meta = {
  title: "Domain/EvidenceTags",
  component: EvidenceTag,
  tags: ["autodocs"],
};
export default meta;

/* ── EvidenceTag ── */
type EvidenceTagStory = StoryObj<typeof EvidenceTag>;

export const Fact: EvidenceTagStory = {
  args: { kind: "fact", children: "Receita líquida de R$ 42.3bi" },
};
export const Inference: EvidenceTagStory = {
  args: { kind: "inference", children: "Expectativa de crescimento de 8%" },
};
export const Recommendation: EvidenceTagStory = {
  args: { kind: "recommendation", children: "Manter peso neutro" },
};

/* ── ConfidenceBar ── */
type ConfidenceBarStory = StoryObj<typeof ConfidenceBar>;

export const HighConfidence: ConfidenceBarStory = {
  args: { value: 92, label: "Citação" },
  render: (args) => <ConfidenceBar {...args} />,
};
export const MediumConfidence: ConfidenceBarStory = {
  args: { value: 65, label: "Modelo" },
  render: (args) => <ConfidenceBar {...args} />,
};
export const LowConfidence: ConfidenceBarStory = {
  args: { value: 25, label: "Manual" },
  render: (args) => <ConfidenceBar {...args} />,
};
export const Clamped: ConfidenceBarStory = {
  args: { value: 150, label: "Over 100" },
  render: (args) => <ConfidenceBar {...args} />,
};

/* ── FreshnessPill ── */
type FreshnessPillStory = StoryObj<typeof FreshnessPill>;

export const Fresh: FreshnessPillStory = {
  args: { retrievedAt: new Date(Date.now() - 1000 * 60 * 30).toISOString(), maxAgeHours: 24 },
  render: (args) => <FreshnessPill {...args} />,
};
export const HoursOld: FreshnessPillStory = {
  args: { retrievedAt: new Date(Date.now() - 1000 * 60 * 60 * 6).toISOString(), maxAgeHours: 24 },
  render: (args) => <FreshnessPill {...args} />,
};
export const Stale: FreshnessPillStory = {
  args: { retrievedAt: new Date(Date.now() - 1000 * 60 * 60 * 48).toISOString(), maxAgeHours: 24 },
  render: (args) => <FreshnessPill {...args} />,
};

/* ── MandateBadge ── */
type MandateBadgeStory = StoryObj<typeof MandateBadge>;

export const Approved: MandateBadgeStory = {
  args: { status: "approved" },
  render: (args) => <MandateBadge {...args} />,
};
export const PaperLive: MandateBadgeStory = {
  args: { status: "paper_live" },
  render: (args) => <MandateBadge {...args} />,
};
export const Committee: MandateBadgeStory = {
  args: { status: "committee" },
  render: (args) => <MandateBadge {...args} />,
};
export const Simulated: MandateBadgeStory = {
  args: { status: "simulated" },
  render: (args) => <MandateBadge {...args} />,
};
export const Ineligible: MandateBadgeStory = {
  args: { status: "ineligible" },
  render: (args) => <MandateBadge {...args} />,
};

/* ── QualityIndicator ── */
type QualityIndicatorStory = StoryObj<typeof QualityIndicator>;

export const HighQuality: QualityIndicatorStory = {
  args: { score: 97 },
  render: (args) => <QualityIndicator {...args} />,
};
export const MediumQuality: QualityIndicatorStory = {
  args: { score: 75 },
  render: (args) => <QualityIndicator {...args} />,
};
export const LowQuality: QualityIndicatorStory = {
  args: { score: 40 },
  render: (args) => <QualityIndicator {...args} />,
};
