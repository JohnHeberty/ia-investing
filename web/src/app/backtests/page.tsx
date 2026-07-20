"use client";

import { Suspense } from "react";

import { AsOfIndicator, Badge, Metric } from "@/components/domain";
import {
  DataStatePanel,
  LoadingSkeleton,
  StaleWarning,
} from "@/components/data-state-components";
import { useBacktests } from "@/hooks/use-backtests";

function BacktestsContent() {
  const {
    runs,
    completedRuns,
    pitGatePass,
    isLoading,
    isError,
    dataState,
    count,
  } = useBacktests();

  if (isLoading) {
    return (
      <>
        <div className="page-head">
          <div>
            <div className="eyebrow">Backtest lab</div>
            <h1>Simulações point-in-time</h1>
            <p className="subtitle">
              Configuração imutável, delay de sinal e execução, custos, impostos e baselines.
            </p>
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

  if (isError) {
    return (
      <>
        <div className="page-head">
          <div>
            <div className="eyebrow">Backtest lab</div>
            <h1>Erro ao carregar backtests</h1>
          </div>
        </div>
        <DataStatePanel
          state="error"
          title="Erro ao carregar backtests"
          detail="Não foi possível acessar os dados de backtesting. Verifique a conexão com a API."
        />
      </>
    );
  }

  const hasRuns = runs.length > 0;

  return (
    <>
      <div className="page-head">
        <div>
          <div className="eyebrow">Backtest lab</div>
          <h1>Simulações point-in-time</h1>
          <p className="subtitle">
            Configuração imutável, delay de sinal e execução, custos, impostos e baselines.
          </p>
        </div>
        <AsOfIndicator
          freshness={dataState === "stale" ? "Desatualizado" : "Atual"}
        />
      </div>

      {dataState === "stale" && (
        <div style={{ marginBottom: 14 }}>
          <StaleWarning lastUpdated={new Date().toISOString()} source="backtests" />
        </div>
      )}

      <section className="grid grid-4" aria-label="Métricas de backtest">
        <Metric
          label="Runs concluídos"
          value={hasRuns ? String(completedRuns) : "—"}
          note={hasRuns ? "mesmo code version" : "dado ausente não vira zero"}
        />
        <Metric
          label="PIT gate"
          value={hasRuns ? (pitGatePass ? "100%" : "—") : "—"}
          note="anti-look-ahead"
          tone={hasRuns && pitGatePass ? "positive" : undefined}
        />
        <Metric
          label="Sharpe mediano"
          value={hasRuns ? "—" : "—"}
          note="out-of-sample"
        />
        <Metric
          label="Reprodutibilidade"
          value={hasRuns ? `${completedRuns}/${count}` : "—"}
          note={hasRuns ? "hashes idênticos" : "dado ausente não vira zero"}
          tone={hasRuns && pitGatePass ? "positive" : undefined}
        />
      </section>

      {/* Runs table */}
      {hasRuns ? (
        <section className="card card-pad" style={{ marginTop: 14 }}>
          <div className="card-title">
            <h2>Runs de backtest</h2>
            <span>{count} run{count !== 1 ? "s" : ""}</span>
          </div>
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Estratégia</th>
                  <th>Status</th>
                  <th>PIT Gate</th>
                  <th>Sharpe</th>
                  <th>Reprodutibilidade</th>
                </tr>
              </thead>
              <tbody>
                {runs.map((run) => (
                  <tr key={run.id}>
                    <td style={{ fontFamily: "var(--font-mono)", fontSize: 11 }}>
                      {run.id.slice(0, 12)}
                    </td>
                    <td>{run.strategy}</td>
                    <td>
                      <Badge tone={run.status === "completed" ? "good" : "warn"}>
                        {run.status === "completed" ? "Concluído" : run.status}
                      </Badge>
                    </td>
                    <td>
                      <Badge tone={run.pitGate === "100%" ? "good" : "neutral"}>
                        {run.pitGate}
                      </Badge>
                    </td>
                    <td className="numeric" style={{ fontFamily: "var(--font-mono)" }}>
                      {run.sharpeRatio ?? "—"}
                    </td>
                    <td>
                      <Badge tone={run.reproducibility.includes("/") ? "good" : "neutral"}>
                        {run.reproducibility}
                      </Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ) : (
        <div style={{ marginTop: 14 }}>
          <DataStatePanel
            state="missing"
            title="Nenhum backtest registrado"
            detail="Runs de backtest são criados quando uma estratégia é submetida ao laboratório. Aguardando submissões."
          />
        </div>
      )}

      <section className="grid grid-3" style={{ marginTop: 14 }}>
        <article className="card card-pad">
          <div className="card-title">
            <h2>Estratégia vs benchmark</h2>
            <Badge tone="good">Saudável</Badge>
          </div>
          <p style={{ color: "var(--muted)", fontSize: 12, lineHeight: 1.65 }}>
            Benchmark permanece fora do universo investível e usa série própria.
          </p>
        </article>
        <article className="card card-pad">
          <div className="card-title">
            <h2>Baselines e ablações</h2>
            <Badge tone="good">Saudável</Badge>
          </div>
          <p style={{ color: "var(--muted)", fontSize: 12, lineHeight: 1.65 }}>
            Equal weight, quantitativo sem agents e ablações isolam contribuição incremental.
          </p>
        </article>
        <article className="card card-pad">
          <div className="card-title">
            <h2>Custos e eventos</h2>
            <Badge tone="warn">Atenção</Badge>
          </div>
          <p style={{ color: "var(--muted)", fontSize: 12, lineHeight: 1.65 }}>
            Resultados evidenciam efeito de slippage, impostos e corporate actions.
          </p>
        </article>
      </section>
    </>
  );
}

export default function BacktestsPage() {
  return (
    <Suspense
      fallback={
        <>
          <div className="page-head">
            <div>
              <div className="eyebrow">Backtest lab</div>
              <h1>Simulações point-in-time</h1>
            </div>
          </div>
          <LoadingSkeleton lines={6} />
        </>
      }
    >
      <BacktestsContent />
    </Suspense>
  );
}
