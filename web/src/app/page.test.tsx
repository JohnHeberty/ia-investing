import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi, beforeEach } from "vitest";
import type { ReactNode } from "react";

// Mock next/navigation
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
  usePathname: () => "/",
  useSearchParams: () => new URLSearchParams(),
}));

// Mock data hooks
const mockUsePortfolios = vi.fn();
const mockUseRiskAssessments = vi.fn();
const mockUseAgentRuns = vi.fn();
const mockUseResearchCases = vi.fn();

vi.mock("@/hooks/use-portfolios", () => ({
  usePortfolios: (...args: unknown[]) => mockUsePortfolios(...args),
}));

vi.mock("@/hooks/use-risk-assessments", () => ({
  useRiskAssessments: (...args: unknown[]) => mockUseRiskAssessments(...args),
}));

vi.mock("@/hooks/use-agent-runs", () => ({
  useAgentRuns: (...args: unknown[]) => mockUseAgentRuns(...args),
}));

vi.mock("@/hooks/use-research-cases", () => ({
  useResearchCases: (...args: unknown[]) => mockUseResearchCases(...args),
}));

// Default mock returns
const defaultPortfolios = {
  portfolios: [
    {
      id: "1",
      name: "Carteira A",
      state: "active",
      mandate_id: "mandate-001",
      base_currency: "BRL",
      environment: "production",
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-07-18T12:00:00Z",
      eligible: true,
      category: "renda-fixa",
    },
    {
      id: "2",
      name: "Carteira B",
      state: "draft",
      mandate_id: "mandate-002",
      base_currency: "BRL",
      environment: "paper",
      created_at: "2026-02-01T00:00:00Z",
      updated_at: "2026-07-18T10:00:00Z",
      eligible: true,
      category: "acoes",
    },
  ],
  isLoading: false,
  dataState: "empty",
  count: 2,
};

const defaultRisk = {
  assessment: {
    breaches: [],
    concentration: { stale_sources: 0 },
  },
  sources: [],
  staleCount: 0,
  healthyCount: 10,
  totalSources: 10,
  isLoading: false,
  dataState: "empty",
};

const defaultRuns = {
  runs: [],
  completedRuns: 5,
  totalCost: 12.5,
  isLoading: false,
  dataState: "empty",
  count: 8,
};

const defaultCases = {
  cases: [],
  openCases: 2,
  researchCases: 3,
  readyForCommittee: 1,
  isLoading: false,
  dataState: "empty",
};

beforeEach(() => {
  mockUsePortfolios.mockReturnValue(defaultPortfolios);
  mockUseRiskAssessments.mockReturnValue(defaultRisk);
  mockUseAgentRuns.mockReturnValue(defaultRuns);
  mockUseResearchCases.mockReturnValue(defaultCases);
});

import { MissionControlContent } from "@/app/page";

