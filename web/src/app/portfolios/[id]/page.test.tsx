import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("next/navigation", () => ({
  useParams: () => ({ id: "portfolio-123" }),
  useRouter: () => ({ push: vi.fn() }),
}));

const mockUsePortfolioDetail = vi.fn();
const mutation = { mutate: vi.fn(), mutateAsync: vi.fn(), isPending: false };

vi.mock("@/hooks/use-portfolios", () => ({
  usePortfolioDetail: (...args: unknown[]) => mockUsePortfolioDetail(...args),
  usePortfolioRecommendations: () => ({ recommendations: [], refetch: vi.fn() }),
  usePortfolioTheses: () => ({ theses: [], isLoading: false }),
  useDeletePortfolio: () => mutation,
  useUpdatePosition: () => mutation,
  useDeletePosition: () => mutation,
}));

vi.mock("@/hooks/use-audit-logs", () => ({
  useAuditLogs: () => ({ entries: [], isLoading: false }),
}));

const defaultPortfolio = {
  id: "portfolio-123",
  name: "Carteira Modelo Ações",
  is_paper_trading: true,
  base_currency: "BRL",
  description: "Estratégia de ações brasileiras",
  initial_capital: 100_000,
  positions: [
    {
      id: "position-1",
      ticker_symbol: "PETR4",
      quantity: 100,
      avg_cost_per_share: 30,
      current_price: 35,
    },
  ],
};

beforeEach(() => {
  mockUsePortfolioDetail.mockReturnValue({
    portfolio: defaultPortfolio,
    isLoading: false,
    isError: false,
  });
});

import { PortfolioContent } from "@/app/portfolios/[id]/page";

describe("Portfolio 360 page", () => {
  it("shows the loading state", () => {
    mockUsePortfolioDetail.mockReturnValue({ portfolio: null, isLoading: true, isError: false });
    render(<PortfolioContent id="portfolio-123" />);
    expect(screen.getByText("Carregando...")).toBeInTheDocument();
  });

  it("shows the missing portfolio state", () => {
    mockUsePortfolioDetail.mockReturnValue({ portfolio: null, isLoading: false, isError: true });
    render(<PortfolioContent id="portfolio-123" />);
    expect(screen.getByText("Carteira não encontrada")).toBeInTheDocument();
  });

  it("renders portfolio identity and position", () => {
    render(<PortfolioContent id="portfolio-123" />);
    expect(screen.getByText("Carteira Modelo Ações")).toBeInTheDocument();
    expect(screen.getByText("PETR4")).toBeInTheDocument();
    expect(screen.getAllByText(/1 posições/).length).toBeGreaterThan(0);
  });

  it("renders all current tabs", () => {
    render(<PortfolioContent id="portfolio-123" />);
    const names = screen.getAllByRole("tab").map((tab) => tab.textContent);
    expect(names).toEqual([
      "Posições",
      "Performance",
      "Risco",
      "Alocação",
      "Limites",
      "Teses",
      "Recomendações",
      "Auditoria",
    ]);
  });

  it("switches to performance", async () => {
    const user = userEvent.setup();
    render(<PortfolioContent id="portfolio-123" />);
    await user.click(screen.getByRole("tab", { name: "Performance" }));
    expect(screen.getByRole("tab", { name: "Performance" })).toHaveAttribute(
      "data-state",
      "active",
    );
  });

  it("opens the delete confirmation", async () => {
    const user = userEvent.setup();
    render(<PortfolioContent id="portfolio-123" />);
    await user.click(screen.getByRole("button", { name: "Excluir" }));
    expect(screen.getByText(/Tem certeza/i)).toBeInTheDocument();
  });
});
