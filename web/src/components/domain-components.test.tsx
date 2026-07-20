import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import {
  ConfidenceBar,
  EvidenceTag,
  FreshnessPill,
  MandateBadge,
  QualityIndicator,
} from "@/components/evidence-tags";
import { ApprovalCard } from "@/components/decision-components";
import { DataStatePanel, LoadingSkeleton, PartialDataIndicator, StaleWarning } from "@/components/data-state-components";

describe("Evidence tags and badges", () => {
  it("EvidenceTag renders fact with correct tone", () => {
    render(<EvidenceTag kind="fact">Receita R$ 10bi</EvidenceTag>);
    const badge = screen.getByText(/fato/i);
    expect(badge).toBeInTheDocument();
    expect(badge.closest("[data-tone]")).toHaveAttribute("data-tone", "good");
  });

  it("EvidenceTag renders inference with warn tone", () => {
    render(<EvidenceTag kind="inference">Crescimento de 5%</EvidenceTag>);
    const badge = screen.getByText(/inferência/i);
    expect(badge.closest("[data-tone]")).toHaveAttribute("data-tone", "warn");
  });

  it("EvidenceTag renders recommendation with neutral tone", () => {
    render(<EvidenceTag kind="recommendation">Comprar 2%</EvidenceTag>);
    const badge = screen.getByText(/recomendação/i);
    expect(badge.closest("[data-tone]")).toHaveAttribute("data-tone", "neutral");
  });

  it("ConfidenceBar clamps values to 0-100", () => {
    const { rerender } = render(<ConfidenceBar value={150} />);
    expect(screen.getByText("100%")).toBeInTheDocument();
    rerender(<ConfidenceBar value={-10} />);
    expect(screen.getByText("0%")).toBeInTheDocument();
  });

  it("ConfidenceBar shows label when provided", () => {
    render(<ConfidenceBar value={85} label="Cobertura" />);
    expect(screen.getByText("Cobertura")).toBeInTheDocument();
  });

  it("FreshnessPill shows 'Atual' for recent data", () => {
    const recent = new Date().toISOString();
    render(<FreshnessPill retrievedAt={recent} />);
    expect(screen.getByText("Atual")).toBeInTheDocument();
  });

  it("FreshnessPill shows 'Stale' for old data", () => {
    const old = new Date(Date.now() - 100 * 24 * 60 * 60 * 1000).toISOString();
    render(<FreshnessPill retrievedAt={old} />);
    expect(screen.getByText("Stale")).toBeInTheDocument();
  });

  it("MandateBadge renders all statuses", () => {
    const { rerender } = render(<MandateBadge status="approved" />);
    expect(screen.getByText("Aprovada")).toBeInTheDocument();
    rerender(<MandateBadge status="paper_live" />);
    expect(screen.getByText("Paper live")).toBeInTheDocument();
    rerender(<MandateBadge status="committee" />);
    expect(screen.getByText("Comitê")).toBeInTheDocument();
    rerender(<MandateBadge status="simulated" />);
    expect(screen.getByText("Simulada")).toBeInTheDocument();
    rerender(<MandateBadge status="ineligible" />);
    expect(screen.getByText("Inelegível")).toBeInTheDocument();
  });

  it("QualityIndicator shows percentage", () => {
    render(<QualityIndicator score={95} />);
    expect(screen.getByText("95%")).toBeInTheDocument();
  });
});

describe("Data state components", () => {
  it("DataStatePanel shows correct title for each state", () => {
    const { rerender } = render(<DataStatePanel state="empty" />);
    expect(screen.getByText("Sem dados disponíveis")).toBeInTheDocument();
    rerender(<DataStatePanel state="stale" />);
    expect(screen.getByText("Dados desatualizados")).toBeInTheDocument();
    rerender(<DataStatePanel state="forbidden" />);
    expect(screen.getByText("Sem permissão")).toBeInTheDocument();
    rerender(<DataStatePanel state="error" />);
    expect(screen.getByText("Erro ao carregar")).toBeInTheDocument();
  });

  it("DataStatePanel allows custom title and detail", () => {
    render(<DataStatePanel state="partial" title="Custom" detail="Custom detail" />);
    expect(screen.getByText("Custom")).toBeInTheDocument();
    expect(screen.getByText("Custom detail")).toBeInTheDocument();
  });

  it("DataStatePanel error state has alert role", () => {
    render(<DataStatePanel state="error" />);
    expect(screen.getByRole("alert")).toBeInTheDocument();
  });

  it("DataStatePanel non-error state has status role", () => {
    render(<DataStatePanel state="empty" />);
    expect(screen.getByRole("status")).toBeInTheDocument();
  });

  it("LoadingSkeleton renders correct number of lines", () => {
    const { container } = render(<LoadingSkeleton lines={5} />);
    expect(container.querySelectorAll("[role='status'] > div")).toHaveLength(5);
  });

  it("StaleWarning shows last updated time", () => {
    render(<StaleWarning lastUpdated="2026-07-18T12:00:00Z" />);
    expect(screen.getByRole("alert")).toBeInTheDocument();
    expect(screen.getByText(/desatualizados desde/)).toBeInTheDocument();
  });

  it("PartialDataIndicator shows coverage percentage", () => {
    render(<PartialDataIndicator coverage={75} missingFields={["revenue", "ebitda"]} />);
    expect(screen.getByText(/75% de cobertura/)).toBeInTheDocument();
    expect(screen.getByText(/revenue, ebitda/)).toBeInTheDocument();
  });
});

describe("ApprovalCard", () => {
  it("renders pending status with warn tone", () => {
    render(
      <ApprovalCard
        title="Rebalanceamento"
        description="Proposta de revisão"
        status="pending"
        requestedBy="Portfolio Manager"
        requestedAt="18/07/2026 14:00"
      />,
    );
    expect(screen.getByText("Pendente")).toBeInTheDocument();
    expect(screen.getByText("Rebalanceamento")).toBeInTheDocument();
  });

  it("renders approved status with good tone", () => {
    render(
      <ApprovalCard
        title="Alocação VALE3"
        description="Compra de 2%"
        status="approved"
        requestedBy="Analyst"
        requestedAt="18/07/2026 10:00"
        decidedBy="Committee"
        decidedAt="18/07/2026 16:00"
        reason="Tese forte com catalyst"
      />,
    );
    expect(screen.getByText("Aprovado")).toBeInTheDocument();
    expect(screen.getByText("Committee")).toBeInTheDocument();
  });

  it("renders conditions when provided", () => {
    render(
      <ApprovalCard
        title="Stress test waiver"
        description="Waiver de limite"
        status="conditional"
        requestedBy="Risk"
        requestedAt="18/07/2026 12:00"
        conditions={["Revisão em 30 dias", "Cobertura de hedge obrigatória"]}
      />,
    );
    expect(screen.getByText("Condicionado")).toBeInTheDocument();
    expect(screen.getByText("Revisão em 30 dias")).toBeInTheDocument();
    expect(screen.getByText("Cobertura de hedge obrigatória")).toBeInTheDocument();
  });
});
