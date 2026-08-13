"use client";

import { useParams, useRouter } from "next/navigation";
import { Suspense, useMemo, useState } from "react";
import Link from "next/link";

import { AllocationChart } from "@/components/allocation-chart";
import { AsOfIndicator, Badge, DomainTabs } from "@/components/domain";
import { LoadingSkeleton } from "@/components/data-state-components";
import {
  usePortfolioDetail,
  usePortfolioRecommendations,
  usePortfolioTheses,
  useDeletePortfolio,
} from "@/hooks/use-portfolios";
import { useUpdatePosition, useDeletePosition } from "@/hooks/use-portfolios";
import { useAuditLogs } from "@/hooks/use-audit-logs";

import { PortfolioMetrics } from "@/components/portfolio/PortfolioMetrics";
import { PositionsTab } from "@/components/portfolio/PositionsTab";
import { PerformanceTab } from "@/components/portfolio/PerformanceTab";
import { RiskTab } from "@/components/portfolio/RiskTab";
import { LimitsTab } from "@/components/portfolio/LimitsTab";
import { RecommendationsTab } from "@/components/portfolio/RecommendationsTab";
import { ThesesTab } from "@/components/portfolio/ThesesTab";
import { AuditTab } from "@/components/portfolio/AuditTab";
import { ConfirmDeleteModal } from "@/components/portfolio/ConfirmDeleteModal";

function computeRiskMetrics(
  positions: Array<{
    ticker_symbol: string;
    quantity: number;
    avg_cost_per_share: number;
    current_price: number | null;
  }>,
  totalValue: number,
) {
  const weights = positions.map((p) => {
    const price = p.current_price ?? p.avg_cost_per_share;
    return totalValue > 0 ? (p.quantity * price) / totalValue : 0;
  });
  const maxWeight = weights.length > 0 ? Math.max(...weights) : 0;
  const hhi = weights.reduce((sum, w) => sum + w * w, 0);
  const top3Weight = [...weights]
    .sort((a, b) => b - a)
    .slice(0, 3)
    .reduce((s, w) => s + w, 0);
  return { maxWeight, hhi, top3Weight };
}

