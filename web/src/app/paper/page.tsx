import { AsOfIndicator, Badge, Metric, StatePanel } from "@/components/domain";

export default function PaperOperationsPage() {
  return (
    <>
      <div className="page-head">
        <div>
          <div className="eyebrow">Paper operations · demo</div>
          <h1>Execução simulada e reconciliada.</h1>
          <p className="subtitle">
            Intents, orders, fills, custos e breaks. Nenhuma integração ou credencial de corretora.
          </p>
        </div>
        <AsOfIndicator freshness="Paper only" />
      </div>
      <section className="grid grid-4">
        <Metric label="Intents aprovados" value="2" note="four-eyes" />
        <Metric label="Partial fills" value="1" note="sim-v1 · seed 42" tone="warning" />
        <Metric label="Breaks críticos" value="1" note="novos submits bloqueados" tone="negative" />
        <Metric label="Slippage" value="9,4 bps" note="spread + impacto" />
      </section>
      <section className="card card-pad" style={{ marginTop: 14 }}>
        <div className="card-title">
          <h2>Order lifecycle</h2>
          <Badge tone="warn">PAPER</Badge>
        </div>
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
              <tr>
                <td>BUY · instrumento demo</td>
                <td>portfolio-v7</td>
                <td>
                  <Badge tone="warn">Partially filled</Badge>
                </td>
                <td className="numeric">100 / 120</td>
                <td>
                  <Badge tone="bad">Break aberto</Badge>
                </td>
              </tr>
              <tr>
                <td>SELL · instrumento demo</td>
                <td>portfolio-v7</td>
                <td>
                  <Badge tone="good">Filled</Badge>
                </td>
                <td className="numeric">50 / 50</td>
                <td>
                  <Badge tone="good">Matched</Badge>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
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
