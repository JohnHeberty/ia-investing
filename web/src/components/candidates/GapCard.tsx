"use client";

import type { CandidateDetail } from "@/lib/candidate-api";
import styles from "@/components/candidates/candidate-intelligence.module.css";

export function GapCard({
  gap,
  editingGapId,
  resolveNotes,
  resolving,
  onResolveGap,
  onEdit,
  onCancelEdit,
  onNotesChange,
}: {
  gap: CandidateDetail["gaps"][number];
  editingGapId: string | null;
  resolveNotes: string;
  resolving: boolean;
  onResolveGap: (gapId: string) => void;
  onEdit: (gapId: string) => void;
  onCancelEdit: () => void;
  onNotesChange: (value: string) => void;
}) {
  return (
    <article className={`${styles.gap} ${gap.status === "open" && gap.level === "blocking" ? styles.blocker : ""}`}>
      <div className={styles.gapHeader}>
        <strong>{gap.title}</strong>
        <span className="badge" data-tone={gap.status === "resolved" ? "good" : gap.level === "blocking" ? "bad" : "warn"}>
          {gap.status} · {gap.level}
        </span>
      </div>
      <p className="subtitle">{gap.description}</p>
      <p className="subtitle"><strong>Ação:</strong> {gap.requested_user_action}</p>
      {gap.status === "open" && editingGapId !== gap.id && (
        <button className="button" style={{ marginTop: 8 }} onClick={() => onEdit(gap.id)}>Resolver</button>
      )}
      {editingGapId === gap.id && (
        <form onSubmit={(e) => { e.preventDefault(); onResolveGap(gap.id); }} className={styles.resolveForm}>
          <textarea className="form-input" value={resolveNotes} onChange={(e) => onNotesChange(e.target.value)} placeholder="Notas de resolução (mínimo 3 caracteres)..." aria-required="true" rows={3} />
          <div className={styles.resolveActions}>
            <button type="submit" className="button" disabled={resolveNotes.length < 3 || resolving}>{resolving ? "Salvando..." : "Salvar"}</button>
            <button type="button" className="button secondary" onClick={onCancelEdit}>Cancelar</button>
          </div>
        </form>
      )}
      {gap.status === "resolved" && gap.resolution_notes && (
        <div className={styles.resolvedInfo}>
          <p className="subtitle"><strong>Resolvido por:</strong> {gap.resolved_by}</p>
          <p className="subtitle"><strong>Em:</strong> {gap.resolved_at ? new Intl.DateTimeFormat("pt-BR", { dateStyle: "medium", timeStyle: "medium" }).format(new Date(gap.resolved_at)) : "—"}</p>
          <p className="subtitle"><strong>Notas:</strong> {gap.resolution_notes}</p>
        </div>
      )}
    </article>
  );
}
