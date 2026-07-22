"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { createCandidate } from "@/lib/candidate-api";
import styles from "./candidate-intelligence.module.css";

export function CandidateCreateForm({ onClose }: { onClose?: () => void }) {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    const form = new FormData(event.currentTarget);
    try {
      const candidate = await createCandidate({
        ticker: String(form.get("ticker") ?? ""),
        exchange: String(form.get("exchange") ?? "B3"),
        legal_name: String(form.get("legal_name") ?? "") || undefined,
        cnpj: String(form.get("cnpj") ?? "") || undefined,
        cvm_code: String(form.get("cvm_code") ?? "") || undefined,
        rationale: String(form.get("rationale") ?? "") || undefined,
      });
      onClose?.();
      router.push(`/opportunities/candidates/${candidate.id}`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Falha ao cadastrar candidato");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form className={`card card-pad ${styles.layout}`} onSubmit={submit}>
      <div className="card-title"><h2>Novo candidato de investimento</h2><span>investigação completa</span></div>
      <div className={styles.formGrid}>
        <div className={styles.field}><label htmlFor="ticker">Ticker *</label><input id="ticker" name="ticker" required maxLength={24} placeholder="WEGE3" autoCapitalize="characters" /></div>
        <div className={styles.field}><label htmlFor="exchange">Bolsa *</label><input id="exchange" name="exchange" required defaultValue="B3" maxLength={20} /></div>
        <div className={styles.field}><label htmlFor="legal_name">Razão social</label><input id="legal_name" name="legal_name" maxLength={300} /></div>
        <div className={styles.field}><label htmlFor="cnpj">CNPJ</label><input id="cnpj" name="cnpj" maxLength={32} /></div>
        <div className={styles.field}><label htmlFor="cvm_code">Código CVM</label><input id="cvm_code" name="cvm_code" maxLength={32} /></div>
        <div className={`${styles.field} ${styles.full}`}><label htmlFor="rationale">Por que investigar</label><textarea id="rationale" name="rationale" maxLength={4000} placeholder="Hipótese inicial, evento observado ou motivo da indicação." /></div>
      </div>
      {error && <div className={styles.error} role="alert">{error}</div>}
      <div className={styles.actions}>
        <button className="button" disabled={submitting}>{submitting ? "Cadastrando..." : "Cadastrar e iniciar investigação"}</button>
        {onClose && <button className="button secondary" type="button" onClick={onClose}>Cancelar</button>}
      </div>
    </form>
  );
}
