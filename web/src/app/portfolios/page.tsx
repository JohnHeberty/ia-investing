"use client";

import { useState } from "react";
import Link from "next/link";

import { CreatePortfolioForm } from "@/components/create-portfolio-form";
import { usePortfoliosList } from "@/hooks/use-portfolios";

export default function PortfoliosPage() {
  const { portfolios, isLoading, isError, error, count } = usePortfoliosList();
  const [showCreateForm, setShowCreateForm] = useState(false);

  if (isLoading) {
    return (
      <>
        <header className="page-head">
          <div>
            <div className="eyebrow">Portfolio Intelligence</div>
            <h1>Carteiras</h1>
          </div>
        </header>
        <div className="state-panel">
          <strong>Carregando carteiras</strong>
          Consultando suas carteiras...
        </div>
      </>
    );
  }

  if (isError) {
    return (
      <>
        <header className="page-head">
          <div>
            <div className="eyebrow">Portfolio Intelligence</div>
            <h1>Carteiras</h1>
          </div>
        </header>
        <div className="state-panel" data-state="error" role="alert">
          <strong>Erro ao carregar</strong>
          {error?.message || "Não foi possível carregar as carteiras."}
        </div>
      </>
    );
  }

  return (
    <>
      <header className="page-head">
        <div>
          <div className="eyebrow">Portfolio Intelligence</div>
          <h1>Carteiras</h1>
          <p className="subtitle">
            Gerencie suas carteiras de investimento. Crie novas carteiras, acompanhe posições e
            receba recomendações dos agents.
          </p>
        </div>
        <button className="button" onClick={() => setShowCreateForm(true)}>
          + Nova Carteira
        </button>
      </header>

      {showCreateForm && (
        <div className="mb-16">
          <CreatePortfolioForm onClose={() => setShowCreateForm(false)} />
        </div>
      )}

      {count === 0 ? (
        <div className="state-panel" data-state="empty">
          <strong>Nenhuma carteira encontrada</strong>
          <p>Crie sua primeira carteira para começar a gerenciar investimentos.</p>
          <button className="button mt-12" onClick={() => setShowCreateForm(true)}>
            Criar Carteira
          </button>
        </div>
      ) : (
        <div className="grid grid-3 gap-16">
          {portfolios.map((portfolio) => (
            <Link
              key={portfolio.id}
              href={`/portfolios/${portfolio.id}`}
              className="no-underline text-inherit"
            >
              <article className="card card-pad cursor-pointer transition-border">
                <div className="card-title">
                  <h2 className="text-16">{portfolio.name}</h2>
                  <span className="badge" data-tone={portfolio.is_paper_trading ? "warn" : "good"}>
                    {portfolio.is_paper_trading ? "Paper" : "Live"}
                  </span>
                </div>

                <div className="flex flex-col gap-8 mt-12">
                  <div className="detail-row">
                    <span className="detail-row-label">Moeda</span>
                    <span className="detail-row-value">{portfolio.base_currency}</span>
                  </div>

                  {portfolio.initial_capital && (
                    <div className="detail-row">
                      <span className="detail-row-label">Capital Inicial</span>
                      <span className="detail-row-value">
                        {new Intl.NumberFormat("pt-BR", {
                          style: "currency",
                          currency: portfolio.base_currency,
                        }).format(portfolio.initial_capital)}
                      </span>
                    </div>
                  )}

                  {portfolio.description && (
                    <p className="mt-8 text-12 text-muted leading-relaxed">
                      {portfolio.description.length > 100
                        ? `${portfolio.description.slice(0, 100)}...`
                        : portfolio.description}
                    </p>
                  )}
                </div>
              </article>
            </Link>
          ))}
        </div>
      )}
    </>
  );
}
