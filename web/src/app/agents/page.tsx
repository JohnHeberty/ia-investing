"use client";

import { Suspense } from "react";

import { AsOfIndicator, Badge, Metric } from "@/components/domain";
import {
  DataStatePanel,
  LoadingSkeleton,
  StaleWarning,
} from "@/components/data-state-components";
import { useAgentRuns } from "@/hooks/use-agent-runs";
import { useUrlState, filterPresets } from "@/hooks/use-url-state";

function AgentsContent() {
  const [urlState, setUrlState] = useUrlState(filterPresets.agents);
  const {
    runs,
    completedRuns,
    failedRuns,
    totalCost,
    isLoading,
    isError,
    dataState,
    count,
  } = useAgentRuns({
    status: urlState.status ?? undefined,
    agent_name: urlState.capability ?? undefined,
  });

  if (isLoading) {
    return (
      <>
        <div className="page-head">
          <div>
            <div className="eyebrow">Agent operations</div>
            <h1>Runtime governado</h1>
            <p className="subtitle">
              Runs fixam prompt, schema, modelo, tools, budget e knowledge cutoff.
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
            <div className="eyebrow">Agent operations</div>
            <h1>Runtime governado</h1>
          </div>
        </div>
        <DataStatePanel
          state="error"
          title="Erro ao carregar runs"
          detail="Não foi possível acessar os dados de execução dos agents."
        />
      </>
    );
  }

  const successRate = count > 0 ? Math.round((completedRuns / count) * 100) : 0;
  const totalTokens = runs.reduce((sum, r) => sum + r.prompt_tokens + r.completion_tokens, 0);

  return (
    <>
      <div className="page-head">
        <div>
          <div className="eyebrow">Agent operations</div>
          <h1>Runtime governado</h1>
          <p className="subtitle">
            Runs fixam prompt, schema, modelo, tools, budget e knowledge cutoff.
          </p>
        </div>
        <AsOfIndicator
          value={new Date().toLocaleString("pt-BR", { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" })}
          freshness={dataState === "stale" ? "Desatualizado" : "Atual"}
        />
      </div>

      {dataState === "stale" && (
        <div style={{ marginBottom: 14 }}>
          <StaleWarning lastUpdated={new Date().toISOString()} source="agents/runs" />
        </div>
      )}

      <section className="grid grid-4" aria-label="Métricas de agents">
        <Metric
          label="Runs hoje"
          value={String(count)}
          note={`${completedRuns} concluídos`}
        />
        <Metric
          label="Taxa de sucesso"
          value={`${successRate}%`}
          note="últimos 7 dias"
          tone={successRate >= 95 ? "positive" : successRate >= 80 ? "warning" : "negative"}
        />
        <Metric
          label="Guardrail trips"
          value={String(failedRuns)}
          note={failedRuns > 0 ? "falharam fechados" : "nenhum"}
          tone={failedRuns > 0 ? "warning" : undefined}
        />
        <Metric
          label="Custo"
          value={`US$ ${totalCost.toFixed(2)}`}
          note={`${totalTokens.toLocaleString("pt-BR")} tokens`}
        />
      </section>

      <section className="grid grid-3" style={{ marginTop: 14 }}>
        <article className="card card-pad">
          <div className="card-title">
            <h2>Versions e evals</h2>
            <Badge tone="good">Saudável</Badge>
          </div>
          <p style={{ color: "var(--muted)", fontSize: 12, lineHeight: 1.65 }}>
            Versões ativas passaram pelos thresholds de schema e citation coverage.
            Cada run é versionada e rastreável.
          </p>
        </article>
        <article className="card card-pad">
          <div className="card-title">
            <h2>Tool calls</h2>
            <Badge tone="good">Saudável</Badge>
          </div>
          <p style={{ color: "var(--muted)", fontSize: 12, lineHeight: 1.65 }}>
            Allowlist, argumentos sanitizados, custo e duração permanecem vinculados ao run.
          </p>
        </article>
        <article className="card card-pad">
          <div className="card-title">
            <h2>Approvals</h2>
            <Badge tone="warn">Atenção</Badge>
          </div>
          <p style={{ color: "var(--muted)", fontSize: 12, lineHeight: 1.65 }}>
            Dois commands sensíveis aguardam decisão humana independente.
            Aprovações seguem princípio dos quatro olhos.
          </p>
        </article>
      </section>

      {runs.length > 0 && (
        <section className="card card-pad" style={{ marginTop: 14 }}>
          <div className="card-title">
            <h2>Runs recentes</h2>
            <span>{count} execuções</span>
          </div>
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Status</th>
                  <th>Capability</th>
                  <th className="numeric">Duração</th>
                  <th className="numeric">Custo</th>
                  <th className="numeric">Tokens</th>
                  <th>Criação</th>
                </tr>
              </thead>
              <tbody>
                {runs.slice(0, 10).map((run) => (
                  <tr key={run.id}>
                    <td className="rank">{run.id.slice(0, 8)}…</td>
                    <td>
                      <Badge
                        tone={
                          run.status === "succeeded"
                            ? "good"
                            : run.status === "failed"
                              ? "bad"
                              : run.status === "running"
                                ? "warn"
                                : "neutral"
                        }
                      >
                        {run.status === "succeeded"
                          ? "Sucesso"
                          : run.status === "failed"
                            ? "Falha"
                            : run.status === "running"
                              ? "Executando"
                              : run.status}
                      </Badge>
                    </td>
                    <td>{run.capability_id.slice(0, 8)}…</td>
                    <td className="numeric" style={{ fontFamily: "var(--font-mono)" }}>
                      {run.duration_ms != null ? `${(run.duration_ms / 1000).toFixed(1)}s` : "—"}
                    </td>
                    <td className="numeric" style={{ fontFamily: "var(--font-mono)" }}>
                      US$ {parseFloat(run.cost_usd).toFixed(4)}
                    </td>
                    <td className="numeric" style={{ fontFamily: "var(--font-mono)" }}>
                      {(run.prompt_tokens + run.completion_tokens).toLocaleString("pt-BR")}
                    </td>
                    <td style={{ color: "var(--muted)", fontSize: 11 }}>
                      {new Date(run.created_at).toLocaleString("pt-BR", {
                        day: "2-digit",
                        month: "short",
                        hour: "2-digit",
                        minute: "2-digit",
                      })}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {runs.length === 0 && (
        <div style={{ marginTop: 14 }}>
          <DataStatePanel
            state="missing"
            title="Nenhum run encontrado"
            detail="Nenhuma execução de agent foi registrada. Verifique se os agents estão configurados."
          />
        </div>
      )}
    </>
  );
}

export default function AgentsPage() {
  return (
    <Suspense
      fallback={
        <>
          <div className="page-head">
            <div>
              <div className="eyebrow">Agent operations</div>
              <h1>Runtime governado</h1>
            </div>
          </div>
          <LoadingSkeleton lines={6} />
        </>
      }
    >
      <AgentsContent />
    </Suspense>
  );
}
