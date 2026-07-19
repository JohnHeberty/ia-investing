import { AsOfIndicator, Badge, Metric, StatePanel } from "@/components/domain";

type WorkspacePageProps = {
  eyebrow: string;
  title: string;
  subtitle: string;
  metrics: Array<{ label: string; value: string; note: string; tone?: string }>;
  sections: Array<{ title: string; status?: string; body: string }>;
};

export function WorkspacePage({ eyebrow, title, subtitle, metrics, sections }: WorkspacePageProps) {
  return (
    <>
      <div className="page-head">
        <div>
          <div className="eyebrow">{eyebrow}</div>
          <h1>{title}</h1>
          <p className="subtitle">{subtitle}</p>
        </div>
        <AsOfIndicator />
      </div>
      <section className="grid grid-4">
        {metrics.map((metric) => (
          <Metric key={metric.label} {...metric} />
        ))}
      </section>
      <section className="grid grid-3" style={{ marginTop: 14 }}>
        {sections.map((section) => (
          <article className="card card-pad" key={section.title}>
            <div className="card-title">
              <h2>{section.title}</h2>
              {section.status && (
                <Badge
                  tone={
                    section.status === "Saudável"
                      ? "good"
                      : section.status === "Atenção"
                        ? "warn"
                        : "neutral"
                  }
                >
                  {section.status}
                </Badge>
              )}
            </div>
            <p style={{ color: "var(--muted)", fontSize: 12, lineHeight: 1.65 }}>{section.body}</p>
          </article>
        ))}
      </section>
      <div style={{ marginTop: 14 }}>
        <StatePanel
          title="Temporalidade preservada"
          detail="Filtros, fontes e estados de erro mantêm o as_of atual. Zero nunca substitui dado ausente."
        />
      </div>
    </>
  );
}
