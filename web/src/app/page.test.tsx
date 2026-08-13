import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";

vi.mock("next/link", () => ({
  default: ({ children, href }: { children: React.ReactNode; href: string }) => (
    <a href={href}>{children}</a>
  ),
}));

const mockUsePortfoliosList = vi.fn();
vi.mock("@/hooks/use-portfolios", () => ({
  usePortfoliosList: (...args: unknown[]) => mockUsePortfoliosList(...args),
}));

beforeEach(() => {
  mockUsePortfoliosList.mockReturnValue({
    portfolios: [],
    count: 0,
    isLoading: false,
    isError: false,
    error: null,
  });
});

import MissionControlPage from "@/app/page";

describe("Mission Control page", () => {
  it("renders loading state", () => {
    mockUsePortfoliosList.mockReturnValue({
      portfolios: [],
      count: 0,
      isLoading: true,
      isError: false,
      error: null,
    });
    render(<MissionControlPage />);
    expect(screen.getByText("Carregando Dashboard")).toBeInTheDocument();
  });

  it("renders error state", () => {
    mockUsePortfoliosList.mockReturnValue({
      portfolios: [],
      count: 0,
      isLoading: false,
      isError: true,
      error: new Error("API error"),
    });
    render(<MissionControlPage />);
    expect(screen.getByText("API error")).toBeInTheDocument();
  });

  it("renders mission control header", () => {
    render(<MissionControlPage />);
    expect(screen.getByText("Mission Control")).toBeInTheDocument();
  });

  it("renders status cards", () => {
    render(<MissionControlPage />);
    expect(screen.getByText("Carteiras")).toBeInTheDocument();
    expect(screen.getByText("Posições")).toBeInTheDocument();
    expect(screen.getByText("Valor Total")).toBeInTheDocument();
    expect(screen.getByText("P&L Geral")).toBeInTheDocument();
  });

  it("renders the empty state", () => {
    render(<MissionControlPage />);
    expect(screen.getByText("Nenhuma carteira encontrada")).toBeInTheDocument();
  });

  it("renders a portfolio summary", () => {
    mockUsePortfoliosList.mockReturnValue({
      portfolios: [
        {
          id: "portfolio-1",
          name: "Carteira A",
          base_currency: "BRL",
          positions: [
            {
              id: "p1",
              ticker_symbol: "PETR4",
              quantity: 10,
              avg_cost_per_share: 20,
              current_price: 25,
            },
          ],
        },
      ],
      count: 1,
      isLoading: false,
      isError: false,
      error: null,
    });
    render(<MissionControlPage />);
    expect(screen.getByText("Carteira A")).toBeInTheDocument();
    expect(screen.getByText(/1 posições · BRL/)).toBeInTheDocument();
  });
});
