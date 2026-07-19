import { AsOfIndicator, Badge, Metric, StatePanel } from "@/components/domain";

const impacts = [
  ["Câmara · PL 123/2026", "Comissão", "42–68%", "Energia", "Revisão humana"],
  ["Senado · PL 456/2026", "Apresentado", "18–39%", "Financeiro", "Monitorar"],
] as const;

export default function PolicyPage() {
  return (
    <>
      <div className="page-head">
        <div>
          <div className="eyebrow">Policy intelligence · demo</div>
          <h1>Fato, chance e impacto separados.</h1>
          <p className="subtitle">
            Tracker legislativo versionado, com fonte oficial, diff, intervalo e caminho de
            exposição.
          </p>
        </div>
        <AsOfIndicator freshness="Fixtures sintéticas" />
      </div>
      <section className="grid grid-4">
        <Metric label="Eventos materiais" value="1" note="aguarda revisão" tone="warning" />
        <Metric label="Objetos monitorados" value="2" note="Câmara e Senado" />
        <Metric label="Diffs novos" value="1" note="texto versionado" />
        <Metric label="Fontes stale" value="0" note="ambiente demo" tone="positive" />
      </section>
      <section className="card card-pad" style={{ marginTop: 14 }}>
        <div className="card-title">
          <h2>Legislative tracker</h2>
          <span>estágio ≠ probabilidade ≠ impacto</span>
        </div>
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
              {impacts.map(([object, stage, probability, exposure, control]) => (
                <tr key={object}>
                  <td>{object}</td>
                  <td>
                    <Badge tone="neutral">{stage}</Badge>
                  </td>
                  <td>
                    <Badge tone="warn">{probability}</Badge>
                  </td>
                  <td>{exposure}</td>
                  <td>
                    <Badge tone={control === "Revisão humana" ? "bad" : "good"}>{control}</Badge>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
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
            Evento → setor → driver → métrica → emissor → tese → carteira, com confiança por aresta.
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
