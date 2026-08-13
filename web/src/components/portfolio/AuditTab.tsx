import { LoadingSkeleton } from "@/components/data-state-components";
import type { AuditLogEntry } from "@/hooks/use-audit-logs";

const actionLabels: Record<string, string> = {
  create: "Criação",
  update: "Atualização",
  delete: "Exclusão",
  transition: "Transição",
  "mandate.create": "Criação de Mandato",
  "portfolio.create": "Criação de Carteira",
  "portfolio.update": "Atualização de Carteira",
};

interface AuditTabProps {
  auditEntries: AuditLogEntry[];
  auditLoading: boolean;
}

export function AuditTab({ auditEntries, auditLoading }: AuditTabProps) {
  return (
    <div className="card card-pad">
      <div className="card-title">
        <h2>Trilha de Auditoria</h2>
        {auditEntries.length > 0 && (
          <span className="audit-meta">{auditEntries.length} registros</span>
        )}
      </div>
      {auditLoading ? (
        <LoadingSkeleton lines={4} />
      ) : auditEntries.length === 0 ? (
        <div className="state-panel mt-12" data-state="empty">
          <strong>Nenhum registro</strong>
          <p>
            Ações realizadas nesta carteira aparecerão aqui quando conectadas ao ledger de
            auditoria.
          </p>
        </div>
      ) : (
        <div className="mt-12">
          {auditEntries.map((entry) => (
            <div key={entry.id} className="audit-entry">
              <div
                className={`audit-dot ${entry.action.includes("create") ? "create" : entry.action.includes("delete") ? "delete" : "update"}`}
              />
              <div className="audit-detail">
                <div className="audit-action">{actionLabels[entry.action] || entry.action}</div>
                <div className="audit-meta">
                  {entry.resource_type}
                  {entry.resource_id ? ` · ${entry.resource_id.toString().slice(0, 8)}…` : ""}
                </div>
                {entry.changes && Object.keys(entry.changes).length > 0 && (
                  <div
                    className="audit-meta"
                    style={{ marginTop: 2, fontFamily: "var(--font-mono)" }}
                  >
                    {Object.entries(entry.changes).map(([key, val]) => (
                      <span key={key} style={{ marginRight: 8 }}>
                        {key}:{" "}
                        {typeof val === "object" &&
                        val !== null &&
                        "after" in (val as Record<string, unknown>)
                          ? String((val as Record<string, unknown>).after ?? "—")
                          : String(val)}
                      </span>
                    ))}
                  </div>
                )}
              </div>
              <div className="audit-time">
                {new Date(entry.timestamp).toLocaleString("pt-BR", {
                  day: "2-digit",
                  month: "2-digit",
                  year: "2-digit",
                  hour: "2-digit",
                  minute: "2-digit",
                })}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
