import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";

vi.mock("next/link", () => ({
  default: ({ children, href }: { children: React.ReactNode; href: string }) => <a href={href}>{children}</a>,
}));

vi.mock("@/components/portfolio-ranking-table", () => ({
  PortfolioRankingTable: ({ items }: { items: unknown[] }) => <div data-testid="ranking-table">{items.length} items</div>,
}));

const mockUseMissionControl = vi.fn();
vi.mock("@/hooks/use-mission-control", () => ({
  useMissionControl: (...args: unknown[]) => mockUseMissionControl(...args),
}));

const defaultData = {
  generated_at: "2026-07-22T18:05:00Z",
  data_as_of: "2026-07-22T18:00:00Z",
  critical_alerts: 0,
  pending_approvals: 2,
  top_portfolios: [
    { portfolio_id: "1", name: "Carteira A", cohort_key: "br-equity", category: "acoes", benchmark: "IBOV", currency: "BRL", risk_class: "moderado", environment: "paper", stage: "active", score: "0.85" },
    { portfolio_id: "2", name: "Carteira B", cohort_key: "br-equity", category: "acoes", benchmark: "IBOV", currency: "BRL", risk_class: "moderado", environment: "paper", stage: "active", score: "0.72" },
  ],
  risk: { open_hard_breaches: 0, open_soft_breaches: 1, portfolios_with_breaches: 0, stale_risk_snapshots: 0 },
  agent_operations: { running: 3, succeeded_24h: 15, failed_24h: 0, evidence_coverage: "0.85", schema_pass_rate: "0.95", cost_usd_24h: "12.50" },
  source_health: [],
  research_funnel: { open: 5, triaged: 3, in_research: 4, ready_for_committee: 2 },
};

beforeEach(() => {
  mockUseMissionControl.mockReturnValue({ data: defaultData, isPending: false, isError: false, error: null });
});

import MissionControlPage from "@/app/page";

describe("Mission Control page", () => {
  it("renders loading state", () => {
    mockUseMissionControl.mockReturnValue({ isPending: true, isError: false, data: null, error: null });
    render(<MissionControlPage />);
    expect(screen.getByText(/Consolidando/)).toBeInTheDocument();
  });

  it("renders error state", () => {
    mockUseMissionControl.mockReturnValue({ isPending: false, isError: true, data: null, error: new Error("API error") });
    render(<MissionControlPage />);
    expect(screen.getByText("API error")).toBeInTheDocument();
  });

  it("renders mission control header", () => {
    render(<MissionControlPage />);
    expect(screen.getByText("Mission Control")).toBeInTheDocument();
  });

  it("renders status cards", () => {
    render(<MissionControlPage />);
    expect(screen.getByText("Alertas críticos")).toBeInTheDocument();
    expect(screen.getByText("Carteiras elegíveis")).toBeInTheDocument();
    expect(screen.getByText("Pesquisa ativa")).toBeInTheDocument();
    expect(screen.getByText("Agents em execução")).toBeInTheDocument();
  });

  it("renders portfolio ranking section", () => {
    render(<MissionControlPage />);
    expect(screen.getByText("Top carteiras por coorte")).toBeInTheDocument();
    expect(screen.getByTestId("ranking-table")).toBeInTheDocument();
  });

  it("renders research funnel", () => {
    render(<MissionControlPage />);
    expect(screen.getByText("Funil de pesquisa")).toBeInTheDocument();
  });

  it("shows all healthy message when no unhealthy sources", () => {
    render(<MissionControlPage />);
    expect(screen.getByText("Todas as fontes ativas estão dentro do SLA.")).toBeInTheDocument();
  });

  it("shows unhealthy sources when present", () => {
    mockUseMissionControl.mockReturnValue({
      data: {
        ...defaultData,
        source_health: [
          { source_id: "src-1", name: "CVM", status: "stale", age_minutes: 300 },
        ],
      },
      isPending: false, isError: false, error: null,
    });
    render(<MissionControlPage />);
    expect(screen.getByText("CVM")).toBeInTheDocument();
  });
});
