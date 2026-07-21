import type { Meta, StoryObj } from "@storybook/nextjs-vite";
import {
  DataStatePanel,
  LoadingSkeleton,
  StaleWarning,
  PartialDataIndicator,
} from "./data-state-components";

const meta: Meta = {
  title: "Domain/DataStates",
  tags: ["autodocs"],
};
export default meta;

/* ── DataStatePanel ── */
type PanelStory = StoryObj<typeof DataStatePanel>;

export const EmptyState: PanelStory = {
  args: { state: "empty" },
};
export const MissingState: PanelStory = {
  args: { state: "missing" },
};
export const StaleState: PanelStory = {
  args: { state: "stale" },
};
export const PartialState: PanelStory = {
  args: { state: "partial" },
};
export const QuarantinedState: PanelStory = {
  args: { state: "quarantined" },
};
export const ForbiddenState: PanelStory = {
  args: { state: "forbidden" },
};
export const ErrorState: PanelStory = {
  args: { state: "error" },
};
export const CustomTitle: PanelStory = {
  args: {
    state: "stale",
    title: "Dados de risco desatualizados",
    detail: "O último cálculo de VaR foi há 72 horas. Solicite recálculo.",
  },
};

/* ── LoadingSkeleton ── */
type SkeletonStory = StoryObj<typeof LoadingSkeleton>;

export const DefaultSkeleton: SkeletonStory = {
  args: { lines: 3 },
};
export const ManyLines: SkeletonStory = {
  args: { lines: 8 },
};

/* ── StaleWarning ── */
type StaleStory = StoryObj<typeof StaleWarning>;

export const StaleWarningBanner: StaleStory = {
  args: {
    lastUpdated: "2026-07-17T10:00:00Z",
    source: "CVM Filing",
  },
};

/* ── PartialDataIndicator ── */
type PartialStory = StoryObj<typeof PartialDataIndicator>;

export const PartialCoverage: PartialStory = {
  args: {
    coverage: 65,
    missingFields: ["ROE", "D/E", "EV/EBITDA"],
  },
};
