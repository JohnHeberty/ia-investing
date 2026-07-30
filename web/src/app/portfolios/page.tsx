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
            Gerencie suas carteiras de investimento. Crie novas carteiras, acompanhe posições e receba recomendações dos agents.
          </p>
        </div>
        <button
          className="button"
          onClick={() => setShowCreateForm(true)}
        >
          + Nova Carteira
        </button>
      </header>

      {showCreateForm && (
        <div style={{ marginBottom: 24 }}>
          <CreatePortfolioForm onClose={() => setShowCreateForm(false)} />
        </div>
      )}

      {count === 0 ? (
        <div className="state-panel" data-state="empty">
          <strong>Nenhuma carteira encontrada</strong>
          <p>Crie sua primeira carteira para começar a gerenciar investimentos.</p>
          <button
            className="button"
            onClick={() => setShowCreateForm(true)}
            style={{ marginTop: 12 }}
          >
            Criar Carteira
          </button>
        </div>
      ) : (
        <div className="grid grid-3" style={{ gap: 16 }}>
          {portfolios.map((portfolio) => (
            <Link
              key={portfolio.id}
              href={`/portfolios/${portfolio.id}`}
              style={{ textDecoration: "none", color: "inherit" }}
            >
              <article className="card card-pad" style={{ cursor: "pointer", transition: "border-color 0.2s" }}>
                <div className="card-title">
                  <h2 style={{ fontSize: 16 }}>{portfolio.name}</h2>
                  <span className="badge" data-tone={portfolio.is_paper_trading ? "warn" : "good"}>
                    {portfolio.is_paper_trading ? "Paper" : "Live"}
                  </span>
                </div>

                <div style={{ marginTop: 12, display: "flex", flexDirection: "column", gap: 8 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", fontSize: 13 }}>
                    <span style={{ color: "var(--muted)" }}>Moeda</span>
                    <span style={{ color: "var(--text)", fontWeight: 500 }}>{portfolio.base_currency}</span>
                  </div>

                  {portfolio.initial_capital && (
                    <div style={{ display: "flex", justifyContent: "space-between", fontSize: 13 }}>
                      <span style={{ color: "var(--muted)" }}>Capital Inicial</span>
                      <span style={{ color: "var(--text)", fontWeight: 500 }}>
                        {new Intl.NumberFormat("pt-BR", { style: "currency", currency: portfolio.base_currency }).format(portfolio.initial_capital)}
                      </span>
                    </div>
                  )}

                  {portfolio.description && (
                    <p style={{ marginTop: 8, fontSize: 12, color: "var(--muted)", lineHeight: 1.5 }}>
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
