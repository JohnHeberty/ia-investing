"use client";

import Link from "next/link";
import { CheckCircle2, ShieldAlert, XCircle } from "lucide-react";
import type { ExplorationDetail } from "@/lib/candidate-api";
import styles from "@/components/candidates/candidate-intelligence.module.css";

function score(value: string): string {
  return `${(Number(value) * 100).toFixed(0)}%`;
}

export function SuggestionCard({
  item,
  workingSuggestion,
  onPromote,
  onDismiss,
}: {
  item: ExplorationDetail["suggestions"][number];
  workingSuggestion: string | null;
  onPromote: (id: string) => void;
  onDismiss: (id: string) => void;
}) {
  const busy = workingSuggestion === item.id;

  return (
    <article className={styles.source}>
      <div className={styles.sourceHeader}>
        <div>
          <strong>{item.exchange}:{item.ticker}</strong>
          <div className={styles.meta}>quantitativo {score(item.quantitative_score)} · dados {score(item.data_coverage_score)} · fontes {score(item.source_discovery_score)}</div>
        </div>
        <span className="badge">{item.status}</span>
      </div>
      <p>{item.rationale}</p>
      {!!item.signals.length && <p className="subtitle"><strong>Sinais:</strong> {item.signals.join(" · ")}</p>}
      {!!item.risks.length && <p className="subtitle"><ShieldAlert size={13} /> <strong>Riscos:</strong> {item.risks.join(" · ")}</p>}
      {item.status === "new" && (
        <div className={styles.actions}>
          <button className="button" type="button" disabled={busy} onClick={() => onPromote(item.id)}><CheckCircle2 size={14} /> Promover para investigação</button>
          <button className="button secondary" type="button" disabled={busy} onClick={() => onDismiss(item.id)}><XCircle size={14} /> Dispensar</button>
        </div>
      )}
      {item.promoted_candidate_id && <Link href={`/opportunities/candidates/${item.promoted_candidate_id}`}>Abrir candidato promovido</Link>}
    </article>
  );
}
