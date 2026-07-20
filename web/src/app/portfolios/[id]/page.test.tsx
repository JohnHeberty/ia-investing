import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi, beforeEach } from "vitest";

// Mock next/navigation
vi.mock("next/navigation", () => ({
  useParams: () => ({ id: "portfolio-123" }),
  useRouter: () => ({ push: vi.fn() }),
  usePathname: () => "/portfolios/portfolio-123",
  useSearchParams: () => new URLSearchParams(),
}));

// Mock portfolio hook
const mockUsePortfolio = vi.fn();

vi.mock("@/hooks/use-portfolios", () => ({
  usePortfolio: (...args: unknown[]) => mockUsePortfolio(...args),
}));

// Default mock portfolio data
const defaultPortfolio = {
  id: "portfolio-123",
  name: "Carteira Modelo Ações",
  state: "active",
  mandate_id: "mandate-001-abcdef",
  base_currency: "BRL",
  environment: "production",
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-07-18T12:00:00Z",
  lock_version: "42",
  owner_team_id: "team-alpha",
  organization_id: "org-1",
  benchmark: "Ibovespa",
  nav_reconciled: true,
  methodology: "nav-v1",
};

beforeEach(() => {
  mockUsePortfolio.mockReturnValue({
    portfolio: defaultPortfolio,
    isLoading: false,
    isError: false,
    dataState: "empty",
  });
});

import { PortfolioContent } from "@/app/portfolios/[id]/page";

