import { useState } from "react";
import type { Meta, StoryObj } from "@storybook/nextjs-vite";
import { SourceDrawer, type SourceEntry } from "./source-drawer";

const meta: Meta<typeof SourceDrawer> = {
  title: "Domain/SourceDrawer",
  component: SourceDrawer,
  tags: ["autodocs"],
};
export default meta;

type Story = StoryObj<typeof SourceDrawer>;

const sampleSources: SourceEntry[] = [
  {
    id: "src-1",
    name: "CVM Filing PETR4 Q4 2025",
    type: "filing",
    url: "https://example.com/filing",
    retrievedAt: "2026-07-19T10:30:00Z",
    confidence: 0.95,
  },
  {
    id: "src-2",
    name: "Reuters: Petrobras anuncia divendo",
    type: "news",
    url: "https://example.com/news",
    retrievedAt: "2026-07-19T08:00:00Z",
    confidence: 0.88,
  },
  {
    id: "src-3",
    name: "SELIC Focus Report",
    type: "macro",
    retrievedAt: "2026-07-18T12:00:00Z",
    confidence: 0.72,
  },
  {
    id: "src-4",
    name: "Comissão de Fiscalização — PL 123",
    type: "political",
    retrievedAt: "2026-07-17T15:00:00Z",
    confidence: 0.6,
  },
];

export const WithSources: Story = {
  render: () => {
    const [open, setOpen] = useState(true);
    return (
      <>
        <button onClick={() => setOpen(true)} className="button">
          Abrir drawer
        </button>
        <SourceDrawer open={open} onClose={() => setOpen(false)} sources={sampleSources} />
      </>
    );
  },
};

export const Empty: Story = {
  render: () => {
    const [open, setOpen] = useState(true);
    return (
      <>
        <button onClick={() => setOpen(true)} className="button">
          Abrir drawer
        </button>
        <SourceDrawer open={open} onClose={() => setOpen(false)} sources={[]} />
      </>
    );
  },
};