export function PortfolioContent({ id }: { id: string }) {
  const { portfolio, isLoading, isError } = usePortfolioDetail(id);
  const { recommendations, refetch: refetchRecommendations } = usePortfolioRecommendations(id);
  const { theses, isLoading: thesesLoading } = usePortfolioTheses(id);
  const { entries: auditEntries, isLoading: auditLoading } = useAuditLogs("portfolio", id);
  const [showAddPosition, setShowAddPosition] = useState(false);
  const [showConfirmDelete, setShowConfirmDelete] = useState(false);
  const [editingPosition, setEditingPosition] = useState<string | null>(null);
  const [editForm, setEditForm] = useState<{
    ticker_symbol: string;
    quantity: string;
    avg_cost_per_share: string;
    current_price: string;
  }>({ ticker_symbol: "", quantity: "", avg_cost_per_share: "", current_price: "" });
  const [needsRecalc, setNeedsRecalc] = useState(false);
  const [editError, setEditError] = useState<string | null>(null);
  const deletePortfolio = useDeletePortfolio();
  const updatePosition = useUpdatePosition();
  const deletePosition = useDeletePosition();
  const router = useRouter();

  const positions = useMemo(() => portfolio?.positions || [], [portfolio?.positions]);
  const totalValue = useMemo(
    () =>
      positions.reduce(
        (sum, pos) => sum + pos.quantity * (pos.current_price ?? pos.avg_cost_per_share),
        0,
      ),
    [positions],
  );
  const totalCost = useMemo(
    () => positions.reduce((sum, pos) => sum + pos.quantity * pos.avg_cost_per_share, 0),
    [positions],
  );
  const riskMetrics = useMemo(
    () => computeRiskMetrics(positions, totalValue),
    [positions, totalValue],
  );
  const currency = portfolio?.base_currency || "BRL";
  const fmt = useMemo(
    () => new Intl.NumberFormat("pt-BR", { style: "currency", currency, maximumFractionDigits: 0 }),
    [currency],
  );

  if (isLoading) {
    return (
      <>
        <div className="page-head">
          <div>
            <div className="eyebrow">Portfolio 360</div>
            <h1>Carregando...</h1>
          </div>
        </div>
        <section className="grid grid-4">
          <LoadingSkeleton lines={4} />
          <LoadingSkeleton lines={4} />
          <LoadingSkeleton lines={4} />
          <LoadingSkeleton lines={4} />
        </section>
      </>
    );
  }

  if (isError || !portfolio) {
    return (
      <>
        <div className="page-head">
          <div>
            <div className="eyebrow">Portfolio 360</div>
            <h1>Carteira não encontrada</h1>
          </div>
        </div>
        <div className="state-panel" data-state="error">
          <strong>Erro ao carregar carteira</strong>
          <p>
            Não foi possível acessar os dados desta carteira. Verifique o ID ou tente novamente.
          </p>
        </div>
        <div className="mt-16">
          <Link href="/portfolios" className="button secondary">
            ← Voltar para Carteiras
          </Link>
        </div>
      </>
    );
  }

  const name = portfolio.name || "Carteira";
  const isPaper = portfolio.is_paper_trading;
  const totalPnl = totalValue - totalCost;
  const totalPnlPercent = totalCost > 0 ? (totalPnl / totalCost) * 100 : 0;

  return (
    <>
      <div className="page-head">
        <div>
          <div className="eyebrow">Portfolio 360</div>
          <h1>{name}</h1>
          <p className="subtitle">
            {isPaper ? "Carteira Paper" : "Carteira Live"} · {currency} · {positions.length}{" "}
            posições
          </p>
        </div>
        <div className="flex items-center gap-12">
          <Badge tone={isPaper ? "warn" : "good"}>{isPaper ? "Paper" : "Live"}</Badge>
          <AsOfIndicator value={new Date().toLocaleString("pt-BR")} freshness="Atual" />
          <button className="button danger sm" onClick={() => setShowConfirmDelete(true)}>
            Excluir
          </button>
        </div>
      </div>

      <ConfirmDeleteModal
        show={showConfirmDelete}
        name={name}
        onClose={() => setShowConfirmDelete(false)}
        onConfirm={async () => {
          await deletePortfolio.mutateAsync(id);
          router.push("/portfolios");
        }}
        isPending={deletePortfolio.isPending}
        error={deletePortfolio.error as Error | null}
      />

      <PortfolioMetrics
        totalValue={totalValue}
        totalPnl={totalPnl}
        totalPnlPercent={totalPnlPercent}
        positionsLength={positions.length}
        currency={currency}
        isPaper={isPaper}
        fmt={fmt}
      />

      <DomainTabs
        label="Detalhes da carteira"
        tabs={[
          {
            id: "positions",
            label: "Posições",
            content: (
              <PositionsTab
                positions={positions}
                totalValue={totalValue}
                currency={currency}
                portfolioId={id}
                editingPosition={editingPosition}
                editForm={editForm}
                setEditingPosition={setEditingPosition}
                setEditForm={setEditForm}
                needsRecalc={needsRecalc}
                setNeedsRecalc={setNeedsRecalc}
                updatePosition={updatePosition}
                deletePosition={deletePosition}
                showAddPosition={showAddPosition}
                setShowAddPosition={setShowAddPosition}
                editError={editError}
                setEditError={setEditError}
                refetchRecommendations={refetchRecommendations}
                fmt={fmt}
              />
            ),
          },
          {
            id: "performance",
            label: "Performance",
            content: (
              <PerformanceTab
                positions={positions}
                totalValue={totalValue}
                totalCost={totalCost}
                totalPnl={totalPnl}
                totalPnlPercent={totalPnlPercent}
                currency={currency}
                fmt={fmt}
              />
            ),
          },
          {
            id: "risk",
            label: "Risco",
            content: (
              <RiskTab positions={positions} totalValue={totalValue} riskMetrics={riskMetrics} />
            ),
          },
          {
            id: "allocation",
            label: "Alocação",
            content: (
              <div>
                <AllocationChart positions={positions} currency={currency} />
                {positions.length > 0 && (
                  <div className="card card-pad mt-16">
                    <div className="card-title">
                      <h2>Distribuição da Carteira</h2>
                    </div>
                    <div className="mt-16">
                      {positions.map((pos, idx) => {
                        const currentPrice = pos.current_price ?? pos.avg_cost_per_share;
                        const value = pos.quantity * currentPrice;
                        const weight = totalValue > 0 ? (value / totalValue) * 100 : 0;
                        const colors = [
                          "var(--accent)",
                          "var(--blue)",
                          "var(--amber)",
                          "var(--red)",
                          "#9b59b6",
                          "#1abc9c",
                        ];
                        const colorIndex = idx % colors.length;
                        return (
                          <div key={pos.id} className="flex items-center gap-12 distribution-row">
                            <div
                              className="distribution-swatch"
                              style={{ background: colors[colorIndex] }}
                            />
                            <span className="flex-1 fw-500">{pos.ticker_symbol}</span>
                            <span className="info-value">{fmt.format(value)}</span>
                            <span className="info-value-muted w-50 text-right">
                              {weight.toFixed(1)}%
                            </span>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}
              </div>
            ),
          },
          {
            id: "riskLimits",
            label: "Limites",
            content: <LimitsTab riskMetrics={riskMetrics} positionsLength={positions.length} />,
          },
          {
            id: "theses",
            label: "Teses",
            content: <ThesesTab theses={theses} isLoading={thesesLoading} />,
          },
          {
            id: "recommendations",
            label: "Recomendações",
            content: <RecommendationsTab recommendations={recommendations} />,
          },
          {
            id: "audit",
            label: "Auditoria",
            content: <AuditTab auditEntries={auditEntries} auditLoading={auditLoading} />,
          },
        ]}
      />

      <footer className="mt-12 page-footer">
        <p>
          <strong>Moeda:</strong> {currency} ·<strong> Tipo:</strong>{" "}
          {isPaper ? "Paper Trading" : "Live"} ·<strong> Posições:</strong> {positions.length} ·
          <strong> NAV:</strong> {fmt.format(totalValue)}
        </p>
      </footer>
    </>
  );
}

export default function PortfolioPage() {
  const params = useParams<{ id: string }>();
  const id = params?.id ?? "";

  return (
    <Suspense
      fallback={
        <>
          <div className="page-head">
            <div>
              <div className="eyebrow">Portfolio 360</div>
              <h1>Carregando...</h1>
            </div>
          </div>
          <LoadingSkeleton lines={6} />
        </>
      }
    >
      <PortfolioContent id={id} />
    </Suspense>
  );
}