describe("Portfolio 360 page", () => {
  describe("Loading state", () => {
    it("shows loading skeleton when data is loading", () => {
      mockUsePortfolio.mockReturnValue({
        portfolio: null,
        isLoading: true,
        isError: false,
        dataState: "empty",
      });

      render(<PortfolioContent id="portfolio-123" />);

      // LoadingSkeleton renders with aria-label="Carregando" and sr-only text
      const loadingElements = screen.getAllByText(/Carregando/);
      expect(loadingElements.length).toBeGreaterThan(0);
    });

    it("shows Carregando... title during loading", () => {
      mockUsePortfolio.mockReturnValue({
        portfolio: null,
        isLoading: true,
        isError: false,
        dataState: "empty",
      });

      render(<PortfolioContent id="portfolio-123" />);

      expect(screen.getByText("Carregando…")).toBeInTheDocument();
    });
  });

  describe("Error state", () => {
    it("shows error panel when portfolio not found", () => {
      mockUsePortfolio.mockReturnValue({
        portfolio: null,
        isLoading: false,
        isError: true,
        dataState: "error",
      });

      render(<PortfolioContent id="portfolio-123" />);

      expect(screen.getByText("Carteira não encontrada")).toBeInTheDocument();
      expect(screen.getByText("Erro ao carregar carteira")).toBeInTheDocument();
    });

    it("shows error panel when portfolio is null", () => {
      mockUsePortfolio.mockReturnValue({
        portfolio: null,
        isLoading: false,
        isError: false,
        dataState: "missing",
      });

      render(<PortfolioContent id="portfolio-123" />);

      expect(screen.getByText("Carteira não encontrada")).toBeInTheDocument();
    });
  });

  describe("Data rendering", () => {
    it("renders portfolio name as page title", () => {
      render(<PortfolioContent id="portfolio-123" />);

      expect(screen.getByText("Carteira Modelo Ações")).toBeInTheDocument();
    });

    it("renders subtitle with currency and environment", () => {
      render(<PortfolioContent id="portfolio-123" />);

      expect(screen.getByText(/Carteira-modelo/)).toBeInTheDocument();
      expect(screen.getAllByText("BRL").length).toBeGreaterThan(0);
      expect(screen.getByText(/ambiente production/)).toBeInTheDocument();
    });

    it("renders metric cards", () => {
      render(<PortfolioContent id="portfolio-123" />);

      expect(screen.getByText("Moeda base")).toBeInTheDocument();
      expect(screen.getByText("Estado")).toBeInTheDocument();
      expect(screen.getByText("Benchmark")).toBeInTheDocument();
      expect(screen.getByText("NAV Reconciliado")).toBeInTheDocument();
    });

    it("renders state badge with correct tone", () => {
      render(<PortfolioContent id="portfolio-123" />);

      const badges = screen.getAllByText("Ativa");
      expect(badges.length).toBeGreaterThan(0);
      expect(badges[0].closest("[data-tone]")).toHaveAttribute("data-tone", "good");
    });

    it("renders benchmark metric", () => {
      render(<PortfolioContent id="portfolio-123" />);

      expect(screen.getByText("Benchmark")).toBeInTheDocument();
      expect(screen.getByText("Ibovespa")).toBeInTheDocument();
    });

    it("renders NAV reconciled status", () => {
      render(<PortfolioContent id="portfolio-123" />);

      expect(screen.getByText("NAV Reconciliado")).toBeInTheDocument();
      expect(screen.getByText("Sim")).toBeInTheDocument();
    });

    it("renders methodology in footer", () => {
      render(<PortfolioContent id="portfolio-123" />);

      expect(screen.getByText(/Metodologia:/)).toBeInTheDocument();
      expect(screen.getByText(/nav-v1/)).toBeInTheDocument();
    });
  });

  describe("Tab switching", () => {
    it("renders all tab triggers", () => {
      render(<PortfolioContent id="portfolio-123" />);

      // Radix Tabs renders buttons with role="tab"
      const tabs = screen.getAllByRole("tab");
      const tabNames = tabs.map((tab) => tab.textContent);
      expect(tabNames).toContain("Posições");
      expect(tabNames).toContain("Performance");
      expect(tabNames).toContain("Risco");
      expect(tabNames).toContain("Teses");
      expect(tabNames).toContain("Auditoria");
    });

    it("shows positions tab content by default", () => {
      render(<PortfolioContent id="portfolio-123" />);

      // Radix Tabs shows the first tab's content by default
      // The positions tab content includes StatePanel with the detail text
      const tabPanels = screen.getAllByRole("tabpanel");
      expect(tabPanels.length).toBeGreaterThan(0);
      // First tab panel should be active
      expect(tabPanels[0]).toHaveAttribute("data-state", "active");
    });

    it("switches to performance tab on click", async () => {
      const user = userEvent.setup();
      render(<PortfolioContent id="portfolio-123" />);

      const tabs = screen.getAllByRole("tab");
      const performanceTab = tabs.find((tab) => tab.textContent === "Performance")!;
      await user.click(performanceTab);

      expect(screen.getByText("NAV e benchmark")).toBeInTheDocument();
      expect(screen.getByText("nav-v1")).toBeInTheDocument();
    });

    it("switches to risk tab on click", async () => {
      const user = userEvent.setup();
      render(<PortfolioContent id="portfolio-123" />);

      const tabs = screen.getAllByRole("tab");
      const riskTab = tabs.find((tab) => tab.textContent === "Risco")!;
      await user.click(riskTab);

      expect(screen.getByText("Limites de risco")).toBeInTheDocument();
      expect(screen.getByText("Histórico de violações")).toBeInTheDocument();
      expect(screen.getByText("Exposções por classe")).toBeInTheDocument();
      expect(screen.getByText("Waterfall de cenários")).toBeInTheDocument();
    });

    it("switches to theses tab on click", async () => {
      const user = userEvent.setup();
      render(<PortfolioContent id="portfolio-123" />);

      const tabs = screen.getAllByRole("tab");
      const thesesTab = tabs.find((tab) => tab.textContent === "Teses")!;
      await user.click(thesesTab);

      expect(screen.getByText("Teses e propostas")).toBeInTheDocument();
      expect(screen.getByText("Expansão infraestrutura verde")).toBeInTheDocument();
    });

    it("switches to audit tab on click", async () => {
      const user = userEvent.setup();
      render(<PortfolioContent id="portfolio-123" />);

      const tabs = screen.getAllByRole("tab");
      const auditTab = tabs.find((tab) => tab.textContent === "Auditoria")!;
      await user.click(auditTab);

      expect(screen.getByText("Trilha de auditoria")).toBeInTheDocument();
      expect(screen.getByText("Rebalanceamento aprovado")).toBeInTheDocument();
    });
  });

  describe("Risk tab content", () => {
    it("shows risk limits table", async () => {
      const user = userEvent.setup();
      render(<PortfolioContent id="portfolio-123" />);

      const tabs = screen.getAllByRole("tab");
      const riskTab = tabs.find((tab) => tab.textContent === "Risco")!;
      await user.click(riskTab);

      expect(screen.getByText("Limites de risco")).toBeInTheDocument();
      expect(screen.getAllByText("Concentração por ativo").length).toBeGreaterThan(0);
    });

    it("shows breach history", async () => {
      const user = userEvent.setup();
      render(<PortfolioContent id="portfolio-123" />);

      const tabs = screen.getAllByRole("tab");
      const riskTab = tabs.find((tab) => tab.textContent === "Risco")!;
      await user.click(riskTab);

      expect(screen.getByText("Histórico de violações")).toBeInTheDocument();
    });

    it("shows authorized action buttons", async () => {
      const user = userEvent.setup();
      render(<PortfolioContent id="portfolio-123" />);

      const tabs = screen.getAllByRole("tab");
      const riskTab = tabs.find((tab) => tab.textContent === "Risco")!;
      await user.click(riskTab);

      expect(screen.getByRole("button", { name: /Solicitar stress adicional/ })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: /Waiver temporário/ })).toBeInTheDocument();
    });

    it("shows ApprovalCard when stress is requested", async () => {
      const user = userEvent.setup();
      render(<PortfolioContent id="portfolio-123" />);

      const tabs = screen.getAllByRole("tab");
      const riskTab = tabs.find((tab) => tab.textContent === "Risco")!;
      await user.click(riskTab);
      await user.click(screen.getByRole("button", { name: /Solicitar stress adicional/ }));

      expect(screen.getByText("Stress adicional solicitado")).toBeInTheDocument();
      expect(screen.getByText("Pendente")).toBeInTheDocument();
    });

    it("shows ApprovalCard when waiver is requested", async () => {
      const user = userEvent.setup();
      render(<PortfolioContent id="portfolio-123" />);

      const tabs = screen.getAllByRole("tab");
      const riskTab = tabs.find((tab) => tab.textContent === "Risco")!;
      await user.click(riskTab);
      await user.click(screen.getByRole("button", { name: /Waiver temporário/ }));

      // The ApprovalCard title and button both say "Waiver temporário", so use getAllByText
      const waiverTexts = screen.getAllByText("Waiver temporário");
      expect(waiverTexts.length).toBeGreaterThan(1);
      expect(screen.getByText("Pendente")).toBeInTheDocument();
      expect(screen.getByText("Revisão em 30 dias")).toBeInTheDocument();
    });
  });

  describe("Theses tab content", () => {
    it("shows thesis items with EvidenceTag", async () => {
      const user = userEvent.setup();
      render(<PortfolioContent id="portfolio-123" />);

      const tabs = screen.getAllByRole("tab");
      const thesesTab = tabs.find((tab) => tab.textContent === "Teses")!;
      await user.click(thesesTab);

      expect(screen.getByText("Expansão infraestrutura verde")).toBeInTheDocument();
      expect(screen.getByText("Risco de juros nos EUA")).toBeInTheDocument();
      expect(screen.getByText("PIB Brasil Q2 2026")).toBeInTheDocument();

      // Check EvidenceTag badges
      expect(screen.getByText(/Recomendação/)).toBeInTheDocument();
      expect(screen.getByText(/Inferência/)).toBeInTheDocument();
      expect(screen.getByText(/Fato/)).toBeInTheDocument();
    });

    it("shows confidence bars for each thesis", async () => {
      const user = userEvent.setup();
      render(<PortfolioContent id="portfolio-123" />);

      const tabs = screen.getAllByRole("tab");
      const thesesTab = tabs.find((tab) => tab.textContent === "Teses")!;
      await user.click(thesesTab);

      // Check confidence values are shown
      expect(screen.getByText("85%")).toBeInTheDocument();
      expect(screen.getByText("72%")).toBeInTheDocument();
      expect(screen.getByText("98%")).toBeInTheDocument();
    });
  });

  describe("Audit tab content", () => {
    it("shows audit trail entries", async () => {
      const user = userEvent.setup();
      render(<PortfolioContent id="portfolio-123" />);

      const tabs = screen.getAllByRole("tab");
      const auditTab = tabs.find((tab) => tab.textContent === "Auditoria")!;
      await user.click(auditTab);

      expect(screen.getByText("Rebalanceamento aprovado")).toBeInTheDocument();
      expect(screen.getByText("Limite de concentração ajustado")).toBeInTheDocument();
      expect(screen.getByText("Snapshot publicado")).toBeInTheDocument();
      expect(screen.getByText("Mandato revisado")).toBeInTheDocument();
    });

    it("shows user and timestamp for each entry", async () => {
      const user = userEvent.setup();
      render(<PortfolioContent id="portfolio-123" />);

      const tabs = screen.getAllByRole("tab");
      const auditTab = tabs.find((tab) => tab.textContent === "Auditoria")!;
      await user.click(auditTab);

      expect(screen.getByText("Committee")).toBeInTheDocument();
      expect(screen.getByText("Risk Manager")).toBeInTheDocument();
      expect(screen.getByText("System")).toBeInTheDocument();
      expect(screen.getByText("Compliance")).toBeInTheDocument();
    });
  });

  describe("Rebalance section", () => {
    it("shows PortfolioDiff with proposed changes", () => {
      render(<PortfolioContent id="portfolio-123" />);

      expect(screen.getByText("Proposta de rebalanceamento")).toBeInTheDocument();
      expect(screen.getByText("PETR4")).toBeInTheDocument();
      expect(screen.getByText("VALE3")).toBeInTheDocument();
      expect(screen.getByText("WEGE3")).toBeInTheDocument();
    });

    it("shows constraint compliance table", () => {
      render(<PortfolioContent id="portfolio-123" />);

      expect(screen.getByText("Conformidade de restrições")).toBeInTheDocument();
      expect(screen.getAllByText("Concentração máxima por ativo").length).toBeGreaterThan(0);
      expect(screen.getByText("Todos passam")).toBeInTheDocument();
    });
  });

  describe("Stale warning", () => {
    it("shows stale warning when data is outdated", () => {
      mockUsePortfolio.mockReturnValue({
        portfolio: defaultPortfolio,
        isLoading: false,
        isError: false,
        dataState: "stale",
      });

      render(<PortfolioContent id="portfolio-123" />);

      expect(screen.getByRole("alert")).toBeInTheDocument();
      expect(screen.getByText(/Dados desatualizados/)).toBeInTheDocument();
    });
  });
});
