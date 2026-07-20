"use client";

import { Suspense } from "react";

import { AsOfIndicator, Badge, Metric, StatePanel } from "@/components/domain";
import {
  DataStatePanel,
  LoadingSkeleton,
  StaleWarning,
} from "@/components/data-state-components";
import { usePaper } from "@/hooks/use-paper";

function PaperContent() {
  const {
    orders,
    approvedIntents,
    partialFills,
    criticalBreaks,
    isLoading,
    isError,
    dataState,
  } = usePaper();

  if (isLoading) {
    return (
      <>
        <div className="page-head">
          <div>
            <div className="eyebrow">Paper operations</div>
            <h1>Execução simulada e reconciliada.</h1>
            <p className="subtitle">
              Intents, orders, fills, custos e breaks. Nenhuma integração ou credencial de
              corretora.
            </p>
          </div>
        </div>
        <section className="grid grid-4">
          <LoadingSkeleton lines={4} />
          <LoadingSkeleton lines={4} />
          <LoadingSkeleton lines={4} />
          <LoadingSkeleton lines={4} />
        </section>
        <section style={{ marginTop: 14 }}>
          <LoadingSkeleton lines={6} />
        </section>
      </>
    );
  }

  if (isError) {
    return (
      <>
        <div className="page-head">
          <div>
            <div className="eyebrow">Paper operations</div>
            <h1>Erro ao carregar dados paper</h1>
          </div>
        </div>
        <DataStatePanel
          state="error"
          title="Erro ao carregar operações paper"
          detail="Não foi possível acessar os trade intents. Verifique a conexão com a API."
        />
      </>
    );
  }

  const hasLiveOrders = orders.length > 0;

  return (
    <>
      <div className="page-head">
        <div>
          <div className="eyebrow">Paper operations</div>
          <h1>Execução simulada e reconciliada.</h1>
          <p className="subtitle">
            Intents, orders, fills, custos e breaks. Nenhuma integração ou credencial de corretora.
          </p>
        </div>
        <AsOfIndicator
          freshness={hasLiveOrders ? "Paper live" : "Paper only"}
        />
      </div>

      {dataState === "stale" && (
        <div style={{ marginBottom: 14 }}>
          <StaleWarning lastUpdated={new Date().toISOString()} source="paper/trade-intents" />
        </div>
      )}

      <section className="grid grid-4">
        <Metric
          label="Intents aprovados"
          value={hasLiveOrders ? String(approvedIntents) : "—"}
          note="four-eyes"
        />
        <Metric
          label="Partial fills"
          value={hasLiveOrders ? String(partialFills) : "—"}
          note={hasLiveOrders ? "sim-v1" : "dado ausente não vira zero"}
          tone={partialFills > 0 ? "warning" : undefined}
        />
        <Metric
          label="Breaks críticos"
          value={hasLiveOrders ? String(criticalBreaks) : "—"}
          note={criticalBreaks > 0 ? "novos submits bloqueados" : "nenhum break"}
          tone={criticalBreaks > 0 ? "negative" : undefined}
        />
        <Metric
          label="Slippage"
          value={hasLiveOrders ? "—" : "—"}
          note="spread + impacto"
        />
      </section>

      <section className="card card-pad" style={{ marginTop: 14 }}>
        <div className="card-title">
          <h2>Order lifecycle</h2>
          <Badge tone="warn">PAPER</Badge>
        </div>
        {hasLiveOrders ? (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Intent</th>
                  <th>Versão aprovada</th>
                  <th>Estado</th>
                  <th className="numeric">Fill</th>
                  <th>Reconciliação</th>
                </tr>
              </thead>
              <tbody>
                {orders.map((order) => (
                  <tr key={order.id}>
                    <td>{order.intent}</td>
                    <td>{order.version}</td>
                    <td>
                      <Badge
                        tone={
                          order.status === "filled"
                            ? "good"
                            : order.status === "partially_filled"
                              ? "warn"
                              : order.status === "rejected"
                                ? "bad"
                                : "neutral"
                        }
                      >
                        {order.status === "filled"
                          ? "Filled"
                          : order.status === "partially_filled"
                            ? "Partially filled"
                            : order.status === "approved"
                              ? "Approved"
                              : order.status}
                      </Badge>
                    </td>
                    <td className="numeric">
                      {order.fillQuantity} / {order.fillTotal}
                    </td>
                    <td>
                      <Badge
                        tone={
                          order.reconciliation === "matched"
                            ? "good"
                            : order.reconciliation === "break"
                              ? "bad"
                              : "warn"
                        }
                      >
                        {order.reconciliation === "matched"
                          ? "Matched"
                          : order.reconciliation === "break"
                            ? "Break aberto"
                            : order.reconciliation}
                      </Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <DataStatePanel
            state="empty"
            title="Nenhum trade intent registrado"
            detail="Orders são criadas a partir de aprovações de committee. Nenhuma execução paper no momento."
          />
        )}
      </section>

      <section className="grid grid-3" style={{ marginTop: 14 }}>
        <article className="card card-pad">
          <h2>Break crítico</h2>
          <p className="subtitle">
            Order/fill/ledger divergente. Alerta deduplicado, owner Operations, submit bloqueado.
          </p>
        </article>
        <article className="card card-pad">
          <h2>Kill switch</h2>
          <p className="subtitle">
            Escopo global ou carteira; liberação exige segundo operador e permanece auditada.
          </p>
        </article>
        <article className="card card-pad">
          <h2>Post-mortem</h2>
          <p className="subtitle">
            Resultado ligado a versão, tese, agents, decisão e trades com relatório imutável.
          </p>
        </article>
      </section>

      <div style={{ marginTop: 14 }}>
        <StatePanel
          title="Ambiente PAPER"
          detail="A UI não oferece send-order live. Cancelamento, leitura e reconciliação permanecem disponíveis durante suspensão."
        />
      </div>
    </>
  );
}

export default function PaperOperationsPage() {
  return (
    <Suspense
      fallback={
        <>
          <div className="page-head">
            <div>
              <div className="eyebrow">Paper operations</div>
              <h1>Execução simulada e reconciliada.</h1>
            </div>
          </div>
          <LoadingSkeleton lines={6} />
        </>
      }
    >
      <PaperContent />
    </Suspense>
  );
}
