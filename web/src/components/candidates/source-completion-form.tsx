"use client";

import { useState, type FormEvent } from "react";
import { addCandidateSource, type SourceKind } from "@/lib/candidate-api";
import styles from "./candidate-intelligence.module.css";

const options: Array<[SourceKind, string]> = [
  ["company_website", "Site oficial"],
  ["investor_relations", "Relações com investidores"],
  ["financial_reports", "Relatórios e resultados"],
  ["cvm_profile", "Cadastro CVM"],
  ["cvm_filings", "Documentos CVM"],
  ["b3_listing", "Listagem B3"],
  ["governance", "Governança"],
  ["newsroom", "Notícias oficiais"],
];

export function SourceCompletionForm({ candidateId, etag, suggestedKind, onSaved }: { candidateId: string; etag: string; suggestedKind?: SourceKind | null; onSaved: () => void }) {
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    const form = new FormData(event.currentTarget);
    try {
      await addCandidateSource(candidateId, etag, {
        kind: String(form.get("kind")) as SourceKind,
        url: String(form.get("url")),
        notes: String(form.get("notes") ?? "") || undefined,
      });
      event.currentTarget.reset();
      onSaved();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Falha ao salvar fonte");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form className={styles.layout} onSubmit={submit}>
      <div className={styles.formGrid}>
        <div className={styles.field}><label htmlFor="kind">Tipo de fonte *</label><select id="kind" name="kind" defaultValue={suggestedKind ?? "financial_reports"}>{options.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></div>
        <div className={styles.field}><label htmlFor="url">URL oficial *</label><input id="url" name="url" type="url" required placeholder="https://ri.empresa.com.br/resultados" /></div>
        <div className={`${styles.field} ${styles.full}`}><label htmlFor="notes">Observação</label><textarea id="notes" name="notes" placeholder="Como você confirmou que esta página pertence à companhia?" /></div>
      </div>
      <p className="subtitle">A URL fornecida fica como descoberta pelo usuário e ainda passa pela validação automática de identidade, domínio e conteúdo.</p>
      {error && <div className={styles.error} role="alert">{error}</div>}
      <button className="button" disabled={submitting}>{submitting ? "Salvando..." : "Salvar fonte para validação"}</button>
    </form>
  );
}
