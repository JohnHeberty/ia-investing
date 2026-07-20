"use client";

import { Suspense } from "react";

import { AsOfIndicator, Badge, Metric } from "@/components/domain";
import {
  DataStatePanel,
  LoadingSkeleton,
  StaleWarning,
} from "@/components/data-state-components";
import { useMacro } from "@/hooks/use-macro";

function MacroContent() {
  const {
    macroSeries,
    selic,
    ipca,
    usdBrl,
    staleSeries,
    missingSeries,
    totalSeries,
    isLoading,
    isError,
    dataState,
  } = useMacro();

  if (isLoading) {
    return (
      <>
        <div className="page-head">
          <div>
            <div className="eyebrow">Macro intelligence</div>
            <h1>Regime e séries macro</h1>
            <p className="subtitle">
              Séries BCB/SIDRA preservam data efetiva, publicação, knowledge cutoff e revisão
              conhecida no as_of.
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
            <div className="eyebrow">Macro intelligence</div>
            <h1>Erro ao carregar séries macro</h1>
          </div>
        </div>
        <DataStatePanel
          state="error"
          title="Erro ao carregar dados macro"
          detail="Não foi possível acessar as séries macroeconômicas. Verifique a conexão com a API."
        />
      </>
    );
  }

  // Key indicators — use "—" for missing data, never 0
  const selicValue = selic?.value ?? "—";
  const ipcaValue = ipca?.value ?? "—";
  const usdBrlValue = usdBrl?.value ?? "—";

  return (
    <>
      <div className="page-head">
        <div>
          <div className="eyebrow">Macro intelligence</div>
          <h1>Regime e séries macro</h1>
          <p className="subtitle">
            Séries BCB/SIDRA preservam data efetiva, publicação, knowledge cutoff e revisão
            conhecida no as_of.
          </p>
        </div>
        <AsOfIndicator
          freshness={dataState === "stale" ? "Desatualizado" : "Atual"}
        />
      </div>

      {dataState === "stale" && (
        <div style={{ marginBottom: 14 }}>
          <StaleWarning lastUpdated={new Date().toISOString()} source="sources/health" />
        </div>
      )}

      <section className="grid grid-4" aria-label="Indicadores macro">
        <Metric
          label="SELIC"
          value={selicValue}
          note={selic?.value ? `fonte: ${selic.source}` : "dado ausente não vira zero"}
          tone={selic?.status === "stale" ? "warning" : undefined}
        />
        <Metric
          label="IPCA"
          value={ipcaValue}
          note={ipca?.value ? `fonte: ${ipca.source}` : "aguardando observação válida"}
          tone={ipca?.status === "stale" ? "warning" : undefined}
        />
        <Metric
          label="USD/BRL"
          value={usdBrlValue}
          note={usdBrl?.value ? `fonte: ${usdBrl.source}` : "freshness não confirmada"}
          tone={usdBrl?.status === "stale" ? "warning" : undefined}
        />
        <Metric
          label="Séries stale"
          value={String(staleSeries)}
          note={staleSeries > 0 ? "alerta de qualidade" : "todas atualizadas"}
          tone={staleSeries > 0 ? "negative" : "positive"}
        />
      </section>

      {/* Series detail table */}
      {macroSeries.length > 0 ? (
        <section className="card card-pad" style={{ marginTop: 14 }}>
          <div className="card-title">
            <h2>Séries monitoradas</h2>
            <span>{totalSeries} série{totalSeries !== 1 ? "s" : ""}</span>
          </div>
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Série</th>
                  <th>Valor</th>
                  <th>Fonte</th>
                  <th>Frequência</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {macroSeries.map((series) => (
                  <tr key={series.id}>
                    <td style={{ fontWeight: 600 }}>{series.name}</td>
                    <td className="numeric" style={{ fontFamily: "var(--font-mono)" }}>
                      {series.value ?? "—"}
                    </td>
                    <td style={{ color: "var(--muted)", fontSize: 12 }}>{series.source}</td>
                    <td style={{ color: "var(--muted)", fontSize: 12 }}>{series.frequency}</td>
                    <td>
                      <Badge
                        tone={
                          series.status === "ok"
                            ? "good"
                            : series.status === "stale"
                              ? "warn"
                              : "bad"
                        }
                      >
                        {series.status === "ok"
                          ? "Atual"
                          : series.status === "stale"
                            ? "Stale"
                            : "Ausente"}
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
            title="Nenhuma série macro registrada"
            detail="Séries macroeconômicas não foram configuradas. Dados ausentes são preservados como '—' e nunca convertidos em zero."
          />
        </div>
      )}

      <section className="grid grid-3" style={{ marginTop: 14 }}>
        <article className="card card-pad">
          <div className="card-title">
            <h2>Revisões point-in-time</h2>
            <Badge tone="warn">Atenção</Badge>
          </div>
          <p style={{ color: "var(--muted)", fontSize: 12, lineHeight: 1.65 }}>
            Cada revisão cria nova observação; valores anteriormente conhecidos permanecem
            reproduzíveis.
          </p>
        </article>
        <article className="card card-pad">
          <div className="card-title">
            <h2>Cenário base</h2>
            <Badge tone={staleSeries > 0 ? "warn" : "good"}>
              {staleSeries > 0 ? "Atenção" : "Saudável"}
            </Badge>
          </div>
          <p style={{ color: "var(--muted)", fontSize: 12, lineHeight: 1.65 }}>
            Nenhum cenário é publicado enquanto séries obrigatórias estiverem stale ou missing.
          </p>
        </article>
        <article className="card card-pad">
          <div className="card-title">
            <h2>Lineage</h2>
            <Badge tone="good">Saudável</Badge>
          </div>
          <p style={{ color: "var(--muted)", fontSize: 12, lineHeight: 1.65 }}>
            Definição da série, transformação, raw object e knowledge_at acompanham cada resultado.
          </p>
        </article>
      </section>
    </>
  );
}

export default function MacroPage() {
  return (
    <Suspense
      fallback={
        <>
          <div className="page-head">
            <div>
              <div className="eyebrow">Macro intelligence</div>
              <h1>Regime e séries macro</h1>
            </div>
          </div>
          <LoadingSkeleton lines={6} />
        </>
      }
    >
      <MacroContent />
    </Suspense>
  );
}
