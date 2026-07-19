import { ArrowUpRight, CircleAlert, FileText, ShieldCheck } from "lucide-react";

import { AsOfIndicator, Badge, Metric } from "@/components/domain";

const portfolios = [
  ["Aurora Quality", "Qualidade · Long Only", "18,4%", "11,2%", "Aprovada", "good", 92],
  ["Atlas Dividendos", "Dividendos · Low Vol", "15,1%", "8,7%", "Paper live", "good", 87],
  ["Cerrado Value", "Value · Contrarian", "13,8%", "14,6%", "Comitê", "warn", 79],
  ["Litoral Small Caps", "Small caps · Growth", "21,3%", "19,8%", "Simulada", "neutral", 74],
] as const;

export default function MissionControlPage() {
  return (
    <>
      <div className="page-head">
        <div>
          <div className="eyebrow">Mission control</div>
          <h1>Decisões com contexto, não ruído.</h1>
          <p className="subtitle">
            Visão consolidada das carteiras-modelo, riscos materiais e trabalho pendente da equipe.
          </p>
        </div>
        <AsOfIndicator />
      </div>
      <section className="grid grid-4" aria-label="Indicadores principais">
        <Metric label="NAV sob análise" value="R$ 48,2 mi" note="4 carteiras comparáveis" />
        <Metric
          label="Retorno esperado"
          value="16,7%"
          note="mediana anualizada · cenário base"
          tone="positive"
        />
        <Metric label="Risco ativo" value="3 limites" note="1 hard · 2 soft" tone="warning" />
        <Metric
          label="Evidência saudável"
          value="94,2%"
          note="claims materiais com citação"
          tone="positive"
        />
      </section>
      <div className="split">
        <section className="card card-pad">
          <div className="card-title">
            <h2>Carteiras elegíveis · Top comparável</h2>
            <span>BRL · 12–24 meses</span>
          </div>
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>#</th>
                  <th>Carteira</th>
                  <th>Estágio</th>
                  <th className="numeric">Retorno</th>
                  <th className="numeric">Vol.</th>
                  <th>Confiança</th>
                </tr>
              </thead>
              <tbody>
                {portfolios.map((item, index) => (
                  <tr key={item[0]}>
                    <td className="rank">0{index + 1}</td>
                    <td>
                      <div className="portfolio-name">{item[0]}</div>
                      <div className="portfolio-meta">{item[1]}</div>
                    </td>
                    <td>
                      <Badge tone={item[5]}>{item[4]}</Badge>
                    </td>
                    <td className="numeric positive">{item[2]}</td>
                    <td className="numeric">{item[3]}</td>
                    <td>
                      <span className="rank">{item[6]}%</span>
                      <div className="bar">
                        <span style={{ width: `${item[6]}%` }} />
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
        <section className="card card-pad">
          <div className="card-title">
            <h2>Eventos materiais</h2>
            <span>últimas 24h</span>
          </div>
          <div className="timeline">
            <div className="event">
              <div className="event-icon">
                <ShieldCheck size={12} />
              </div>
              <div>
                <strong>Risk review concluído</strong>
                <p>Aurora Quality permaneceu dentro dos 14 limites do mandato.</p>
              </div>
              <time>17:42</time>
            </div>
            <div className="event">
              <div className="event-icon">
                <FileText size={12} />
              </div>
              <div>
                <strong>Nova evidência CVM</strong>
                <p>ITR vinculada a 7 claims da tese de VALE3.</p>
              </div>
              <time>16:18</time>
            </div>
            <div className="event">
              <div className="event-icon">
                <CircleAlert size={12} />
              </div>
              <div>
                <strong>Dados parcialmente stale</strong>
                <p>Curva DI ultrapassou a janela de freshness da fonte.</p>
              </div>
              <time>14:03</time>
            </div>
          </div>
        </section>
      </div>
      <section className="grid grid-3" style={{ marginTop: 14 }}>
        <article className="card card-pad">
          <div className="card-title">
            <h2>Funil de pesquisa</h2>
            <ArrowUpRight size={14} />
          </div>
          <MetricLine label="Oportunidades triadas" value="28" />
          <MetricLine label="Casos em pesquisa" value="11" />
          <MetricLine label="Prontos para comitê" value="3" />
        </article>
        <article className="card card-pad">
          <div className="card-title">
            <h2>Pendências humanas</h2>
            <span>SLA</span>
          </div>
          <MetricLine label="Revisões independentes" value="4" tone="warning" />
          <MetricLine label="Approvals de agent" value="2" />
          <MetricLine label="Waivers expirando" value="1" tone="negative" />
        </article>
        <article className="card card-pad">
          <div className="card-title">
            <h2>Operação de agents</h2>
            <span>hoje</span>
          </div>
          <MetricLine label="Runs concluídos" value="146" tone="positive" />
          <MetricLine label="Schema pass" value="100%" />
          <MetricLine label="Custo acumulado" value="US$ 18,42" />
        </article>
      </section>
    </>
  );
}

function MetricLine({ label, value, tone }: { label: string; value: string; tone?: string }) {
  return (
    <div
      style={{
        display: "flex",
        justifyContent: "space-between",
        padding: "11px 0",
        borderTop: "1px solid var(--line-soft)",
        fontSize: 11,
      }}
    >
      <span style={{ color: "var(--muted)" }}>{label}</span>
      <strong className={tone} style={{ fontFamily: "var(--font-mono)" }}>
        {value}
      </strong>
    </div>
  );
}
