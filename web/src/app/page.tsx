"use client";

import Link from "next/link";

import { usePortfoliosList } from "@/hooks/use-portfolios";

const money = new Intl.NumberFormat("pt-BR", {
  style: "currency",
  currency: "BRL",
  maximumFractionDigits: 0,
});

export default function MissionControlPage() {
  const { portfolios, isLoading, isError, error, count } = usePortfoliosList();

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
          <p className="mono text-sm mt-8" style={{ wordBreak: "break-all" }}>
            {error?.message || "Erro desconhecido — verifique o console do navegador (F12)"}
          </p>
        </div>
      </>
    );
  }

  const totalPositions = portfolios.reduce((sum, p) => sum + (p.positions?.length || 0), 0);
  const totalValue = portfolios.reduce((sum, p) => {
    const positions = p.positions || [];
    return sum + positions.reduce((posSum: number, pos) => {
      const price = pos.current_price || pos.avg_cost_per_share || 0;
      return posSum + (pos.quantity * price);
    }, 0);
  }, 0);

  const totalCost = portfolios.reduce((sum, p) => {
    const positions = p.positions || [];
    return sum + positions.reduce((posSum: number, pos) => {
      return posSum + (pos.quantity * (pos.avg_cost_per_share || 0));
    }, 0);
  }, 0);
  const totalPnl = totalValue - totalCost;
  const totalPnlPercent = totalCost > 0 ? (totalPnl / totalCost) * 100 : 0;

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
          <Link href="/portfolios" className="button">
            + Nova Carteira
          </Link>
        </div>
      </header>

      <section className="grid grid-4 mt-24">
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
        <section className="card card-pad mt-24">
          <div className="card-title">
            <h2>Suas Carteiras</h2>
            <span className="mono">{count} {count === 1 ? "carteira" : "carteiras"}</span>
          </div>
          <div className="mt-16">
            {portfolios.map((portfolio) => {
              const positions = portfolio.positions || [];
              const value = positions.reduce((sum: number, pos) => {
                const price = pos.current_price || pos.avg_cost_per_share || 0;
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
                  className="flex items-center justify-between"
                  style={{ padding: "14px 0", borderBottom: "1px solid var(--line-soft)", textDecoration: "none", color: "inherit" }}
                >
                  <div>
                    <div className="fw-500 text-sm" style={{ fontSize: 14 }}>{portfolio.name}</div>
                    <div className="muted" style={{ fontSize: 12, marginTop: 2 }}>
                      {positions.length} posições · {portfolio.base_currency}
                    </div>
                  </div>
                  <div style={{ textAlign: "right" }}>
                    <div className="mono" style={{ fontSize: 14 }}>
                      {money.format(value)}
                    </div>
                    <div className={`mono ${pnl >= 0 ? "positive" : "negative"}`} style={{ fontSize: 12 }}>
                      {pnl >= 0 ? "+" : ""}{pnlPercent.toFixed(2)}%
                    </div>
                  </div>
                </Link>
              );
            })}
          </div>
        </section>
      )}

      <section className="card card-pad mt-24">
        <div className="card-title">
          <h2>Funcionalidades Disponíveis</h2>
        </div>
        <div className="grid grid-3 mt-16" style={{ gap: 12 }}>
          <Link href="/portfolios" style={{ textDecoration: "none", color: "inherit" }}>
            <div className="card" style={{ padding: 16, cursor: "pointer" }}>
              <div className="fw-500" style={{ marginBottom: 4 }}>📊 Carteiras</div>
              <div className="muted text-sm">
                Gerenciar carteiras e posições
              </div>
            </div>
          </Link>
          <Link href="/rebalance" style={{ textDecoration: "none", color: "inherit" }}>
            <div className="card" style={{ padding: 16, cursor: "pointer" }}>
              <div className="fw-500" style={{ marginBottom: 4 }}>⚖️ Rebalance</div>
              <div className="muted text-sm">
                Análise de drift e rebalanceamento
              </div>
            </div>
          </Link>
          <Link href="/risk" style={{ textDecoration: "none", color: "inherit" }}>
            <div className="card" style={{ padding: 16, cursor: "pointer" }}>
              <div className="fw-500" style={{ marginBottom: 4 }}>🛡️ Risco</div>
              <div className="muted text-sm">
                Monitoramento de risco
              </div>
            </div>
          </Link>
          <Link href="/opportunities" style={{ textDecoration: "none", color: "inherit" }}>
            <div className="card" style={{ padding: 16, cursor: "pointer" }}>
              <div className="fw-500" style={{ marginBottom: 4 }}>🎯 Oportunidades</div>
              <div className="muted text-sm">
                Análise de candidatos
              </div>
            </div>
          </Link>
          <Link href="/committee" style={{ textDecoration: "none", color: "inherit" }}>
            <div className="card" style={{ padding: 16, cursor: "pointer" }}>
              <div className="fw-500" style={{ marginBottom: 4 }}>🏛️ Comitê</div>
              <div className="muted text-sm">
                Decisões de investimento
              </div>
            </div>
          </Link>
          <Link href="/data-quality" style={{ textDecoration: "none", color: "inherit" }}>
            <div className="card" style={{ padding: 16, cursor: "pointer" }}>
              <div className="fw-500" style={{ marginBottom: 4 }}>✅ Qualidade</div>
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