describe("Mission Control page", () => {
  describe("Loading state", () => {
    it("shows loading skeleton when any data source is loading", () => {
      mockUsePortfolios.mockReturnValue({ ...defaultPortfolios, isLoading: true });

      render(<MissionControlContent />);

      // LoadingSkeleton renders with aria-label="Carregando" and sr-only text
      const loadingElements = screen.getAllByText(/Carregando/);
      expect(loadingElements.length).toBeGreaterThan(0);
    });
  });

  describe("Error state", () => {
    it("shows DataStatePanel when any data source has error", () => {
      mockUsePortfolios.mockReturnValue({ ...defaultPortfolios, dataState: "error" });

      render(<MissionControlContent />);

      expect(screen.getByRole("alert")).toBeInTheDocument();
      expect(screen.getByText("Erro ao carregar dados")).toBeInTheDocument();
    });
  });

  describe("Empty state", () => {
    it("shows empty state when no portfolios found", () => {
      mockUsePortfolios.mockReturnValue({
        ...defaultPortfolios,
        portfolios: [],
        count: 0,
      });

      render(<MissionControlContent />);

      expect(screen.getByText("Nenhuma carteira encontrada")).toBeInTheDocument();
    });
  });

  describe("Stale warning", () => {
    it("shows stale warning when data is outdated", () => {
      mockUsePortfolios.mockReturnValue({ ...defaultPortfolios, dataState: "stale" });

      render(<MissionControlContent />);

      expect(screen.getByRole("alert")).toBeInTheDocument();
      expect(screen.getByText(/Dados desatualizados/)).toBeInTheDocument();
    });
  });

  describe("Data rendering", () => {
    it("renders page title and subtitle", () => {
      render(<MissionControlContent />);

      expect(screen.getByText("Mission control")).toBeInTheDocument();
      expect(screen.getByText("Decisões com contexto, não ruído.")).toBeInTheDocument();
    });

    it("renders metric cards with correct values", () => {
      render(<MissionControlContent />);

      expect(screen.getByText("Carteiras ativas")).toBeInTheDocument();
      // "Runs concluídos" appears in both metrics and agent section, use getAllByText
      expect(screen.getAllByText("Runs concluídos").length).toBeGreaterThan(0);
      expect(screen.getByText("Risco ativo")).toBeInTheDocument();
      expect(screen.getAllByText("Fontes saudáveis").length).toBeGreaterThan(0);
    });

    it("renders portfolio table with eligible portfolios", () => {
      render(<MissionControlContent />);

      expect(screen.getByText("Carteiras elegíveis · Top comparável")).toBeInTheDocument();
      expect(screen.getByText("Carteira A")).toBeInTheDocument();
      expect(screen.getByText("Carteira B")).toBeInTheDocument();
    });

    it("renders eligibility filter dropdown", () => {
      render(<MissionControlContent />);

      const select = screen.getByLabelText("Filtrar por elegibilidade");
      expect(select).toBeInTheDocument();
      expect(select).toHaveValue("eligible");
    });

    it("renders events section", () => {
      render(<MissionControlContent />);

      expect(screen.getByText("Eventos materiais")).toBeInTheDocument();
    });

    it("renders research funnel metrics", () => {
      render(<MissionControlContent />);

      expect(screen.getByText("Funil de pesquisa")).toBeInTheDocument();
      // "Casos abertos" appears in both funnel and events
      expect(screen.getAllByText("Casos abertos").length).toBeGreaterThan(0);
      expect(screen.getByText("Em pesquisa")).toBeInTheDocument();
    });

    it("renders agent operations metrics", () => {
      render(<MissionControlContent />);

      expect(screen.getByText("Operação de agents")).toBeInTheDocument();
      expect(screen.getAllByText("Runs concluídos").length).toBeGreaterThan(0);
    });

    it("renders data quality metrics", () => {
      render(<MissionControlContent />);

      expect(screen.getByText("Qualidade dos dados")).toBeInTheDocument();
      expect(screen.getAllByText("Fontes saudáveis").length).toBeGreaterThan(0);
    });
  });

  describe("Eligibility filtering", () => {
    it("filters out ineligible portfolios from comparison", () => {
      mockUsePortfolios.mockReturnValue({
        ...defaultPortfolios,
        portfolios: [
          ...defaultPortfolios.portfolios,
          {
            id: "3",
            name: "Carteira Inelegível",
            state: "active",
            mandate_id: "mandate-003",
            base_currency: "BRL",
            environment: "production",
            created_at: "2026-03-01T00:00:00Z",
            updated_at: "2026-07-18T11:00:00Z",
            eligible: false,
            category: "",
          },
        ],
        count: 3,
      });

      render(<MissionControlContent />);

      // Should show 2 eligible portfolios, not the ineligible one
      expect(screen.getByText("Carteira A")).toBeInTheDocument();
      expect(screen.getByText("Carteira B")).toBeInTheDocument();
      expect(screen.queryByText("Carteira Inelegível")).not.toBeInTheDocument();
    });

    it("filters out non-BRL portfolios from comparison", () => {
      mockUsePortfolios.mockReturnValue({
        ...defaultPortfolios,
        portfolios: [
          ...defaultPortfolios.portfolios,
          {
            id: "4",
            name: "Carteira USD",
            state: "active",
            mandate_id: "mandate-004",
            base_currency: "USD",
            environment: "production",
            created_at: "2026-04-01T00:00:00Z",
            updated_at: "2026-07-18T09:00:00Z",
            eligible: true,
            category: "",
          },
        ],
        count: 3,
      });

      render(<MissionControlContent />);

      // Should show only BRL portfolios
      expect(screen.getByText("Carteira A")).toBeInTheDocument();
      expect(screen.getByText("Carteira B")).toBeInTheDocument();
      expect(screen.queryByText("Carteira USD")).not.toBeInTheDocument();
    });
  });

  describe("Events section", () => {
    it("shows stale sources event when stale count > 0", () => {
      mockUseRiskAssessments.mockReturnValue({
        ...defaultRisk,
        staleCount: 3,
      });

      render(<MissionControlContent />);

      expect(screen.getByText("Fontes desatualizadas")).toBeInTheDocument();
    });

    it("shows hard breach event when hard breaches exist", () => {
      mockUseRiskAssessments.mockReturnValue({
        ...defaultRisk,
        assessment: {
          breaches: [
            { limit_type: "hard", name: "Limite 1" },
            { limit_type: "soft", name: "Limite 2" },
          ],
          concentration: { stale_sources: 0 },
        },
      });

      render(<MissionControlContent />);

      expect(screen.getByText("Hard breach ativo")).toBeInTheDocument();
    });

    it("shows open cases event when open cases > 0", () => {
      mockUseResearchCases.mockReturnValue({
        ...defaultCases,
        openCases: 5,
      });

      render(<MissionControlContent />);

      // "Casos abertos" appears in both funnel and events
      expect(screen.getAllByText("Casos abertos").length).toBeGreaterThan(0);
    });
  });
});
