"use client";

import { Suspense } from "react";

import { AsOfIndicator, Badge, Metric, StatePanel } from "@/components/domain";
import {
  DataStatePanel,
  LoadingSkeleton,
  StaleWarning,
} from "@/components/data-state-components";
import { usePolicy } from "@/hooks/use-policy";

function PolicyContent() {
  const {
    policyEvents,
    materialEvents,
    monitoredObjects,
    staleSources,
    isLoading,
    isError,
    dataState,
  } = usePolicy();

  if (isLoading) {
    return (
      <>
        <div className="page-head">
          <div>
            <div className="eyebrow">Policy intelligence</div>
            <h1>Fato, chance e impacto separados.</h1>
            <p className="subtitle">
              Tracker legislativo versionado, com fonte oficial, diff, intervalo e caminho de
              exposição.
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
            <div className="eyebrow">Policy intelligence</div>
            <h1>Erro ao carregar dados de política</h1>
          </div>
        </div>
        <DataStatePanel
          state="error"
          title="Erro ao carregar dados de política"
          detail="Não foi possível acessar os eventos políticos. Verifique a conexão com a API."
        />
      </>
    );
  }

  const hasLiveEvents = policyEvents.length > 0;

  return (
    <>
      <div className="page-head">
        <div>
          <div className="eyebrow">Policy intelligence</div>
          <h1>Fato, chance e impacto separados.</h1>
          <p className="subtitle">
            Tracker legislativo versionado, com fonte oficial, diff, intervalo e caminho de
            exposição.
          </p>
        </div>
        <AsOfIndicator
          freshness={dataState === "stale" ? "Desatualizado" : hasLiveEvents ? "Atual" : "Fixtures sintéticas"}
        />
      </div>

      {dataState === "stale" && (
        <div style={{ marginBottom: 14 }}>
          <StaleWarning lastUpdated={new Date().toISOString()} source="policy/events" />
        </div>
      )}

      <section className="grid grid-4">
        <Metric
          label="Eventos materiais"
          value={hasLiveEvents ? String(materialEvents.length) : "—"}
          note={materialEvents.length > 0 ? "aguarda revisão" : "dado ausente não vira zero"}
          tone={materialEvents.length > 0 ? "warning" : undefined}
        />
        <Metric
          label="Objetos monitorados"
          value={hasLiveEvents ? String(monitoredObjects) : "—"}
          note={hasLiveEvents ? `${monitoredObjects} objeto${monitoredObjects !== 1 ? "s" : ""}` : "dado ausente não vira zero"}
        />
        <Metric
          label="Diffs novos"
          value={hasLiveEvents ? String(Math.min(materialEvents.length, 3)) : "—"}
          note="texto versionado"
        />
        <Metric
          label="Fontes stale"
          value={hasLiveEvents ? String(staleSources) : "—"}
          note={staleSources > 0 ? "requer atenção" : "todas atualizadas"}
          tone={staleSources > 0 ? "warning" : "positive"}
        />
      </section>

      <section className="card card-pad" style={{ marginTop: 14 }}>
        <div className="card-title">
          <h2>Legislative tracker</h2>
          <span>estágio ≠ probabilidade ≠ impacto</span>
        </div>
        {hasLiveEvents ? (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Objeto oficial</th>
                  <th>Estágio jurídico</th>
                  <th>Probabilidade</th>
                  <th>Exposição</th>
                  <th>Controle</th>
                </tr>
              </thead>
              <tbody>
                {policyEvents.map((event) => (
                  <tr key={event.id}>
                    <td>{event.object_name || event.title}</td>
                    <td>
                      <Badge tone="neutral">{event.stage}</Badge>
                    </td>
                    <td>
                      <Badge tone="warn">{event.probability}</Badge>
                    </td>
                    <td>{event.exposure}</td>
                    <td>
                      <Badge
                        tone={
                          event.control === "Revisão humana"
                            ? "bad"
                            : event.control === "Monitorar"
                              ? "good"
                              : "neutral"
                        }
                      >
                        {event.control}
                      </Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <DataStatePanel
            state="missing"
            title="Nenhum evento político registrado"
            detail="Tracker legislativo vazio. Eventos são adicionados quando há materialidade identificada."
          />
        )}
      </section>

      <section className="grid grid-3" style={{ marginTop: 14 }}>
        <article className="card card-pad">
          <h2>Timeline versionada</h2>
          <p className="subtitle">
            Apresentado → Comissão. Diff: 1 adição, 1 remoção. Fonte e knowledge_at preservados.
          </p>
        </article>
        <article className="card card-pad">
          <h2>Matriz de exposição</h2>
          <p className="subtitle">
            Evento → setor → driver → métrica → emissor → tese → carteira, com confiança por
            aresta.
          </p>
        </article>
        <article className="card card-pad">
          <h2>Corroboração</h2>
          <p className="subtitle">
            Materialidade combina exposição, freshness e fontes corroborantes; ausência não reduz
            chance.
          </p>
        </article>
      </section>

      <div style={{ marginTop: 14 }}>
        <StatePanel
          title="Sem alteração automática"
          detail="Impacto material pausa no Temporal; tese e carteira permanecem imutáveis até decisão humana autorizada."
        />
      </div>
    </>
  );
}

export default function PolicyPage() {
  return (
    <Suspense
      fallback={
        <>
          <div className="page-head">
            <div>
              <div className="eyebrow">Policy intelligence</div>
              <h1>Fato, chance e impacto separados.</h1>
            </div>
          </div>
          <LoadingSkeleton lines={6} />
        </>
      }
    >
      <PolicyContent />
    </Suspense>
  );
}
