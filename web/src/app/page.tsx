"use client";

import Link from "next/link";
import { useMemo } from "react";

import { usePortfoliosList } from "@/hooks/use-portfolios";

const money = new Intl.NumberFormat("pt-BR", {
  style: "currency",
  currency: "BRL",
  maximumFractionDigits: 0,
});

export default function MissionControlPage() {
  const { portfolios, isLoading, isError, error, count } = usePortfoliosList();

  const totalPositions = useMemo(
    () => portfolios.reduce((sum, p) => sum + (p.positions?.length || 0), 0),
    [portfolios],
  );

  const totalValue = useMemo(
    () =>
      portfolios.reduce((sum, p) => {
        const positions = p.positions || [];
        return (
          sum +
          positions.reduce((posSum: number, pos) => {
            const price = pos.current_price ?? pos.avg_cost_per_share ?? 0;
            return posSum + pos.quantity * price;
          }, 0)
        );
      }, 0),
    [portfolios],
  );

  const totalCost = useMemo(
    () =>
      portfolios.reduce((sum, p) => {
        const positions = p.positions || [];
        return (
          sum +
          positions.reduce((posSum: number, pos) => {
            return posSum + pos.quantity * (pos.avg_cost_per_share || 0);
          }, 0)
        );
      }, 0),
    [portfolios],
  );

  const totalPnl = totalValue - totalCost;
  const totalPnlPercent = totalCost > 0 ? (totalPnl / totalCost) * 100 : 0;

  if (isLoading) {
    return (
      <div className="state-panel" aria-busy="true">
        <strong>Carregando Dashboard</strong>
        Consultando suas carteiras...
      </div>
    );
  }

  if (isError) {
    return (
      <>
        <header className="page-head">
          <div>
            <div className="eyebrow">Investment Operations</div>
            <h1>Erro ao carregar</h1>
          </div>
        </header>
        <div className="state-panel" data-state="error" role="alert">
          <strong>Erro ao carregar dashboard</strong>
          <p className="mono text-sm mt-8 truncate">
            {error?.message || "Erro desconhecido — verifique o console do navegador (F12)"}
          </p>
        </div>
      </>
    );
  }

  return (
    <>
      <header className="page-head">
        <div>
          <div className="eyebrow">Investment Operations</div>
          <h1>Mission Control</h1>
          <p className="subtitle">
            Visão geral das suas carteiras de investimento e operações.
          </p>
        </div>
        <div className="flex gap-8">
          <Link href="/portfolios" className="button secondary">
            Ver Carteiras
          </Link>
          <Link
            href="/portfolios?create=true"
            className="button secondary text-accent border-accent"
          >
            + Nova Carteira
          </Link>
        </div>
      </header>

      <section className="grid grid-4 section-gap" aria-live="polite">
        <div className="card metric">
          <div className="metric-label">Carteiras</div>
          <div className="metric-value">{count}</div>
          <div className="metric-note">Total de carteiras</div>
        </div>
        <div className="card metric">
          <div className="metric-label">Posições</div>
          <div className="metric-value">{totalPositions}</div>
          <div className="metric-note">Total de posições</div>
        </div>
        <div className="card metric">
          <div className="metric-label">Valor Total</div>
          <div className="metric-value">{money.format(totalValue)}</div>
          <div className="metric-note">Patrimônio investido</div>
        </div>
        <div className="card metric">
          <div className="metric-label">P&L Geral</div>
          <div className={`metric-value ${totalPnl >= 0 ? "positive" : "negative"}`}>
            {totalPnl >= 0 ? "+" : ""}{totalPnlPercent.toFixed(1)}%
          </div>
          <div className="metric-note">{money.format(totalPnl)}</div>
        </div>
      </section>

      {count === 0 ? (
        <div className="state-panel mt-24" data-state="empty">
          <strong>Nenhuma carteira encontrada</strong>
          <p>Crie sua primeira carteira para começar a gerenciar investimentos.</p>
          <Link href="/portfolios" className="button mt-12">
            Criar Carteira
          </Link>
        </div>
      ) : (
        <section className="card card-pad section-gap">
          <div className="card-title">
            <h2>Suas Carteiras</h2>
            <span className="mono">{count} {count === 1 ? "carteira" : "carteiras"}</span>
          </div>
          <div className="mt-16">
            {portfolios.map((portfolio) => {
              const positions = portfolio.positions || [];
              const value = positions.reduce((sum: number, pos) => {
                const price = pos.current_price ?? pos.avg_cost_per_share ?? 0;
                return sum + (pos.quantity * price);
              }, 0);
              const cost = positions.reduce((sum: number, pos) => {
                return sum + (pos.quantity * (pos.avg_cost_per_share || 0));
              }, 0);
              const pnl = value - cost;
              const pnlPercent = cost > 0 ? (pnl / cost) * 100 : 0;

              return (
                <Link
                  key={portfolio.id}
                  href={`/portfolios/${portfolio.id}`}
                  className="flex items-center justify-between portfolio-row"
                >
                  <div>
                    <div className="fw-500 text-14">{portfolio.name}</div>
                    <div className="muted text-12 mt-2">
                      {positions.length} posições · {portfolio.base_currency}
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="mono text-14">
                      {money.format(value)}
                    </div>
                    <div className={`mono text-12 ${pnl >= 0 ? "positive" : "negative"}`}>
                      {pnl >= 0 ? "+" : ""}{pnlPercent.toFixed(2)}%
                    </div>
                  </div>
                </Link>
              );
            })}
          </div>
        </section>
      )}

      <section className="card card-pad section-gap">
        <div className="card-title">
          <h2>Funcionalidades Disponíveis</h2>
        </div>
        <div className="grid grid-3 mt-16 gap-12">
          <Link href="/portfolios" className="no-underline text-inherit">
            <div className="card feature-tile">
              <div className="fw-500 feature-tile-title">📊 Carteiras</div>
              <div className="muted text-sm">
                Gerenciar carteiras e posições
              </div>
            </div>
          </Link>
          <Link href="/rebalance" className="no-underline text-inherit">
            <div className="card feature-tile">
              <div className="fw-500 feature-tile-title">⚖️ Rebalance</div>
              <div className="muted text-sm">
                Análise de drift e rebalanceamento
              </div>
            </div>
          </Link>
          <Link href="/risk" className="no-underline text-inherit">
            <div className="card feature-tile">
              <div className="fw-500 feature-tile-title">🛡️ Risco</div>
              <div className="muted text-sm">
                Monitoramento de risco
              </div>
            </div>
          </Link>
          <Link href="/opportunities" className="no-underline text-inherit">
            <div className="card feature-tile">
              <div className="fw-500 feature-tile-title">🎯 Oportunidades</div>
              <div className="muted text-sm">
                Análise de candidatos
              </div>
            </div>
          </Link>
          <Link href="/committee" className="no-underline text-inherit">
            <div className="card feature-tile">
              <div className="fw-500 feature-tile-title">🏛️ Comitê</div>
              <div className="muted text-sm">
                Decisões de investimento
              </div>
            </div>
          </Link>
          <Link href="/data-quality" className="no-underline text-inherit">
            <div className="card feature-tile">
              <div className="fw-500 feature-tile-title">✅ Qualidade</div>
              <div className="muted text-sm">
                Monitoramento de dados
              </div>
            </div>
          </Link>
        </div>
      </section>
    </>
  );
}
