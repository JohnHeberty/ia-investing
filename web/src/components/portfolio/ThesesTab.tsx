import { Badge, StatePanel } from "@/components/domain";
import type { PortfolioThesis } from "@/hooks/use-portfolios";

interface ThesesTabProps {
  theses: PortfolioThesis[];
  isLoading: boolean;
}

function recBadgeTone(rec: string): "good" | "warn" | "bad" | "neutral" {
  switch (rec) {
    case "buy":
      return "good";
    case "sell":
      return "bad";
    case "hold":
      return "neutral";
    case "watch":
      return "warn";
    default:
      return "neutral";
  }
}

function statusBadgeTone(status: string): "good" | "warn" | "bad" | "neutral" {
  switch (status) {
    case "active":
      return "good";
    case "approved":
      return "good";
    case "draft":
      return "neutral";
    case "monitoring":
      return "warn";
    case "completed":
      return "neutral";
    case "archived":
      return "neutral";
    case "stale":
      return "warn";
    case "closed":
      return "bad";
    default:
      return "neutral";
  }
}

function ThesisCard({ thesis }: { thesis: PortfolioThesis }) {
  const expiresDate = new Date(thesis.expires_at);
  const now = new Date();
  const daysUntilExpiry = Math.ceil(
    (expiresDate.getTime() - now.getTime()) / (1000 * 60 * 60 * 24),
  );
  const isExpiringSoon = daysUntilExpiry <= 30 && daysUntilExpiry > 0;
  const isExpired = daysUntilExpiry <= 0;

  return (
    <div className="card card-pad" style={{ marginBottom: 12 }}>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-start",
          marginBottom: 8,
        }}
      >
        <div>
          <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 4 }}>
            <Badge tone={recBadgeTone(thesis.recommendation)}>
              {thesis.recommendation.toUpperCase()}
            </Badge>
            <Badge tone={statusBadgeTone(thesis.version_status)}>
              v{thesis.version_number} · {thesis.version_status}
            </Badge>
            {thesis.thesis_status !== thesis.version_status && (
              <Badge tone={statusBadgeTone(thesis.thesis_status)}>
                tese: {thesis.thesis_status}
              </Badge>
            )}
          </div>
          <div style={{ fontSize: 13, lineHeight: 1.5, color: "var(--text)" }}>
            {thesis.summary}
          </div>
        </div>
        <div style={{ textAlign: "right", minWidth: 100 }}>
          <div style={{ fontSize: 11, color: "var(--muted)" }}>Confiança</div>
          <div style={{ fontFamily: "var(--font-mono)", fontSize: 14, fontWeight: 500 }}>
            {Math.round(thesis.recommendation_confidence * 100)}%
          </div>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 12, marginTop: 12 }}>
        {thesis.assumptions.length > 0 && (
          <div>
            <div style={{ fontSize: 11, fontWeight: 500, color: "var(--accent)", marginBottom: 4 }}>
              Premissas
            </div>
            {thesis.assumptions.map((a, i) => (
              <div key={i} style={{ fontSize: 12, color: "var(--muted)", marginBottom: 2 }}>
                • {String(a.description || a.text || JSON.stringify(a))}
              </div>
            ))}
          </div>
        )}
        {thesis.catalysts.length > 0 && (
          <div>
            <div style={{ fontSize: 11, fontWeight: 500, color: "var(--blue)", marginBottom: 4 }}>
              Catalisadores
            </div>
            {thesis.catalysts.map((c, i) => (
              <div key={i} style={{ fontSize: 12, color: "var(--muted)", marginBottom: 2 }}>
                • {String(c.description || c.text || JSON.stringify(c))}
              </div>
            ))}
          </div>
        )}
        {thesis.risks.length > 0 && (
          <div>
            <div style={{ fontSize: 11, fontWeight: 500, color: "var(--amber)", marginBottom: 4 }}>
              Riscos
            </div>
            {thesis.risks.map((r, i) => (
              <div key={i} style={{ fontSize: 12, color: "var(--muted)", marginBottom: 2 }}>
                • {String(r.description || r.text || JSON.stringify(r))}
              </div>
            ))}
          </div>
        )}
      </div>

      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          marginTop: 12,
          paddingTop: 8,
          borderTop: "1px solid var(--line)",
          fontSize: 11,
          color: "var(--muted)",
        }}
      >
        <span>
          Criado por: {thesis.created_by}
          {thesis.approved_by && ` · Aprovado por: ${thesis.approved_by}`}
        </span>
        <span>
          Dados até: {new Date(thesis.data_as_of).toLocaleDateString("pt-BR")}
          {" · "}
          Expira:{" "}
          <span
            style={{
              color: isExpired ? "var(--red)" : isExpiringSoon ? "var(--amber)" : "var(--muted)",
            }}
          >
            {expiresDate.toLocaleDateString("pt-BR")}
            {isExpired ? " (expirada)" : isExpiringSoon ? ` (${daysUntilExpiry}d)` : ""}
          </span>
        </span>
      </div>
    </div>
  );
}

export function ThesesTab({ theses, isLoading }: ThesesTabProps) {
  if (isLoading) {
    return <StatePanel title="Teses de Investimento" detail="Carregando teses vinculadas..." />;
  }

  if (theses.length === 0) {
    return (
      <div className="card card-pad">
        <div className="card-title">
          <h2>Teses de Investimento</h2>
        </div>
        <div style={{ padding: 24 }}>
          <p style={{ fontSize: 13, color: "var(--muted)", marginBottom: 12 }}>
            Teses de investimento são gerenciadas pelo workflow institucional. Para vincular teses a
            esta carteira, é necessário criar um portfolio version e associar as teses durante o
            processo de aprovação do comitê.
          </p>
          <div className="state-panel mt-12" data-state="empty">
            <strong>Nenhuma tese vinculada</strong>
            <p>
              Teses e propostas vinculadas a esta carteira aparecerão aqui quando conectadas ao
              workflow de aprovação do comitê de investimento.
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div>
      <div className="card card-pad" style={{ marginBottom: 16 }}>
        <div className="card-title">
          <h2>Teses de Investimento</h2>
          <Badge tone="neutral">
            {theses.length} tese{theses.length !== 1 ? "s" : ""}
          </Badge>
        </div>
        <p style={{ fontSize: 12, color: "var(--muted)" }}>
          Teses vinculadas a versões aprovadas desta carteira pelo comitê de investimento.
        </p>
      </div>
      {theses.map((thesis) => (
        <ThesisCard key={thesis.version_id} thesis={thesis} />
      ))}
    </div>
  );
}
