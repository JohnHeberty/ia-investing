"use client";

import { useParams } from "next/navigation";
import { Suspense } from "react";

import { AsOfIndicator, Badge, DomainTabs, Metric, StatePanel } from "@/components/domain";
import {
  DataStatePanel,
  LoadingSkeleton,
  StaleWarning,
} from "@/components/data-state-components";
import { ConfidenceBar, FreshnessPill } from "@/components/evidence-tags";
import { usePortfolio } from "@/hooks/use-portfolios";

// --- API-connected data will replace these placeholders ---

export function PortfolioContent({ id }: { id: string }) {
  const { portfolio, isLoading, isError, dataState } = usePortfolio(id);

  if (isLoading) {
    return (
      <>
        <div className="page-head">
          <div>
            <div className="eyebrow">Portfolio 360</div>
            <h1>Carregando…</h1>
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
        <DataStatePanel
          state={dataState}
          title="Erro ao carregar carteira"
          detail="Não foi possível acessar os dados desta carteira. Verifique o ID ou tente novamente."
        />
      </>
    );
  }

  const name = String(portfolio.name ?? "Carteira");
  const state = String(portfolio.state ?? "");
  const currency = String(portfolio.base_currency ?? "BRL");
  const environment = String(portfolio.environment ?? "");
  const updatedAt = String(portfolio.updated_at ?? portfolio.created_at ?? "");
  const mandateId = String(portfolio.mandate_id ?? "");
  const lockVersion = String(portfolio.lock_version ?? "0");
  const ownerTeamId = String(portfolio.owner_team_id ?? "");
  const organizationId = String(portfolio.organization_id ?? "");
  const createdAt = String(portfolio.created_at ?? "");
  const benchmark = String(portfolio.benchmark ?? "Ibovespa");
  const navReconciled = portfolio.nav_reconciled !== false;
  const methodology = String(portfolio.methodology ?? "nav-v1");

  const stateTone =
    state === "active" ? "good" : state === "draft" ? "warn" : "neutral";
  const stateLabel =
    state === "active" ? "Ativa" : state === "draft" ? "Rascunho" : state;

  return (
    <>
      <div className="page-head">
        <div>
          <div className="eyebrow">Portfolio 360</div>
          <h1>{name}</h1>
          <p className="subtitle">
            Carteira-modelo · {currency} · ambiente {environment} · mandato {mandateId.slice(0, 8) || "—"}
          </p>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <Badge tone={stateTone}>{stateLabel}</Badge>
          {updatedAt && <FreshnessPill retrievedAt={updatedAt} maxAgeHours={1} />}
          <AsOfIndicator
            value={updatedAt ? new Date(updatedAt).toLocaleString("pt-BR") : "—"}
            freshness={dataState === "stale" ? "Desatualizado" : "Atual"}
          />
        </div>
      </div>

      {dataState === "stale" && (
        <div style={{ marginBottom: 14 }}>
          <StaleWarning lastUpdated={updatedAt} source="model-portfolios" />
        </div>
      )}

      <section className="grid grid-4">
        <Metric label="Moeda base" value={currency} note={`Código: ${currency}`} />
        <Metric
          label="Estado"
          value={stateLabel}
          note={`Ambiente: ${environment}`}
          tone={stateTone}
        />
        <Metric
          label="Benchmark"
          value={benchmark}
          note="Índice de referência"
        />
        <Metric
          label="NAV Reconciliado"
          value={navReconciled ? "Sim" : "Não"}
          note={navReconciled ? "Conferido automaticamente" : "Pendente de conciliação"}
          tone={navReconciled ? "positive" : "warning"}
        />
      </section>

      <section className="grid grid-3" style={{ marginTop: 14 }}>
        <article className="card card-pad">
          <div className="card-title">
            <h2>Mandato</h2>
            <Badge tone="neutral">v{mandateId.slice(0, 8) || "—"}</Badge>
          </div>
          <p style={{ color: "var(--muted)", fontSize: 12, lineHeight: 1.65 }}>
            Mandato vinculado: {mandateId || "Não definido"}.
            A carteira opera sob as restrições e limites definidos pelo mandato.
          </p>
        </article>
        <article className="card card-pad">
          <div className="card-title">
            <h2>Ownership</h2>
          </div>
          <p style={{ color: "var(--muted)", fontSize: 12, lineHeight: 1.65 }}>
            Time responsável: {ownerTeamId || "Não atribuído"}.
            Organização: {organizationId || "—"}.
          </p>
        </article>
        <article className="card card-pad">
          <div className="card-title">
            <h2>Temporalidade</h2>
          </div>
          <p style={{ color: "var(--muted)", fontSize: 12, lineHeight: 1.65 }}>
            Criado em: {createdAt ? new Date(createdAt).toLocaleString("pt-BR") : "—"}.
            Atualizado em: {updatedAt ? new Date(updatedAt).toLocaleString("pt-BR") : "—"}.
          </p>
        </article>
      </section>

      <DomainTabs
        label="Detalhes da carteira"
        tabs={[
          {
            id: "positions",
            label: "Posições",
            content: (
              <StatePanel
                title="Posições"
                detail="Snapshot point-in-time reconciliado. As posições são resolvidas pelo instrumento e preço no cutoff."
              />
            ),
          },
          {
            id: "performance",
            label: "Performance",
            content: (
              <div>
                <div className="card card-pad" style={{ marginBottom: 14 }}>
                  <div className="card-title">
                    <h2>NAV e benchmark</h2>
                    <Badge tone="neutral">{methodology}</Badge>
                  </div>
                  <p style={{ color: "var(--muted)", fontSize: 12, lineHeight: 1.65 }}>
                    Metodologia: {methodology}, mesma moeda e mesmo cutoff.
                    Benchmark: {benchmark}.
                  </p>
                  <div style={{ marginTop: 12 }}>
                    <ConfidenceBar value={navReconciled ? 100 : 0} label="Conciliação" />
                  </div>
                </div>
                <StatePanel
                  title="Curva de performance"
                  detail="Gráfico de rendimento acumulado versus benchmark será exibido aqui."
                />
              </div>
            ),
          },
          {
            id: "risk",
            label: "Risco",
            content: (
              <StatePanel
                title="Risco"
                detail="Limites de risco, violações e exposições serão exibidos aqui quando conectados à API."
              />
            ),
          },
          {
            id: "theses",
            label: "Teses",
            content: (
              <StatePanel
                title="Teses"
                detail="Teses e propostas vinculadas a esta carteira serão exibidas aqui quando conectadas à API."
              />
            ),
          },
          {
            id: "audit",
            label: "Auditoria",
            content: (
              <StatePanel
                title="Auditoria"
                detail="Trilha de auditoria completa será exibida aqui quando conectada à API."
              />
            ),
          },
        ]}
      />

      <section style={{ marginTop: 14 }}>
        <StatePanel
          title="Rebalanceamento"
          detail="Diferenças entre pesos atuais e propostos serão exibidas aqui quando conectadas à API."
        />
      </section>

      {/* Methodology Footer */}
      <footer style={{ marginTop: 14, padding: "12px 0", borderTop: "1px solid var(--line-soft)", fontSize: 11, color: "var(--muted)" }}>
        <p>
          <strong>Metodologia:</strong> {methodology} · 
          <strong> Benchmark:</strong> {benchmark} · 
          <strong> Moeda:</strong> {currency} · 
          <strong> As of:</strong> {updatedAt ? new Date(updatedAt).toLocaleString("pt-BR") : "—"} · 
          <strong> Lock:</strong> v{lockVersion}
        </p>
        <p style={{ marginTop: 4 }}>
          Dados reconciliados automaticamente. Última conciliação: {updatedAt ? new Date(updatedAt).toLocaleString("pt-BR") : "—"}.
          Para dúvidas, contacte o time de Risk.
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
              <h1>Carregando…</h1>
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
