import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { AsOfIndicator, Badge, DomainTabs, StatePanel } from "./domain";

describe("institutional domain components", () => {
  it("always exposes as_of and freshness as text", () => {
    render(<AsOfIndicator value="18 jul 2026" freshness="Stale" />);
    expect(screen.getByText(/as of 18 jul 2026 · Stale/)).toBeVisible();
  });

  it("does not rely only on color for semantic status", () => {
    render(<Badge tone="bad">Hard breach</Badge>);
    expect(screen.getByText("Hard breach")).toBeVisible();
  });

  it("announces operational states", () => {
    render(
      <StatePanel state="missing" title="Sem evidência" detail="A pesquisa está bloqueada." />,
    );
    expect(screen.getByRole("status")).toHaveTextContent("Sem evidência");
    expect(screen.getByRole("status")).toHaveAttribute("data-state", "missing");
  });

  it("exposes accessible keyboard-ready domain tabs", () => {
    render(
      <DomainTabs
        label="Visão da carteira"
        tabs={[
          { id: "positions", label: "Posições", content: "14 posições" },
          { id: "risk", label: "Risco", content: "Sem breach" },
        ]}
      />,
    );
    expect(screen.getByRole("tablist", { name: "Visão da carteira" })).toBeVisible();
    expect(screen.getByRole("tab", { name: "Posições" })).toHaveAttribute("aria-selected", "true");
  });
});
